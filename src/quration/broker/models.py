"""
Data models for the Method Broker system.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MethodCategory(str, Enum):
    """Categories of analysis methods."""

    VARIANT_CALLING = "variant_calling"
    RNA_SEQ = "rna_seq"
    CHIP_SEQ = "chip_seq"
    ATAC_SEQ = "atac_seq"
    METHYLATION = "methylation"
    SINGLE_CELL = "single_cell"
    METAGENOMICS = "metagenomics"
    QUALITY_CONTROL = "quality_control"
    ALIGNMENT = "alignment"
    ASSEMBLY = "assembly"
    DIFFERENTIAL_EXPRESSION = "differential_expression"
    PATHWAY_ANALYSIS = "pathway_analysis"
    CUSTOM = "custom"


class DataModality(str, Enum):
    """Types of sequencing data modalities."""

    DNA_SEQ = "dna_seq"
    RNA_SEQ = "rna_seq"
    CHIP_SEQ = "chip_seq"
    ATAC_SEQ = "atac_seq"
    BISULFITE_SEQ = "bisulfite_seq"
    SINGLE_CELL_RNA = "single_cell_rna"
    SINGLE_CELL_ATAC = "single_cell_atac"
    METAGENOMICS = "metagenomics"
    METATRANSCRIPTOMICS = "metatranscriptomics"
    UNKNOWN = "unknown"


class MethodInputSpec(BaseModel):
    """Specification of inputs required by a method."""

    name: str = Field(description="Input parameter name")
    description: str = Field(description="Description of the input")
    data_type: str = Field(description="Expected data type (e.g., 'FASTQ', 'BAM', 'VCF')")
    required: bool = Field(default=True, description="Whether this input is required")
    multiple: bool = Field(default=False, description="Whether multiple files are accepted")
    example: Optional[str] = Field(default=None, description="Example value or file path")


class MethodOutputSpec(BaseModel):
    """Specification of outputs produced by a method."""

    name: str = Field(description="Output name")
    description: str = Field(description="Description of the output")
    data_type: str = Field(description="Output data type")
    file_pattern: Optional[str] = Field(default=None, description="File naming pattern")


class MethodAssumption(BaseModel):
    """Assumptions and prerequisites for a method."""

    description: str = Field(description="Description of the assumption")
    category: str = Field(description="Category (e.g., 'data_quality', 'experimental_design')")
    critical: bool = Field(default=False, description="Whether this is a critical assumption")


class MethodCaveat(BaseModel):
    """Caveats and limitations of a method."""

    description: str = Field(description="Description of the caveat")
    severity: str = Field(description="Severity level (low, medium, high)")
    workaround: Optional[str] = Field(default=None, description="Possible workaround")


class MethodQualityMetrics(BaseModel):
    """Quality metrics for a method."""

    reproducibility_score: float = Field(
        ge=0.0, le=1.0, description="Reproducibility score (0-1)"
    )
    code_availability: bool = Field(description="Whether code is publicly available")
    documentation_quality: float = Field(
        ge=0.0, le=1.0, description="Documentation quality score (0-1)"
    )
    peer_reviewed: bool = Field(default=False, description="Whether method is peer-reviewed")
    citation_count: int = Field(default=0, description="Number of citations")
    last_updated: Optional[datetime] = Field(
        default=None, description="Last update date"
    )
    community_rating: Optional[float] = Field(
        default=None, ge=0.0, le=5.0, description="Community rating (0-5)"
    )


class AnalysisMethod(BaseModel):
    """
    Represents an analysis method or pipeline in the registry.
    """

    id: str = Field(description="Unique identifier for the method")
    name: str = Field(description="Human-readable name")
    category: MethodCategory = Field(description="Method category")
    description: str = Field(description="Detailed description of the method")

    # Technical specifications
    implementation_type: str = Field(
        description="Type of implementation (e.g., 'nextflow', 'snakemake', 'script', 'tool')"
    )
    version: str = Field(description="Version of the method")
    repository_url: Optional[str] = Field(default=None, description="Code repository URL")
    documentation_url: Optional[str] = Field(default=None, description="Documentation URL")

    # Input/Output specifications
    inputs: List[MethodInputSpec] = Field(description="Input specifications")
    outputs: List[MethodOutputSpec] = Field(description="Output specifications")

    # Requirements and constraints
    supported_modalities: List[DataModality] = Field(
        description="Supported data modalities"
    )
    supported_organisms: Optional[List[str]] = Field(
        default=None, description="Supported organisms (e.g., 'human', 'mouse')"
    )
    min_samples: Optional[int] = Field(
        default=None, description="Minimum number of samples required"
    )
    max_samples: Optional[int] = Field(
        default=None, description="Maximum number of samples (for scalability)"
    )

    # Assumptions and caveats
    assumptions: List[MethodAssumption] = Field(
        default_factory=list, description="Method assumptions"
    )
    caveats: List[MethodCaveat] = Field(
        default_factory=list, description="Method caveats"
    )

    # Quality metrics
    quality_metrics: MethodQualityMetrics = Field(
        description="Quality and reliability metrics"
    )

    # Computational requirements
    compute_requirements: Dict[str, Any] = Field(
        default_factory=dict,
        description="Computational requirements (CPU, memory, storage)"
    )

    # Runtime estimates
    estimated_runtime: Optional[str] = Field(
        default=None,
        description="Estimated runtime (e.g., '2 hours for 10 samples')"
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = Field(default="system")
    tags: List[str] = Field(default_factory=list, description="Searchable tags")

    # Status
    status: str = Field(
        default="active",
        description="Method status (active, deprecated, experimental)"
    )

    # References
    publications: List[str] = Field(
        default_factory=list,
        description="Related publication DOIs or PMIDs"
    )


class ParsedRequest(BaseModel):
    """
    Structured representation of a user's analysis request after LLM parsing.
    """

    original_query: str = Field(description="Original user query")

    # Identified requirements
    data_modality: DataModality = Field(description="Identified data modality")
    analysis_type: str = Field(description="Type of analysis requested")
    specific_tools: List[str] = Field(
        default_factory=list,
        description="Specific tools or methods mentioned"
    )

    # Context
    organism: Optional[str] = Field(default=None, description="Target organism")
    sample_count: Optional[int] = Field(default=None, description="Number of samples")
    experimental_design: Optional[str] = Field(
        default=None, description="Experimental design type"
    )

    # Constraints
    constraints: Dict[str, Any] = Field(
        default_factory=dict,
        description="User-specified constraints (e.g., runtime, resources)"
    )

    # Preferences
    preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description="User preferences (e.g., prefer published methods)"
    )

    # Extracted entities
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")

    # Confidence
    confidence: float = Field(
        ge=0.0, le=1.0, description="Parser confidence in the interpretation"
    )

    # Metadata
    parsed_at: datetime = Field(default_factory=datetime.now)


class MatchResult(BaseModel):
    """
    Result of matching a request to a method.
    """

    method: AnalysisMethod = Field(description="Matched method")
    score: float = Field(ge=0.0, le=1.0, description="Match score (0-1)")

    # Score breakdown
    relevance_score: float = Field(ge=0.0, le=1.0, description="Relevance to request")
    quality_score: float = Field(ge=0.0, le=1.0, description="Method quality score")
    compatibility_score: float = Field(
        ge=0.0, le=1.0, description="Compatibility with requirements"
    )

    # Explanation
    match_reasons: List[str] = Field(
        description="Reasons why this method matches"
    )
    potential_issues: List[str] = Field(
        default_factory=list,
        description="Potential issues or concerns"
    )

    # Recommendations
    recommended: bool = Field(description="Whether this method is recommended")
    rank: int = Field(description="Rank among all matches")


class MethodRequest(BaseModel):
    """
    Request to execute a method or get method recommendations.
    """

    query: str = Field(description="Natural language description of the analysis need")

    # Optional structured parameters
    data_modality: Optional[DataModality] = Field(
        default=None, description="Known data modality"
    )
    sample_metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Sample metadata"
    )

    # Execution parameters
    execute: bool = Field(
        default=False,
        description="Whether to execute the top method or just return recommendations"
    )
    max_recommendations: int = Field(
        default=5, description="Maximum number of method recommendations"
    )

    # Preferences
    prefer_published: bool = Field(
        default=True, description="Prefer peer-reviewed methods"
    )
    prefer_reproducible: bool = Field(
        default=True, description="Prefer highly reproducible methods"
    )
    min_quality_score: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum acceptable quality score"
    )

    # Context
    conversation_id: Optional[str] = Field(
        default=None, description="Conversation ID for context"
    )

    # User info
    user_id: Optional[str] = Field(default=None, description="User identifier")


class MethodResponse(BaseModel):
    """
    Response containing method recommendations or execution results.
    """

    request: MethodRequest = Field(description="Original request")
    parsed_request: ParsedRequest = Field(description="Parsed request structure")

    # Recommendations
    matches: List[MatchResult] = Field(description="Matched methods, ranked by score")

    # Execution results (if executed)
    execution_result: Optional[Dict[str, Any]] = Field(
        default=None, description="Results if method was executed"
    )

    # Metadata
    processing_time_ms: float = Field(description="Processing time in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.now)


class MethodProposal(BaseModel):
    """
    User proposal for a new method to be added to the registry.
    """

    # Basic info
    name: str = Field(description="Proposed method name")
    category: MethodCategory = Field(description="Method category")
    description: str = Field(description="Detailed description")

    # Why is this needed?
    justification: str = Field(
        description="Why this method should be added to the registry"
    )
    use_cases: List[str] = Field(
        description="Specific use cases this method addresses"
    )

    # Technical details (optional)
    repository_url: Optional[str] = Field(default=None, description="Code repository")
    documentation_url: Optional[str] = Field(default=None, description="Documentation")
    publications: List[str] = Field(
        default_factory=list, description="Related publications"
    )

    # Comparison with existing methods
    advantages_over_existing: Optional[str] = Field(
        default=None,
        description="Advantages over existing methods in the registry"
    )

    # Metadata
    proposed_by: str = Field(description="User who proposed this method")
    proposed_at: datetime = Field(default_factory=datetime.now)
    status: str = Field(
        default="pending", description="Proposal status (pending, approved, rejected)"
    )
    review_notes: Optional[str] = Field(
        default=None, description="Review notes from administrators"
    )
