"""LLM-assisted GEO query generation for intelligent dataset discovery."""

import json
from typing import List, Literal

from quration.config import get_config
from quration.llm import get_llm_provider

# Import QuerySpec for the spec function
try:
    from quration.models.geo_search import QuerySpec
except ImportError:
    QuerySpec = None  # type: ignore


TherapyScope = Literal["specific", "broad"]


class GEOQueryGenerator:
    """Generates optimized GEO search queries using LLM assistance."""

    def __init__(self, api_key: str | None = None, provider: str | None = None):
        """Initialize the query generator.

        Args:
            api_key: API key for the LLM provider (uses config if not provided)
            provider: LLM provider name ("anthropic" or "openrouter", uses config if not provided)
        """
        config = get_config()

        # Determine provider
        self.provider_name = provider or config.llm.provider

        # Get provider-specific configuration
        if self.provider_name == "anthropic":
            provider_config = config.llm.anthropic
            self.model = provider_config.smart_model
        elif self.provider_name == "openrouter":
            provider_config = config.llm.openrouter
            self.model = provider_config.smart_model
        elif self.provider_name == "claude_subscription":
            provider_config = config.llm.claude_subscription
            self.model = provider_config.smart_model
        else:
            raise ValueError(f"Unsupported provider: {self.provider_name}")

        # Get LLM provider instance. Extra kwargs are harmless for providers
        # that don't read them (anthropic/openrouter ignore the subscription
        # ones, and vice versa).
        self.llm = get_llm_provider(
            provider_name=self.provider_name,
            api_key=api_key or getattr(provider_config, "api_key", None),
            site_url=getattr(provider_config, "site_url", None),
            app_name=getattr(provider_config, "app_name", None),
            claude_executable=getattr(provider_config, "claude_executable", "claude"),
            force_subscription=getattr(provider_config, "force_subscription", True),
            timeout_seconds=getattr(provider_config, "timeout_seconds", 180),
        )

    def generate_queries(
        self,
        disease_terms: list[str],
        therapy_class: str | None = None,
        therapy_scope: TherapyScope = "specific",
        targets_or_genes: list[str] | None = None,
        study_keywords: list[str] | None = None,
        must_have_clinical: bool = False,
    ) -> list[str]:
        """Generate 3-6 optimized GEO search queries using LLM.

        Args:
            disease_terms: List of disease terms (e.g., ["lung cancer", "NSCLC"])
            therapy_class: Therapy class (e.g., "EGFR-TKI")
            therapy_scope: "specific" to use exact therapy term, "broad" to expand
            targets_or_genes: Target genes or proteins
            study_keywords: Additional keywords
            must_have_clinical: Whether to emphasize clinical/survival data

        Returns:
            List of 3-6 GEO search query strings
        """
        targets_or_genes = targets_or_genes or []
        study_keywords = study_keywords or []

        prompt = self._build_prompt(
            disease_terms=disease_terms,
            therapy_class=therapy_class,
            therapy_scope=therapy_scope,
            targets_or_genes=targets_or_genes,
            study_keywords=study_keywords,
            must_have_clinical=must_have_clinical,
        )

        try:
            content = self.llm.create_message(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=2000,
            )

            # Extract JSON from response
            start_idx = content.find("[")
            end_idx = content.rfind("]") + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                queries = json.loads(json_str)

                if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
                    return queries

        except Exception as e:
            print(f"Error generating queries with LLM: {e}")

        # Fallback to rule-based generation
        return self._generate_fallback_queries(
            disease_terms=disease_terms,
            therapy_class=therapy_class,
            targets_or_genes=targets_or_genes,
            study_keywords=study_keywords,
            must_have_clinical=must_have_clinical,
        )

    def _build_prompt(
        self,
        disease_terms: list[str],
        therapy_class: str | None,
        therapy_scope: TherapyScope,
        targets_or_genes: list[str],
        study_keywords: list[str],
        must_have_clinical: bool,
    ) -> str:
        """Build the LLM prompt for query generation."""
        disease_str = ", ".join(disease_terms)
        genes_str = ", ".join(targets_or_genes) if targets_or_genes else "none"
        keywords_str = ", ".join(study_keywords) if study_keywords else "none"

        therapy_instruction = ""
        if therapy_class:
            if therapy_scope == "specific":
                therapy_instruction = f"""
- Therapy class: {therapy_class} (SPECIFIC - use only this exact term)
"""
            else:
                therapy_instruction = f"""
- Therapy class: {therapy_class} (BROAD - expand to related drug names and class terms)
  For example, if therapy_class is "EGFR-TKI", expand to: gefitinib, erlotinib, afatinib, osimertinib, EGFR inhibitor, etc.
"""

        clinical_instruction = ""
        if must_have_clinical:
            clinical_instruction = """
- MUST include clinical/survival terms: Include terms like "survival", "prognosis", "clinical outcome", "progression-free survival", "overall survival" in some queries.
"""

        prompt = f"""You are an expert in bioinformatics and GEO (Gene Expression Omnibus) database searches.

Generate 3-6 effective GEO search query strings based on the following requirements:

Query Specification:
- Disease terms: {disease_str}
{therapy_instruction}- Target genes: {genes_str}
- Study keywords: {keywords_str}
{clinical_instruction}
IMPORTANT CONSTRAINTS:
- ALL queries must be constrained to "Homo sapiens" (human)
- ALL queries should preferentially target RNA-seq or expression profiling studies
- Weight disease_terms and therapy_class most heavily
- Vary the queries to capture different ways researchers might describe these studies
- Use GEO search syntax with field tags where helpful (e.g., [Organism], [Title], [Description])

Return ONLY a JSON array of query strings, like:
["query 1", "query 2", "query 3", ...]

Do not include any other text or explanation, just the JSON array.
"""

        return prompt

    def _generate_fallback_queries(
        self,
        disease_terms: list[str],
        therapy_class: str | None,
        targets_or_genes: list[str],
        study_keywords: list[str] | None = None,
        must_have_clinical: bool = False,
    ) -> list[str]:
        """Generate fallback queries using rule-based approach."""
        study_keywords = study_keywords or []
        queries = []

        # Base disease query
        disease_query = " OR ".join(disease_terms)

        # Query 1: Disease + organism + RNA-seq
        queries.append(
            f'({disease_query}) AND "Homo sapiens"[Organism] AND ("RNA-seq" OR "expression profiling")'
        )

        # Query 2: Add therapy if present
        if therapy_class:
            queries.append(
                f'({disease_query}) AND {therapy_class} AND "Homo sapiens"[Organism]'
            )

        # Query 3: Add genes if present
        if targets_or_genes:
            genes_query = " OR ".join(targets_or_genes)
            queries.append(
                f'({disease_query}) AND ({genes_query}) AND "Homo sapiens"[Organism]'
            )

        # Query 4: Add study keywords if present (e.g. "muscle biopsy"). Without this,
        # the fallback silently drops the caller's keyword constraint.
        if study_keywords:
            keyword_query = " OR ".join(f'"{kw}"' for kw in study_keywords)
            queries.append(
                f'({disease_query}) AND ({keyword_query}) AND "Homo sapiens"[Organism]'
            )

        # Query 5: Clinical terms if required
        if must_have_clinical:
            queries.append(
                f'({disease_query}) AND (survival OR prognosis OR "clinical outcome") AND "Homo sapiens"[Organism]'
            )

        return queries[:6]


def build_geo_queries_with_llm(spec: "QuerySpec") -> List[str]:
    """
    Use an LLM (Claude) to generate 3-6 GEO search expressions based on the QuerySpec.

    This function matches the original spec signature.

    - Weight disease_terms and therapy_class most heavily.
    - If spec.therapy_scope == "specific": use only the given therapy_class.
    - If spec.therapy_scope == "broad": expand therapy_class into related drug names
      and class terms (e.g., EGFR-TKI → gefitinib, erlotinib, EGFR inhibitor).
    - Always constrain to Homo sapiens and RNA-seq in the generated expressions.
    - If must_have_clinical is True, include survival/prognosis-related terms
      where appropriate.

    Args:
        spec: QuerySpec describing the search requirements

    Returns:
        List of 3-6 GEO search query strings
    """
    generator = GEOQueryGenerator()
    return generator.generate_queries(
        disease_terms=spec.disease_terms,
        therapy_class=spec.therapy_class,
        therapy_scope=spec.therapy_scope,
        targets_or_genes=spec.targets_or_genes,
        study_keywords=spec.study_keywords,
        must_have_clinical=spec.must_have_clinical,
    )
