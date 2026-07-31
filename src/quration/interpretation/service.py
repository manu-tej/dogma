"""
Interpretation service for bioinformatics data analysis.

This module provides the main service class that orchestrates
all interpretation components for analyzing transcriptomic data.
"""

import logging
from datetime import datetime, timezone
from collections.abc import Sequence
from typing import Any
from uuid import uuid4

from quration.config import get_config
from quration.interpretation.cache import ResultCacheManager, get_cache_manager
from quration.interpretation.citations import CitationCollection, CitationGenerator
from quration.interpretation.claude_integration import ClaudeToolCaller
from quration.interpretation.confidence import ConfidenceScorer, InterpretationValidator
from quration.interpretation.executor import ToolExecutor, create_executor
from quration.interpretation.models import (
    ClaimType,
    ConfidenceLevel,
    InterpretationClaim,
    InterpretationResult,
    InterpretationType,
    TokenUsage,
)
from quration.interpretation.parsers import ClaimExtractor, ResponseParser
from quration.interpretation.prompts import DEGene, PromptBuilder, get_template

logger = logging.getLogger(__name__)


class InterpretationService:
    """Main service for bioinformatics data interpretation.

    This service orchestrates:
    - LLM-powered interpretation with tool augmentation
    - Evidence gathering from databases
    - Claim extraction and confidence scoring
    - Citation generation and bibliography

    Example:
        ```python
        service = InterpretationService()

        # Interpret DEG results
        result = await service.interpret_deg_results(
            upregulated=[("TP53", 2.5), ("BRCA1", 1.8)],
            downregulated=[("MYC", -2.1)],
            condition_a="treated",
            condition_b="control",
        )

        print(result.summary)
        for claim in result.claims:
            print(f"- {claim.statement}")
        ```
    """

    def __init__(
        self,
        executor: ToolExecutor | None = None,
        model: str | None = None,
        enable_cache: bool = True,
    ):
        """Initialize the interpretation service.

        Args:
            executor: Tool executor (creates default if not provided)
            model: Claude model to use (defaults to config)
            enable_cache: Enable result caching
        """
        self._executor = executor or create_executor(include_all_tools=True)
        self._model = model or get_config().interpretation.default_model

        # Initialize components
        self._claude_caller = ClaudeToolCaller(
            executor=self._executor,
            model=self._model,
        )
        self._parser = ResponseParser()
        self._claim_extractor = ClaimExtractor()
        self._scorer = ConfidenceScorer()
        self._validator = InterpretationValidator()
        self._citation_generator = CitationGenerator()
        self._cache = get_cache_manager() if enable_cache else None

        logger.info(f"InterpretationService initialized with model: {self._model}")

    async def interpret_deg_results(
        self,
        # Sequence, not list: list is invariant, so a caller holding
        # list[tuple[str, float, float | None]] could not pass it as list[DEGene].
        upregulated: Sequence[DEGene],
        downregulated: Sequence[DEGene],
        condition_a: str,
        condition_b: str,
        experiment_type: str = "RNA-seq",
        organism: str = "human",
        additional_context: str = "",
        max_iterations: int = 10,
    ) -> InterpretationResult:
        """Interpret differential expression analysis results.

        Args:
            upregulated: (gene, log2fc) or (gene, log2fc, adjusted_p_value) entries.
                The two-element form means significance was not supplied, and the
                prompt says so — it does not mean the genes passed a threshold.
            downregulated: same shape
            condition_a: First condition name
            condition_b: Second condition name
            experiment_type: Type of experiment
            organism: Organism name
            additional_context: Additional context for interpretation
            max_iterations: Maximum tool calling iterations

        Returns:
            InterpretationResult with analysis
        """
        # Build prompt
        builder = PromptBuilder("deg_analysis")
        builder.set_variables(
            experiment_type=experiment_type,
            condition_a=condition_a,
            condition_b=condition_b,
            organism=organism,
        )
        builder.set_deg_results(upregulated, downregulated)

        if additional_context:
            builder.set_context(additional_context)

        system_prompt, user_prompt = builder.build()

        # Run interpretation
        return await self._run_interpretation(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            interpretation_type=InterpretationType.DEG_ANALYSIS,
            max_iterations=max_iterations,
            context={
                # Index rather than unpack: entries may carry a third element
                # (adjusted p-value), and `for g, _ in ...` silently breaks on those.
                "upregulated_genes": [entry[0] for entry in upregulated],
                "downregulated_genes": [entry[0] for entry in downregulated],
                "organism": organism,
            },
        )

    async def interpret_pathway_enrichment(
        self,
        pathways: list[dict[str, Any]],
        experiment_context: str,
        gene_set_size: int | None = None,
        max_iterations: int = 10,
    ) -> InterpretationResult:
        """Interpret pathway enrichment analysis results.

        Args:
            pathways: List of pathway dicts with name, p_value, gene_count
            experiment_context: Description of the experiment
            gene_set_size: Number of genes analyzed
            max_iterations: Maximum iterations

        Returns:
            InterpretationResult
        """
        builder = PromptBuilder("pathway_enrichment")
        builder.set_pathway_results(pathways)
        builder.set_variables(experiment_context=experiment_context)

        if gene_set_size:
            builder.set_variables(gene_set_size=str(gene_set_size))

        system_prompt, user_prompt = builder.build()

        return await self._run_interpretation(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            interpretation_type=InterpretationType.PATHWAY_ENRICHMENT,
            max_iterations=max_iterations,
            context={"pathways": pathways},
        )

    async def analyze_gene_function(
        self,
        genes: list[str],
        analysis_context: str = "",
        max_iterations: int = 10,
    ) -> InterpretationResult:
        """Analyze function and role of specific genes.

        Args:
            genes: List of gene symbols
            analysis_context: Context for the analysis
            max_iterations: Maximum iterations

        Returns:
            InterpretationResult
        """
        builder = PromptBuilder("gene_function")
        builder.set_gene_list(genes)

        if analysis_context:
            builder.set_variables(analysis_context=analysis_context)
        else:
            builder.set_variables(analysis_context="General gene function analysis")

        system_prompt, user_prompt = builder.build()

        return await self._run_interpretation(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            interpretation_type=InterpretationType.GENE_FUNCTION,
            max_iterations=max_iterations,
            context={"genes": genes},
        )

    async def assess_batch_effects(
        self,
        batch_count: int,
        batch_metrics: str,
        samples_per_batch: str = "",
        pca_summary: str = "",
        max_iterations: int = 5,
    ) -> InterpretationResult:
        """Assess batch effects in a dataset.

        Args:
            batch_count: Number of batches
            batch_metrics: Description of batch effect metrics
            samples_per_batch: Sample distribution
            pca_summary: PCA analysis summary
            max_iterations: Maximum iterations

        Returns:
            InterpretationResult
        """
        builder = PromptBuilder("batch_effect")
        builder.set_variables(
            batch_count=str(batch_count),
            batch_metrics=batch_metrics,
        )

        if samples_per_batch:
            builder.set_variables(samples_per_batch=samples_per_batch)
        if pca_summary:
            builder.set_variables(pca_summary=pca_summary)

        system_prompt, user_prompt = builder.build()

        return await self._run_interpretation(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            interpretation_type=InterpretationType.BATCH_EFFECT,
            max_iterations=max_iterations,
        )

    async def review_literature(
        self,
        topic: str,
        focus_areas: str = "",
        research_context: str = "",
        max_iterations: int = 8,
    ) -> InterpretationResult:
        """Review literature on a biological topic.

        Args:
            topic: Topic to review
            focus_areas: Specific areas to focus on
            research_context: Research context
            max_iterations: Maximum iterations

        Returns:
            InterpretationResult
        """
        builder = PromptBuilder("literature_review")
        builder.set_variables(topic=topic)

        if focus_areas:
            builder.set_variables(focus_areas=focus_areas)
        if research_context:
            builder.set_variables(research_context=research_context)

        system_prompt, user_prompt = builder.build()

        return await self._run_interpretation(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            interpretation_type=InterpretationType.LITERATURE_REVIEW,
            max_iterations=max_iterations,
        )

    async def custom_interpretation(
        self,
        prompt: str,
        interpretation_type: InterpretationType = InterpretationType.CUSTOM,
        system_prompt: str | None = None,
        context: dict[str, Any] | None = None,
        max_iterations: int = 10,
    ) -> InterpretationResult:
        """Run a custom interpretation with user-defined prompt.

        Args:
            prompt: User prompt for interpretation
            interpretation_type: Type of interpretation
            system_prompt: Custom system prompt
            context: Additional context data
            max_iterations: Maximum iterations

        Returns:
            InterpretationResult
        """
        return await self._run_interpretation(
            system_prompt=system_prompt,
            user_prompt=prompt,
            interpretation_type=interpretation_type,
            max_iterations=max_iterations,
            context=context,
        )

    async def _run_interpretation(
        self,
        user_prompt: str,
        interpretation_type: InterpretationType,
        system_prompt: str | None = None,
        max_iterations: int = 10,
        context: dict[str, Any] | None = None,
    ) -> InterpretationResult:
        """Run the interpretation pipeline.

        Args:
            user_prompt: User prompt
            interpretation_type: Type of interpretation
            system_prompt: System prompt
            max_iterations: Maximum iterations
            context: Additional context

        Returns:
            InterpretationResult
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Run Claude with tool calling
            raw_result = await self._claude_caller.interpret(
                prompt=user_prompt,
                interpretation_type=interpretation_type,
                system_prompt=system_prompt,
                max_iterations=max_iterations,
                context=context,
            )

            # Parse response
            parsed = self._parser.parse(raw_result.summary)

            # Extract claims
            claims = self._claim_extractor.extract_claims(
                raw_result.summary,
                min_confidence=ConfidenceLevel.LOW,
            )

            # Enrich claims with genes/pathways
            enriched_claims = self._enrich_claims(claims, parsed)

            # Generate citations from tool calls
            citations = CitationCollection()
            for tool_call in raw_result.tool_calls:
                tool_citations = self._citation_generator.from_tool_call(tool_call)
                for citation in tool_citations:
                    citations.add(citation)

            # Add citations as evidence to claims
            for claim in enriched_claims:
                for citation in citations.citations[:5]:  # Limit per claim
                    evidence = self._citation_generator.to_evidence_source(citation)
                    claim.evidence.append(evidence)

            # Score interpretation
            scoring = self._scorer.score_interpretation(raw_result)

            # Validate
            validation = self._validator.validate(raw_result)

            # Calculate timing
            end_time = datetime.now(timezone.utc)
            processing_time_ms = (end_time - start_time).total_seconds() * 1000

            # Build final result
            result = InterpretationResult(
                id=uuid4(),
                interpretation_type=interpretation_type,
                summary=self._generate_summary(raw_result.summary, parsed),
                claims=enriched_claims,
                tool_calls=raw_result.tool_calls,
                open_questions=self._extract_open_questions(parsed),
                limitations=self._extract_limitations(parsed),
                recommendations=self._validator.suggest_improvements(raw_result),
                confidence_score=scoring["overall_score"],
                token_usage=raw_result.token_usage,
                processing_time_ms=processing_time_ms,
                model_used=self._model,
                metadata={
                    "interpretation_text": raw_result.summary,
                    "bibliography": citations.generate_bibliography(),
                    "validation": validation,
                    "tool_count": len(raw_result.tool_calls),
                    "claim_count": len(enriched_claims),
                },
            )

            logger.info(
                f"Interpretation complete: {len(enriched_claims)} claims, "
                f"confidence={scoring['overall_score']:.2f}"
            )

            return result

        except Exception as e:
            logger.exception(f"Interpretation error: {e}")

            # Return error result
            end_time = datetime.now(timezone.utc)
            processing_time_ms = (end_time - start_time).total_seconds() * 1000

            return InterpretationResult(
                id=uuid4(),
                interpretation_type=interpretation_type,
                summary=f"Interpretation failed: {e}",
                claims=[],
                tool_calls=[],
                confidence_score=0.0,
                token_usage=TokenUsage(),
                processing_time_ms=processing_time_ms,
                model_used=self._model,
                metadata={"error": str(e)},
            )

    def _generate_summary(self, interpretation: str, parsed: Any) -> str:
        """Generate summary from interpretation.

        Returns the full interpretation text (up to 10000 chars) to preserve
        content for evaluation. The previous 500-char limit caused truncation
        that hid the actual analysis from benchmarks and downstream consumers.
        """
        max_len = 10000

        # Return the full interpretation text to preserve content for
        # evaluation and downstream consumers. The parsed summary is often
        # just the first paragraph which may be a preamble, not the analysis.
        if interpretation and len(interpretation.strip()) > 50:
            return interpretation[:max_len]

        # Fallback to parsed summary if interpretation is empty/short
        if parsed.summary:
            return parsed.summary[:max_len]

        return interpretation[:max_len]

    def _enrich_claims(
        self,
        claims: list[InterpretationClaim],
        parsed: Any,
    ) -> list[InterpretationClaim]:
        """Enrich claims with parsed genes and pathways."""
        for claim in claims:
            # Add genes mentioned in the statement
            for gene in parsed.genes_mentioned:
                if gene.upper() in claim.statement.upper():
                    if gene not in claim.genes_mentioned:
                        claim.genes_mentioned.append(gene)

            # Add pathways mentioned
            for pathway in parsed.pathways_mentioned:
                if pathway in claim.statement:
                    if pathway not in claim.pathways_mentioned:
                        claim.pathways_mentioned.append(pathway)

        return claims

    def _extract_open_questions(self, parsed: Any) -> list[str]:
        """Extract open questions from parsed response."""
        questions = []

        for statement in parsed.confidence_statements:
            if "unclear" in statement.lower() or "uncertain" in statement.lower():
                questions.append(statement)

        return questions[:5]

    def _extract_limitations(self, parsed: Any) -> list[str]:
        """Extract limitations from parsed response."""
        limitations = []

        keywords = ["limitation", "limited", "cannot", "unable", "caveat"]
        for section in parsed.sections:
            if any(kw in section.title.lower() for kw in keywords):
                limitations.append(section.content[:200])

        return limitations[:5]

    def get_available_tools(self) -> list[str]:
        """Get list of available tools.

        Returns:
            List of tool names
        """
        return self._executor.list_tools()

    def get_metrics(self) -> dict[str, Any]:
        """Get service metrics.

        Returns:
            Metrics dictionary
        """
        return {
            "executor_metrics": self._executor.get_metrics(),
            "model": self._model,
        }


# Factory function
def create_interpretation_service(
    model: str | None = None,
    enable_cache: bool = True,
) -> InterpretationService:
    """Create a configured interpretation service.

    Args:
        model: Model to use
        enable_cache: Enable caching

    Returns:
        InterpretationService instance
    """
    return InterpretationService(
        model=model,
        enable_cache=enable_cache,
    )
