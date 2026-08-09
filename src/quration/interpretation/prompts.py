"""
Prompt templates for LLM interpretation tasks.

This module provides reusable prompt templates for different
bioinformatics interpretation scenarios.
"""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from string import Template
from typing import Any


class PromptType(str, Enum):
    """Types of interpretation prompts."""

    DEG_ANALYSIS = "deg_analysis"
    BATCH_EFFECT = "batch_effect"
    PATHWAY_ENRICHMENT = "pathway_enrichment"
    GENE_FUNCTION = "gene_function"
    QC_ASSESSMENT = "qc_assessment"
    LITERATURE_REVIEW = "literature_review"
    COMPARISON = "comparison"
    CUSTOM = "custom"


@dataclass
class PromptTemplate:
    """A reusable prompt template with variable substitution."""

    name: str
    prompt_type: PromptType
    system_template: str
    user_template: str
    description: str
    required_variables: list[str]
    optional_variables: list[str]
    recommended_tools: list[str]

    def _fill_missing_optionals(
        self, template_text: str, kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        """Default unsupplied optional variables instead of leaking `$name`.

        `safe_substitute` leaves unknown variables verbatim, so a caller with
        no accession used to send the model the literal line
        `Dataset: $dataset_id` — and a model shown template syntax may fill it
        in, which for an accession means inventing one.

        Two shapes, two defaults. A labeled field (`Dataset: $dataset_id`)
        becomes "not provided" — absence stated, the same convention the DEG
        formatter uses for a missing adjusted p-value. A bare content block
        (`$additional_context` on its own) renders empty, because "not
        provided" dangling at the end of a prompt is itself noise.
        """
        filled = dict(kwargs)
        for variable in self.optional_variables:
            if filled.get(variable):
                continue
            labeled = re.search(rf"\S+:[ \t]*\${variable}\b", template_text)
            filled[variable] = "not provided" if labeled else ""
        return filled

    def render_system(self, **kwargs: Any) -> str:
        """Render the system prompt with variables.

        Args:
            **kwargs: Template variables

        Returns:
            Rendered system prompt
        """
        template = Template(self.system_template)
        rendered = template.safe_substitute(
            **self._fill_missing_optionals(self.system_template, kwargs)
        )
        # Every system prompt demands the claims block — including bespoke and
        # runtime-built templates that never embedded SYSTEM_OUTPUT_FORMAT.
        if "```claims" not in rendered:
            rendered += "\n" + SYSTEM_CLAIMS_CHANNEL
        return rendered

    def render_user(self, **kwargs: Any) -> str:
        """Render the user prompt with variables.

        Args:
            **kwargs: Template variables

        Returns:
            Rendered user prompt
        """
        template = Template(self.user_template)
        return template.safe_substitute(
            **self._fill_missing_optionals(self.user_template, kwargs)
        )

    def render(self, **kwargs: Any) -> tuple[str, str]:
        """Render both system and user prompts.

        Args:
            **kwargs: Template variables

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        return self.render_system(**kwargs), self.render_user(**kwargs)

    def validate_variables(self, **kwargs: Any) -> tuple[bool, list[str]]:
        """Check if all required variables are provided.

        Args:
            **kwargs: Template variables

        Returns:
            Tuple of (is_valid, missing_variables)
        """
        missing = [v for v in self.required_variables if v not in kwargs]
        return len(missing) == 0, missing


# System prompt components
SYSTEM_BASE = """You are an expert bioinformatics analyst with deep knowledge of:
- Gene expression analysis and RNA-seq data interpretation
- Molecular biology and cellular pathways
- Statistical methods for omics data
- Scientific literature and databases

Your task is to provide accurate, evidence-based interpretations."""

SYSTEM_TOOL_GUIDANCE = """
MANDATORY SIGNAL STRENGTH ASSESSMENT:
Before interpreting, classify the overall signal strength:
- STRONG (|log2FC| >= 2.0 for multiple genes, coherent biology): Definitive language OK
- MODERATE (1.0 <= |log2FC| < 2.0 for most genes): Use "suggests", "is consistent with"
- WEAK (|log2FC| < 1.0 for most genes, or housekeeping gene noise present): MUST state signal weakness prominently, MUST NOT use "paradoxical"/"dysregulated"/"coordinated"
- NO SIGNAL (all |log2FC| < 0.5, only housekeeping genes): Report as negative result

State your signal classification explicitly in the Summary section.

If results are noisy or contradictory, flag the uncertainty prominently rather than constructing a speculative narrative.
State what the data clearly shows, then separately note what is speculative or requires further validation.

You have access to bioinformatics tools to gather evidence:
- Use tools to look up gene functions, pathways, and literature
- Ground all claims in tool results and citations
- Be explicit about confidence levels
- Acknowledge limitations and uncertainties"""

# The machine-readable claims channel. Appended by `render_system` to every
# system prompt that does not already carry it, so a template author cannot
# forget it — the service parses this block instead of regex-extracting claims
# from prose, and a template without the instruction silently degrades every
# downstream metric to extractor coverage.
SYSTEM_CLAIMS_CHANNEL = """
End your response with a machine-readable list of every claim your report
makes, in a fenced block with the language tag `claims`:

```claims
[
  {"statement": "<one self-contained assertion>",
   "type": "from_data|tool_result|inference|literature",
   "confidence": "high|medium|low"}
]
```

One entry per distinct assertion your report actually makes — no more, no
fewer. Each statement must stand alone without the surrounding prose. Use
"type" for where the claim comes from: "from_data" (directly from the input),
"tool_result" (from a tool lookup), "literature" (from published work),
"inference" (your reasoning). If your report deliberately asserts nothing,
emit an empty list []."""

SYSTEM_OUTPUT_FORMAT = f"""
Structure your response with:
1. Summary - Key findings in 2-3 sentences
2. Detailed Analysis - Evidence-based interpretation
3. Biological Context - Relevant pathways and mechanisms
4. Confidence Assessment - How certain are the conclusions
5. Recommendations - Suggested follow-up analyses if relevant
{SYSTEM_CLAIMS_CHANNEL}"""


# Prompt templates
DEG_ANALYSIS_TEMPLATE = PromptTemplate(
    name="deg_analysis",
    prompt_type=PromptType.DEG_ANALYSIS,
    description="Interpret differentially expressed genes from RNA-seq analysis",
    system_template=f"""{SYSTEM_BASE}

Your focus is interpreting differentially expressed genes (DEGs) from transcriptomic analysis.
{SYSTEM_TOOL_GUIDANCE}

Consider:
- Biological functions of top DEGs
- Enriched pathways and GO terms
- Known disease associations
- Protein-protein interactions
{SYSTEM_OUTPUT_FORMAT}""",
    user_template="""Analyze the following differentially expressed genes from a $experiment_type experiment comparing $condition_a vs $condition_b.

Dataset: $dataset_id
Organism: $organism
Number of DEGs: $deg_count

Top upregulated genes (by log2FC):
$upregulated_genes

Top downregulated genes (by log2FC):
$downregulated_genes

Statistical thresholds: adjusted p-value < $pvalue_threshold, |log2FC| > $logfc_threshold

Please provide a comprehensive interpretation of these results, focusing on:
1. What biological processes are affected?
2. What pathways are involved?
3. What is the overall biological significance?
$additional_context""",
    required_variables=[
        "experiment_type",
        "condition_a",
        "condition_b",
        "upregulated_genes",
        "downregulated_genes",
    ],
    optional_variables=[
        "dataset_id",
        "organism",
        "deg_count",
        "pvalue_threshold",
        "logfc_threshold",
        "additional_context",
    ],
    recommended_tools=[
        "get_gene_info",
        "search_pubmed",
        "analyze_pathway_enrichment",
        "get_protein_interactions",
    ],
)


BATCH_EFFECT_TEMPLATE = PromptTemplate(
    name="batch_effect_assessment",
    prompt_type=PromptType.BATCH_EFFECT,
    description="Assess and interpret batch effects in omics data",
    system_template=f"""{SYSTEM_BASE}

Your focus is assessing batch effects in omics datasets and their impact on analysis.

IMPORTANT: Provide your assessment DIRECTLY based on the metrics provided. Do NOT say "I will analyze" or plan future steps — analyze the data NOW and give your conclusions.

You do not need to use any tools for batch effect assessment — the metrics provided contain all the information needed. Assess:
- Whether batch and treatment are confounded (compare sample distributions across batches)
- Severity of batch effects (use PVCA percentages and PCA separation)
- Whether batch correction is feasible and recommended
- Specific correction methods appropriate for the situation

Be explicit about confidence levels and acknowledge limitations.""",
    user_template="""Assess the batch effects in this dataset and provide your analysis directly:

Number of batches: $batch_count
Samples per batch: $samples_per_batch

Batch effect metrics:
$batch_metrics

PCA results:
$pca_summary

Provide your assessment NOW covering:
1. Severity classification (none / low / moderate / severe / fatal)
2. Whether batch is confounded with treatment
3. Whether batch correction is needed and which method to use
4. Impact on downstream differential expression analysis
$additional_context""",
    required_variables=["batch_count", "batch_metrics"],
    optional_variables=[
        "dataset_id",
        "samples_per_batch",
        "pca_summary",
        "additional_context",
    ],
    recommended_tools=[],
)


PATHWAY_ENRICHMENT_TEMPLATE = PromptTemplate(
    name="pathway_enrichment_interpretation",
    prompt_type=PromptType.PATHWAY_ENRICHMENT,
    description="Interpret pathway enrichment analysis results",
    system_template=f"""{SYSTEM_BASE}

Your focus is interpreting pathway enrichment results from omics analysis.
{SYSTEM_TOOL_GUIDANCE}

Consider:
- Biological relevance of enriched pathways
- Cross-talk between pathways
- Gene overlap between pathways
- Context-specific pathway activation""",
    user_template="""Interpret the following pathway enrichment results:

Analysis type: $analysis_type
Gene set source: $gene_set_source
Background: $background

Top enriched pathways:
$enriched_pathways

Gene set size: $gene_set_size genes

Please provide:
1. Summary of major biological themes
2. Key pathways and their significance
3. Interconnections between pathways
4. Biological interpretation in context of $experiment_context
$additional_context""",
    required_variables=["enriched_pathways", "experiment_context"],
    optional_variables=[
        "analysis_type",
        "gene_set_source",
        "background",
        "gene_set_size",
        "additional_context",
    ],
    recommended_tools=[
        "get_reactome_pathway",
        "get_kegg_pathway",
        "search_reactome_pathways",
    ],
)


GENE_FUNCTION_TEMPLATE = PromptTemplate(
    name="gene_function_analysis",
    prompt_type=PromptType.GENE_FUNCTION,
    description="Analyze the function and role of specific genes",
    system_template=f"""{SYSTEM_BASE}

Your focus is explaining gene function and biological roles.

You have access to bioinformatics tools to look up gene information, protein functions, interactions, and literature. Use these tools to gather evidence, then synthesize your findings into a comprehensive analysis.

CRITICAL: Your FINAL response must contain the complete written analysis. Do NOT end with statements like "Let me compile..." or "Now I'll analyze..." — you must actually WRITE the full analysis as your final output. After using tools, synthesize all gathered information into a detailed, structured response covering each gene's function, pathways, disease associations, and relevance to the analysis context.""",
    user_template="""Provide a detailed analysis of the following gene(s):

Gene(s): $gene_list

Context: $analysis_context

For each gene, provide:
1. Basic function and protein product
2. Key pathways and biological processes
3. Known disease associations
4. Important interacting partners
5. Relevance to the analysis context

IMPORTANT: After looking up information with tools, you MUST write out the complete analysis. Your final response should be the full written interpretation, not a plan to write one.
$additional_context""",
    required_variables=["gene_list"],
    optional_variables=["analysis_context", "additional_context"],
    recommended_tools=[
        "get_gene_info",
        "get_protein_function",
        "get_interaction_partners",
        "search_gene_literature",
    ],
)


QC_ASSESSMENT_TEMPLATE = PromptTemplate(
    name="qc_assessment",
    prompt_type=PromptType.QC_ASSESSMENT,
    description="Assess quality control metrics for omics data",
    system_template=f"""{SYSTEM_BASE}

Your focus is assessing data quality for omics experiments.
{SYSTEM_TOOL_GUIDANCE}

Evaluate:
- Sample quality metrics
- Technical quality indicators
- Potential issues and outliers
- Recommendations for analysis""",
    user_template="""Assess the quality of this dataset:

Dataset: $dataset_id
Platform: $platform
Sample count: $sample_count

QC Metrics:
$qc_metrics

Sample summary:
$sample_summary

Please evaluate:
1. Overall data quality assessment
2. Any samples that should be excluded
3. Potential technical issues
4. Recommendations for preprocessing
$additional_context""",
    required_variables=["qc_metrics"],
    optional_variables=[
        "dataset_id",
        "platform",
        "sample_count",
        "sample_summary",
        "additional_context",
    ],
    recommended_tools=["get_geo_metadata", "get_geo_samples"],
)


LITERATURE_REVIEW_TEMPLATE = PromptTemplate(
    name="literature_review",
    prompt_type=PromptType.LITERATURE_REVIEW,
    description="Review literature for a biological topic",
    system_template=f"""{SYSTEM_BASE}

Your focus is reviewing and summarizing scientific literature.
{SYSTEM_TOOL_GUIDANCE}

Provide:
- Summary of key findings from literature
- Current understanding of the topic
- Controversies or open questions
- Recent advances and trends""",
    user_template="""Review the literature on:

Topic: $topic

Focus areas:
$focus_areas

Please provide:
1. Overview of current knowledge
2. Key findings from recent studies
3. Mechanisms and pathways involved
4. Open questions and controversies
5. Relevance to $research_context
$additional_context""",
    required_variables=["topic"],
    optional_variables=["focus_areas", "research_context", "additional_context"],
    recommended_tools=["search_pubmed", "get_abstract", "search_gene_literature"],
)


COMPARISON_TEMPLATE = PromptTemplate(
    name="dataset_comparison",
    prompt_type=PromptType.COMPARISON,
    description="Compare results between datasets or conditions",
    system_template=f"""{SYSTEM_BASE}

Your focus is comparing omics results across datasets or conditions.
{SYSTEM_TOOL_GUIDANCE}

Consider:
- Similarities and differences in findings
- Biological explanations for discrepancies
- Technical factors that might explain differences
- Consensus findings across datasets""",
    user_template="""Compare the following datasets/conditions:

Dataset A: $dataset_a_name
$dataset_a_summary

Dataset B: $dataset_b_name
$dataset_b_summary

Comparison metrics:
$comparison_metrics

Please analyze:
1. Key similarities between datasets
2. Notable differences and potential explanations
3. Genes/pathways consistently affected
4. Dataset-specific findings
5. Overall biological interpretation
$additional_context""",
    required_variables=["dataset_a_name", "dataset_b_name"],
    optional_variables=[
        "dataset_a_summary",
        "dataset_b_summary",
        "comparison_metrics",
        "additional_context",
    ],
    recommended_tools=["search_pubmed", "analyze_pathway_enrichment"],
)


# Template registry
_TEMPLATES: dict[str, PromptTemplate] = {
    "deg_analysis": DEG_ANALYSIS_TEMPLATE,
    "batch_effect": BATCH_EFFECT_TEMPLATE,
    "pathway_enrichment": PATHWAY_ENRICHMENT_TEMPLATE,
    "gene_function": GENE_FUNCTION_TEMPLATE,
    "qc_assessment": QC_ASSESSMENT_TEMPLATE,
    "literature_review": LITERATURE_REVIEW_TEMPLATE,
    "comparison": COMPARISON_TEMPLATE,
}


def get_template(name: str) -> PromptTemplate:
    """Get a prompt template by name.

    Args:
        name: Template name

    Returns:
        PromptTemplate

    Raises:
        KeyError: If template not found
    """
    if name not in _TEMPLATES:
        raise KeyError(f"Template '{name}' not found. Available: {list(_TEMPLATES.keys())}")
    return _TEMPLATES[name]


def list_templates() -> list[str]:
    """List available template names.

    Returns:
        List of template names
    """
    return list(_TEMPLATES.keys())


def get_template_info() -> list[dict[str, Any]]:
    """Get information about all available templates.

    Returns:
        List of template info dictionaries
    """
    return [
        {
            "name": t.name,
            "type": t.prompt_type.value,
            "description": t.description,
            "required_variables": t.required_variables,
            "optional_variables": t.optional_variables,
            "recommended_tools": t.recommended_tools,
        }
        for t in _TEMPLATES.values()
    ]


def register_template(template: PromptTemplate) -> None:
    """Register a custom template.

    Args:
        template: Template to register
    """
    _TEMPLATES[template.name] = template


def create_custom_template(
    name: str,
    system_prompt: str,
    user_prompt: str,
    description: str = "",
    required_variables: list[str] | None = None,
    optional_variables: list[str] | None = None,
    recommended_tools: list[str] | None = None,
) -> PromptTemplate:
    """Create a custom prompt template.

    Args:
        name: Template name
        system_prompt: System prompt template
        user_prompt: User prompt template
        description: Template description
        required_variables: Required template variables
        optional_variables: Optional template variables
        recommended_tools: Recommended tools to use

    Returns:
        New PromptTemplate
    """
    return PromptTemplate(
        name=name,
        prompt_type=PromptType.CUSTOM,
        system_template=system_prompt,
        user_template=user_prompt,
        description=description,
        required_variables=required_variables or [],
        optional_variables=optional_variables or [],
        recommended_tools=recommended_tools or [],
    )


#: One differentially expressed gene: (symbol, log2FC) or
#: (symbol, log2FC, adjusted_p_value). The two-element form is accepted so existing
#: callers keep working, but it means "significance unknown", not "significant" —
#: `set_deg_results` says so in the prompt rather than letting the omission pass as
#: a filtered list.
DEGene = tuple[str, float] | tuple[str, float, float | None]


def _symbol(entry: DEGene) -> str:
    return entry[0]


def _fc(entry: DEGene) -> float:
    return entry[1]


def _padj(entry: DEGene) -> float | None:
    """Adjusted p-value, or None when the caller did not supply one."""
    return entry[2] if len(entry) > 2 else None


def _has_significance(entries: Sequence[DEGene]) -> bool:
    return any(_padj(e) is not None for e in entries)


def _format_gene(entry: DEGene) -> str:
    """Render one gene for the prompt.

    Significance is stated when known and marked absent when not. Printing a bare
    fold change for a gene whose adjusted p-value was never provided invites the
    model to call it differentially expressed on effect size alone.
    """
    padj = _padj(entry)
    if padj is None:
        return f"- {_symbol(entry)} (log2FC: {_fc(entry):.2f}, adj. p: not provided)"
    return f"- {_symbol(entry)} (log2FC: {_fc(entry):.2f}, adj. p: {padj:.2e})"


class PromptBuilder:
    """Builder for constructing prompts from templates and data.

    Example:
        ```python
        builder = PromptBuilder("deg_analysis")
        builder.set_variables(
            experiment_type="RNA-seq",
            condition_a="treated",
            condition_b="control",
            upregulated_genes="GENE1, GENE2, GENE3",
            downregulated_genes="GENE4, GENE5",
        )
        system, user = builder.build()
        ```
    """

    def __init__(self, template_name: str):
        """Initialize the builder with a template.

        Args:
            template_name: Name of the template to use
        """
        self._template = get_template(template_name)
        self._variables: dict[str, Any] = {}

    def set_variables(self, **kwargs: Any) -> "PromptBuilder":
        """Set template variables.

        Args:
            **kwargs: Variable values

        Returns:
            Self for chaining
        """
        self._variables.update(kwargs)
        return self

    def set_gene_list(
        self, genes: list[str], variable_name: str = "gene_list"
    ) -> "PromptBuilder":
        """Set a gene list variable.

        Args:
            genes: List of gene symbols
            variable_name: Variable name in template

        Returns:
            Self for chaining
        """
        self._variables[variable_name] = ", ".join(genes)
        return self

    def set_deg_results(
        self,
        upregulated: Sequence[DEGene],
        downregulated: Sequence[DEGene],
        top_n: int = 10,
    ) -> "PromptBuilder":
        """Set DEG results from gene lists with fold changes and, ideally, significance.

        Args:
            upregulated: (gene, log2fc) or (gene, log2fc, adjusted_p_value) entries
            downregulated: same shape
            top_n: Number of top genes to include

        The adjusted p-value is optional in the type but not in the science. The
        request schema has always accepted `adjustedPValue`, and the route has always
        thrown it away before it reached here — so the prompt listed bare fold
        changes, and a model shown a 2-fold change with no significance attached will
        read it as a finding. Where significance is absent this now says so in the
        prompt rather than letting silence imply it was checked.

        Returns:
            Self for chaining
        """
        up_str = "\n".join(_format_gene(entry) for entry in upregulated[:top_n])
        down_str = "\n".join(_format_gene(entry) for entry in downregulated[:top_n])

        self._variables["upregulated_genes"] = up_str
        self._variables["downregulated_genes"] = down_str
        self._variables["deg_count"] = len(upregulated) + len(downregulated)

        if not _has_significance(upregulated) and not _has_significance(downregulated):
            existing = self._variables.get("additional_context", "")
            self._variables["additional_context"] = existing + (
                "\nNOTE: No adjusted p-values were supplied with these genes. Fold "
                "change alone does not establish that a gene is differentially "
                "expressed. Treat the ranking as unfiltered and do not describe any "
                "gene as significantly changed."
            )

        # Inject signal strength note for weak/moderate signals
        all_fcs = [abs(_fc(e)) for e in upregulated] + [abs(_fc(e)) for e in downregulated]
        max_fc = max(all_fcs) if all_fcs else 0.0
        housekeeping = {"ACTB", "GAPDH", "TUBB", "B2M", "RPLP0"}
        all_genes = {_symbol(e) for e in upregulated} | {_symbol(e) for e in downregulated}
        has_housekeeping = bool(all_genes & housekeeping)

        if max_fc < 1.5 and has_housekeeping:
            signal_note = (
                f"\nNOTE: Maximum fold change is {max_fc:.1f}. "
                "Housekeeping genes detected in the list. "
                "Apply weak/moderate signal interpretation guidelines."
            )
            existing_context = self._variables.get("additional_context", "")
            self._variables["additional_context"] = existing_context + signal_note

        return self

    def set_pathway_results(
        self, pathways: list[dict[str, Any]], top_n: int = 10
    ) -> "PromptBuilder":
        """Set pathway enrichment results.

        Args:
            pathways: List of pathway dicts with name, pvalue, genes
            top_n: Number of top pathways to include

        Returns:
            Self for chaining
        """
        # Prefer the adjusted p-value. Enrichment tests thousands of gene sets, so a
        # nominal p-value is the one number that must not stand alone here — and it
        # was the only one being shown, while `adjusted_p_value` was available on the
        # same dict and dropped.
        def _pathway_significance(p: dict[str, Any]) -> str:
            adjusted = p.get("adjusted_p_value")
            if adjusted is not None:
                return f"adj. p: {adjusted:.2e}"
            nominal = p.get("p_value")
            if nominal is not None:
                return f"nominal p: {nominal:.2e} (UNADJUSTED — not corrected for multiple testing)"
            return "significance: not provided"

        pathway_str = "\n".join(
            [
                f"- {p['name']} ({_pathway_significance(p)}, "
                f"genes: {p.get('gene_count', 'N/A')})"
                for p in pathways[:top_n]
            ]
        )
        self._variables["enriched_pathways"] = pathway_str
        return self

    def set_context(self, context: str) -> "PromptBuilder":
        """Set additional context.

        Args:
            context: Context string

        Returns:
            Self for chaining
        """
        self._variables["additional_context"] = f"\nAdditional context: {context}"
        return self

    def validate(self) -> tuple[bool, list[str]]:
        """Validate that required variables are set.

        Returns:
            Tuple of (is_valid, missing_variables)
        """
        return self._template.validate_variables(**self._variables)

    def build(self) -> tuple[str, str]:
        """Build the final prompts.

        Returns:
            Tuple of (system_prompt, user_prompt)

        Raises:
            ValueError: If required variables are missing
        """
        is_valid, missing = self.validate()
        if not is_valid:
            raise ValueError(f"Missing required variables: {missing}")

        # Set defaults for optional variables
        if "additional_context" not in self._variables:
            self._variables["additional_context"] = ""
        if "organism" not in self._variables:
            self._variables["organism"] = "human"
        if "pvalue_threshold" not in self._variables:
            self._variables["pvalue_threshold"] = "0.05"
        if "logfc_threshold" not in self._variables:
            self._variables["logfc_threshold"] = "1.0"

        return self._template.render(**self._variables)

    def get_recommended_tools(self) -> list[str]:
        """Get tools recommended for this template.

        Returns:
            List of tool names
        """
        return self._template.recommended_tools
