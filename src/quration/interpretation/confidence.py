"""
Confidence scoring for interpretation claims.

This module provides confidence scoring algorithms for evaluating
the reliability of interpretation claims based on evidence quality.
"""

from dataclasses import dataclass, field
from typing import Any

from quration.interpretation.models import (
    ClaimType,
    ConfidenceLevel,
    EvidenceSource,
    InterpretationClaim,
    InterpretationResult,
    ToolCallRecord,
    ToolCallStatus,
)


@dataclass
class EvidenceWeights:
    """Weights for different types of evidence."""

    # Source type weights (0-1)
    literature_citation: float = 0.9
    database_lookup: float = 0.85
    tool_result: float = 0.8
    inference: float = 0.4
    data_observation: float = 0.7

    # Quality modifiers
    recent_publication: float = 1.1  # Papers < 5 years
    high_impact_journal: float = 1.2
    multiple_sources: float = 1.15  # Multiple citations
    consistent_evidence: float = 1.2  # Multiple sources agree
    contradictory_evidence: float = 0.6

    # Confidence modifiers
    high_confidence_tool: float = 1.1
    cached_result: float = 0.95  # Slightly lower for cached
    failed_tool: float = 0.0


@dataclass
class ConfidenceScore:
    """Confidence score with explanation."""

    score: float  # 0.0 to 1.0
    level: ConfidenceLevel
    explanation: str
    factors: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_score(cls, score: float, factors: dict[str, float] | None = None) -> "ConfidenceScore":
        """Create confidence score from numeric value.

        Args:
            score: Score between 0 and 1
            factors: Contributing factors

        Returns:
            ConfidenceScore with appropriate level
        """
        # Clamp score
        score = max(0.0, min(1.0, score))

        # Determine level
        if score >= 0.75:
            level = ConfidenceLevel.HIGH
        elif score >= 0.45:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        # Generate explanation
        explanations = []
        if factors:
            if factors.get("evidence_count", 0) > 0:
                explanations.append(f"Based on {int(factors['evidence_count'])} evidence sources")
            if factors.get("literature_support", 0) > 0:
                explanations.append("Supported by literature")
            if factors.get("tool_verification", 0) > 0:
                explanations.append("Verified by database lookups")
            if factors.get("consistency", 0) > 0.5:
                explanations.append("Consistent across sources")
            if factors.get("inference_penalty", 0) > 0:
                explanations.append("Includes inferred conclusions")

        explanation = ". ".join(explanations) if explanations else f"Score: {score:.2f}"

        return cls(
            score=score,
            level=level,
            explanation=explanation,
            factors=factors or {},
        )


class ConfidenceScorer:
    """Scorer for evaluating claim confidence.

    This scorer considers:
    - Evidence source quality
    - Number of supporting sources
    - Tool call success/failure
    - Claim type (data vs inference)
    - Evidence consistency

    Example:
        ```python
        scorer = ConfidenceScorer()

        # Score a single claim
        score = scorer.score_claim(claim, tool_calls)

        # Score an entire interpretation
        result = scorer.score_interpretation(interpretation_result)
        ```
    """

    def __init__(self, weights: EvidenceWeights | None = None):
        """Initialize the scorer.

        Args:
            weights: Custom evidence weights
        """
        self.weights = weights or EvidenceWeights()

    def score_claim(
        self,
        claim: InterpretationClaim,
        tool_calls: list[ToolCallRecord] | None = None,
    ) -> ConfidenceScore:
        """Score a single claim's confidence.

        Args:
            claim: Claim to score
            tool_calls: Related tool call records

        Returns:
            ConfidenceScore
        """
        factors: dict[str, float] = {}
        base_score = 0.5  # Start at medium confidence

        # Factor 1: Claim type weight
        type_weights = {
            ClaimType.LITERATURE: self.weights.literature_citation,
            ClaimType.TOOL_RESULT: self.weights.tool_result,
            ClaimType.FROM_DATA: self.weights.data_observation,
            ClaimType.INFERENCE: self.weights.inference,
        }
        type_weight = type_weights.get(claim.claim_type, 0.5)
        factors["claim_type_weight"] = type_weight
        base_score = type_weight

        # Factor 2: Evidence count
        evidence_count = len(claim.evidence)
        factors["evidence_count"] = evidence_count

        if evidence_count > 0:
            # More evidence increases confidence
            evidence_bonus = min(0.2, evidence_count * 0.05)
            base_score += evidence_bonus
            factors["evidence_bonus"] = evidence_bonus

        # Factor 3: Tool call success rate
        if tool_calls:
            related_calls = self._find_related_calls(claim, tool_calls)
            if related_calls:
                success_count = sum(
                    1 for c in related_calls if c.status == ToolCallStatus.SUCCESS
                )
                success_rate = success_count / len(related_calls)
                factors["tool_success_rate"] = success_rate

                if success_rate > 0.8:
                    factors["tool_verification"] = 0.1
                    base_score += 0.1
                elif success_rate < 0.5:
                    factors["tool_failure_penalty"] = -0.1
                    base_score -= 0.1

        # Factor 4: Genes/pathways mentioned (specificity)
        specificity_count = len(claim.genes_mentioned) + len(claim.pathways_mentioned)
        if specificity_count > 0:
            specificity_bonus = min(0.1, specificity_count * 0.02)
            factors["specificity_bonus"] = specificity_bonus
            base_score += specificity_bonus

        # Factor 5: Existing confidence level (from LLM)
        llm_confidence_map = {
            ConfidenceLevel.HIGH: 0.1,
            ConfidenceLevel.MEDIUM: 0.0,
            ConfidenceLevel.LOW: -0.1,
        }
        llm_adjustment = llm_confidence_map.get(claim.confidence, 0.0)
        factors["llm_confidence_adjustment"] = llm_adjustment
        base_score += llm_adjustment

        # Factor 6: Inference penalty
        if claim.claim_type == ClaimType.INFERENCE:
            factors["inference_penalty"] = -0.1
            base_score -= 0.1

        # Check for literature support
        for evidence in claim.evidence:
            if evidence.source_type in ["pmid", "doi", "pubmed"]:
                factors["literature_support"] = 0.1
                base_score += 0.1
                break

        return ConfidenceScore.from_score(base_score, factors)

    def score_interpretation(
        self, result: InterpretationResult
    ) -> dict[str, Any]:
        """Score an entire interpretation result.

        Args:
            result: InterpretationResult to score

        Returns:
            Scoring summary with claim scores and overall score
        """
        claim_scores = []
        total_score = 0.0

        for claim in result.claims:
            score = self.score_claim(claim, result.tool_calls)
            claim_scores.append({
                "statement": claim.statement[:100],
                "claim_type": claim.claim_type.value,
                "score": score.score,
                "level": score.level.value,
                "explanation": score.explanation,
            })
            total_score += score.score

        # Calculate overall score
        if claim_scores:
            overall_score = total_score / len(claim_scores)
        else:
            overall_score = 0.5  # Default for no claims

        # Factor in tool call success rate
        if result.tool_calls:
            success_rate = sum(
                1 for c in result.tool_calls if c.status == ToolCallStatus.SUCCESS
            ) / len(result.tool_calls)
            # Blend with overall score
            overall_score = (overall_score * 0.7) + (success_rate * 0.3)

        overall_confidence = ConfidenceScore.from_score(overall_score)

        return {
            "overall_score": round(overall_score, 3),
            "overall_level": overall_confidence.level.value,
            "overall_explanation": overall_confidence.explanation,
            "claim_count": len(claim_scores),
            "claim_scores": claim_scores,
            "tool_calls_total": len(result.tool_calls),
            "tool_calls_successful": sum(
                1 for c in result.tool_calls if c.status == ToolCallStatus.SUCCESS
            ),
        }

    def _find_related_calls(
        self,
        claim: InterpretationClaim,
        tool_calls: list[ToolCallRecord],
    ) -> list[ToolCallRecord]:
        """Find tool calls related to a claim.

        Args:
            claim: Claim to match
            tool_calls: All tool calls

        Returns:
            Related tool calls
        """
        related = []

        # Check if claim mentions genes that were looked up
        claim_genes = set(claim.genes_mentioned)
        claim_pathways = set(claim.pathways_mentioned)

        for call in tool_calls:
            # Check tool output for matching genes/pathways
            if call.tool_output:
                output_str = str(call.tool_output).upper()
                if any(gene in output_str for gene in claim_genes):
                    related.append(call)
                    continue
                if any(pathway in output_str for pathway in claim_pathways):
                    related.append(call)
                    continue

            # Check tool input for matching genes
            if call.tool_input:
                input_str = str(call.tool_input).upper()
                if any(gene in input_str for gene in claim_genes):
                    related.append(call)

        return related

    def explain_score(self, score: ConfidenceScore) -> str:
        """Generate detailed explanation of a confidence score.

        Args:
            score: Score to explain

        Returns:
            Detailed explanation string
        """
        lines = [f"Confidence Level: {score.level.value.upper()} ({score.score:.2f})"]
        lines.append("")

        if score.factors:
            lines.append("Contributing Factors:")
            for factor, value in sorted(score.factors.items()):
                if isinstance(value, float):
                    if value > 0:
                        lines.append(f"  + {factor}: +{value:.2f}")
                    elif value < 0:
                        lines.append(f"  - {factor}: {value:.2f}")
                else:
                    lines.append(f"  * {factor}: {value}")

        lines.append("")
        lines.append(f"Summary: {score.explanation}")

        return "\n".join(lines)


class InterpretationValidator:
    """Validator for interpretation quality.

    Validates that interpretations meet quality standards:
    - Minimum evidence requirements
    - Confidence thresholds
    - Claim substantiation
    """

    def __init__(
        self,
        min_confidence: float = 0.4,
        require_evidence: bool = True,
        min_tool_success_rate: float = 0.5,
    ):
        """Initialize validator.

        Args:
            min_confidence: Minimum acceptable confidence score
            require_evidence: Whether claims must have evidence
            min_tool_success_rate: Minimum tool call success rate
        """
        self.min_confidence = min_confidence
        self.require_evidence = require_evidence
        self.min_tool_success_rate = min_tool_success_rate
        self._scorer = ConfidenceScorer()

    def validate(self, result: InterpretationResult) -> dict[str, Any]:
        """Validate an interpretation result.

        Args:
            result: InterpretationResult to validate

        Returns:
            Validation results
        """
        issues = []
        warnings = []

        # Check for empty interpretation
        if not result.summary or len(result.summary.strip()) < 50:
            issues.append("Interpretation summary is too short or empty")

        # Check claims
        if not result.claims:
            warnings.append("No structured claims extracted")
        else:
            # Score each claim
            low_confidence_claims = 0
            unsupported_claims = 0

            for claim in result.claims:
                score = self._scorer.score_claim(claim, result.tool_calls)

                if score.score < self.min_confidence:
                    low_confidence_claims += 1

                if self.require_evidence and not claim.evidence:
                    if claim.claim_type == ClaimType.INFERENCE:
                        unsupported_claims += 1

            if low_confidence_claims > 0:
                warnings.append(
                    f"{low_confidence_claims} claims below confidence threshold"
                )

            if unsupported_claims > 0:
                warnings.append(
                    f"{unsupported_claims} inferred claims without evidence"
                )

        # Check tool calls
        if result.tool_calls:
            success_count = sum(
                1 for c in result.tool_calls if c.status == ToolCallStatus.SUCCESS
            )
            success_rate = success_count / len(result.tool_calls)

            if success_rate < self.min_tool_success_rate:
                issues.append(
                    f"Tool success rate ({success_rate:.1%}) below threshold "
                    f"({self.min_tool_success_rate:.1%})"
                )
        else:
            warnings.append("No tool calls made during interpretation")

        # Overall validation
        is_valid = len(issues) == 0

        return {
            "is_valid": is_valid,
            "issues": issues,
            "warnings": warnings,
            "claim_count": len(result.claims),
            "tool_call_count": len(result.tool_calls),
        }

    def suggest_improvements(self, result: InterpretationResult) -> list[str]:
        """Suggest improvements for an interpretation.

        Args:
            result: InterpretationResult to improve

        Returns:
            List of improvement suggestions
        """
        suggestions = []

        # Check tool diversity
        tool_names = {c.tool_name for c in result.tool_calls}
        if len(tool_names) < 3:
            suggestions.append(
                "Consider using more diverse tools (literature, pathways, interactions)"
            )

        # Check for literature support
        lit_tools = {"search_pubmed", "get_abstract", "search_gene_literature"}
        if not tool_names.intersection(lit_tools):
            suggestions.append("Add literature search to support claims")

        # Check for pathway analysis
        pathway_tools = {
            "get_reactome_pathway",
            "analyze_pathway_enrichment",
            "search_reactome_pathways",
        }
        if not tool_names.intersection(pathway_tools):
            suggestions.append("Consider pathway enrichment analysis")

        # Check for interaction analysis
        interaction_tools = {"get_protein_interactions", "get_interaction_partners"}
        if not tool_names.intersection(interaction_tools):
            suggestions.append("Consider protein interaction analysis")

        # Check claim types
        if result.claims:
            inference_count = sum(
                1 for c in result.claims if c.claim_type == ClaimType.INFERENCE
            )
            if inference_count > len(result.claims) * 0.5:
                suggestions.append(
                    "Many claims are inferences - add more evidence-based claims"
                )

        return suggestions
