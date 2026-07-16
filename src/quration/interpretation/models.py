"""
Data models for the Interpretation system.

These models define the structure for LLM-powered interpretation of
bioinformatics analysis results, including tool call tracking,
claim attribution, and confidence scoring.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class InterpretationType(str, Enum):
    """Types of interpretation analysis."""

    DEG_ANALYSIS = "deg_analysis"
    BATCH_EFFECT = "batch_effect"
    PATHWAY_ENRICHMENT = "pathway_enrichment"
    GENE_FUNCTION = "gene_function"
    QC_ASSESSMENT = "qc_assessment"
    LITERATURE_REVIEW = "literature_review"
    CUSTOM = "custom"


class ClaimType(str, Enum):
    """Types of claims in an interpretation."""

    FROM_DATA = "from_data"  # Directly derived from input data
    INFERENCE = "inference"  # Inferred by the LLM
    LITERATURE = "literature"  # Supported by literature
    TOOL_RESULT = "tool_result"  # From external tool/database


class ConfidenceLevel(str, Enum):
    """Confidence levels for interpretation claims."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ToolCallStatus(str, Enum):
    """Status of a tool call."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    CACHED = "cached"


class ToolCallRecord(BaseModel):
    """Record of a tool call made during interpretation."""

    tool_name: str = Field(description="Name of the tool called")
    tool_input: dict[str, Any] = Field(
        description="Input parameters passed to the tool"
    )
    tool_output: dict[str, Any] | None = Field(
        default=None, description="Output returned by the tool"
    )
    status: ToolCallStatus = Field(description="Status of the tool call")
    error_message: str | None = Field(
        default=None, description="Error message if call failed"
    )
    latency_ms: float = Field(description="Tool call latency in milliseconds")
    cached: bool = Field(default=False, description="Whether result was from cache")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When the tool was called"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class EvidenceSource(BaseModel):
    """Source of evidence for a claim."""

    source_type: str = Field(
        description="Type of source (e.g., 'pubmed', 'uniprot', 'kegg', 'data')"
    )
    source_id: str | None = Field(
        default=None, description="Identifier (e.g., PMID, UniProt ID)"
    )
    source_url: str | None = Field(default=None, description="URL to the source")
    description: str = Field(description="Description of the evidence")
    tool_call_index: int | None = Field(
        default=None, description="Index of the tool call that provided this evidence"
    )


class InterpretationClaim(BaseModel):
    """A single claim within an interpretation."""

    claim_type: ClaimType = Field(description="Type of claim")
    statement: str = Field(description="The claim statement")
    evidence: list[EvidenceSource] = Field(
        default_factory=list, description="Evidence supporting the claim"
    )
    source_tool: str | None = Field(
        default=None, description="Tool that provided data for this claim"
    )
    confidence: ConfidenceLevel = Field(description="Confidence level of the claim")
    genes_mentioned: list[str] = Field(
        default_factory=list, description="Gene symbols mentioned in the claim"
    )
    pathways_mentioned: list[str] = Field(
        default_factory=list, description="Pathway IDs mentioned in the claim"
    )


class TokenUsage(BaseModel):
    """Token usage tracking for LLM calls."""

    input_tokens: int = Field(default=0, description="Input tokens used")
    output_tokens: int = Field(default=0, description="Output tokens generated")
    cache_read_tokens: int = Field(default=0, description="Tokens read from cache")
    cache_write_tokens: int = Field(default=0, description="Tokens written to cache")

    @property
    def total_tokens(self) -> int:
        """Total tokens used."""
        return self.input_tokens + self.output_tokens


class InterpretationResult(BaseModel):
    """Result of an interpretation analysis."""

    id: UUID = Field(default_factory=uuid4, description="Unique identifier")
    interpretation_type: InterpretationType = Field(
        description="Type of interpretation performed"
    )
    summary: str = Field(description="Executive summary of the interpretation")
    claims: list[InterpretationClaim] = Field(
        default_factory=list, description="Individual claims with evidence"
    )
    tool_calls: list[ToolCallRecord] = Field(
        default_factory=list, description="Tools called during interpretation"
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Questions that could not be answered or need follow-up",
    )
    limitations: list[str] = Field(
        default_factory=list, description="Limitations of this interpretation"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Recommended next steps"
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0, description="Overall confidence score (0-1)"
    )
    token_usage: TokenUsage = Field(
        default_factory=TokenUsage, description="Token usage statistics"
    )
    cost_usd: float = Field(default=0.0, ge=0.0, description="Estimated cost in USD")
    model_used: str = Field(description="LLM model used for interpretation")
    processing_time_ms: float = Field(
        description="Total processing time in milliseconds"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="When interpretation was created"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat(), UUID: str}


class InterpretationRequest(BaseModel):
    """Request for an interpretation analysis."""

    interpretation_type: InterpretationType = Field(
        description="Type of interpretation requested"
    )
    input_data: dict[str, Any] = Field(description="Input data for interpretation")
    experimental_context: str | None = Field(
        default=None, description="Context about the experiment"
    )
    organism: str = Field(default="human", description="Target organism")
    user_question: str | None = Field(
        default=None, description="Specific question from the user"
    )
    max_tool_calls: int = Field(
        default=10, ge=1, le=50, description="Maximum number of tool calls allowed"
    )
    include_literature: bool = Field(
        default=True, description="Whether to search literature"
    )
    user_id: UUID | None = Field(default=None, description="User making the request")
    conversation_id: UUID | None = Field(
        default=None, description="Associated conversation ID"
    )

    class Config:
        json_encoders = {UUID: str}


# Specialized result types for different interpretation types


class DEGInterpretationResult(InterpretationResult):
    """Result specifically for DEG interpretation."""

    interpretation_type: InterpretationType = Field(
        default=InterpretationType.DEG_ANALYSIS
    )
    top_upregulated: list[str] = Field(
        default_factory=list, description="Top upregulated genes"
    )
    top_downregulated: list[str] = Field(
        default_factory=list, description="Top downregulated genes"
    )
    enriched_pathways: list[dict[str, Any]] = Field(
        default_factory=list, description="Enriched pathways identified"
    )
    biological_themes: list[str] = Field(
        default_factory=list, description="Major biological themes"
    )


class BatchEffectInterpretation(InterpretationResult):
    """Result specifically for batch effect interpretation."""

    interpretation_type: InterpretationType = Field(
        default=InterpretationType.BATCH_EFFECT
    )
    batch_variables_identified: list[str] = Field(
        default_factory=list, description="Variables correlated with batch"
    )
    severity: str = Field(
        default="unknown", description="Severity of batch effect (none/low/medium/high)"
    )
    confounding_detected: bool = Field(
        default=False, description="Whether batch is confounded with treatment"
    )
    correction_recommended: bool = Field(
        default=False, description="Whether batch correction is recommended"
    )
    recommended_method: str | None = Field(
        default=None, description="Recommended correction method"
    )


class PathwayInterpretation(InterpretationResult):
    """Result specifically for pathway enrichment interpretation."""

    interpretation_type: InterpretationType = Field(
        default=InterpretationType.PATHWAY_ENRICHMENT
    )
    top_pathways: list[dict[str, Any]] = Field(
        default_factory=list, description="Top enriched pathways with details"
    )
    biological_themes: list[str] = Field(
        default_factory=list, description="Overarching biological themes"
    )
    leading_edge_genes: dict[str, list[str]] = Field(
        default_factory=dict, description="Leading edge genes per pathway"
    )


class GeneFunctionInterpretation(InterpretationResult):
    """Result specifically for gene function interpretation."""

    interpretation_type: InterpretationType = Field(
        default=InterpretationType.GENE_FUNCTION
    )
    gene_summaries: dict[str, str] = Field(
        default_factory=dict, description="Summary for each gene"
    )
    interaction_network: dict[str, list[str]] = Field(
        default_factory=dict, description="Gene interaction network"
    )
    functional_categories: dict[str, list[str]] = Field(
        default_factory=dict, description="Genes grouped by function"
    )


class QCInterpretation(InterpretationResult):
    """Result specifically for QC assessment interpretation."""

    interpretation_type: InterpretationType = Field(
        default=InterpretationType.QC_ASSESSMENT
    )
    overall_quality: str = Field(
        default="unknown", description="Overall quality (good/acceptable/poor)"
    )
    problematic_samples: list[str] = Field(
        default_factory=list, description="Samples with quality issues"
    )
    quality_metrics: dict[str, Any] = Field(
        default_factory=dict, description="Key quality metrics"
    )
    recommended_actions: list[str] = Field(
        default_factory=list, description="Recommended actions for issues"
    )
