"""Pydantic schemas for interpretation API endpoints."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class GeneExpressionItem(BaseModel):
    """Gene expression data item."""

    gene_symbol: str = Field(..., alias="geneSymbol", description="Gene symbol")
    log2_fold_change: float = Field(..., alias="log2FoldChange", description="Log2 fold change")
    p_value: float | None = Field(None, alias="pValue", description="P-value (optional)")
    adjusted_p_value: float | None = Field(
        None, alias="adjustedPValue", description="Adjusted p-value (optional)"
    )

    class Config:
        populate_by_name = True


class PathwayEnrichmentItem(BaseModel):
    """Pathway enrichment result item."""

    pathway_name: str = Field(..., alias="pathwayName", description="Pathway name")
    pathway_id: str | None = Field(None, alias="pathwayId", description="Pathway ID")
    p_value: float = Field(..., alias="pValue", description="P-value")
    adjusted_p_value: float | None = Field(None, alias="adjustedPValue", description="Adjusted p-value")
    gene_count: int = Field(..., alias="geneCount", description="Number of genes in pathway")
    genes: list[str] = Field(default_factory=list, description="Gene symbols in pathway")

    class Config:
        populate_by_name = True


class ToolCallSummary(BaseModel):
    """Summary of a tool call for API response."""

    tool_name: str = Field(..., alias="toolName", description="Name of the tool")
    status: str = Field(..., description="Status (success, failure, timeout, cached)")
    latency_ms: float = Field(..., alias="latencyMs", description="Latency in milliseconds")
    cached: bool = Field(default=False, description="Whether result was cached")

    class Config:
        populate_by_name = True


class ClaimResponse(BaseModel):
    """A claim in the interpretation response."""

    claim_type: str = Field(..., alias="claimType", description="Type of claim")
    statement: str = Field(..., description="The claim statement")
    confidence: str = Field(..., description="Confidence level (high, medium, low)")
    genes_mentioned: list[str] = Field(
        default_factory=list, alias="genesMentioned", description="Genes mentioned"
    )
    pathways_mentioned: list[str] = Field(
        default_factory=list, alias="pathwaysMentioned", description="Pathways mentioned"
    )
    evidence_count: int = Field(default=0, alias="evidenceCount", description="Number of evidence sources")

    class Config:
        populate_by_name = True


class TokenUsageResponse(BaseModel):
    """Token usage statistics."""

    input_tokens: int = Field(..., alias="inputTokens", description="Input tokens used")
    output_tokens: int = Field(..., alias="outputTokens", description="Output tokens generated")
    total_tokens: int = Field(..., alias="totalTokens", description="Total tokens used")

    class Config:
        populate_by_name = True


# ============================================================================
# DEG Interpretation
# ============================================================================


class InterpretDEGRequest(BaseModel):
    """Request for differential expression interpretation."""

    upregulated_genes: list[GeneExpressionItem] = Field(
        ...,
        alias="upregulatedGenes",
        description="Upregulated genes with fold changes",
        min_length=1,
    )
    downregulated_genes: list[GeneExpressionItem] = Field(
        default_factory=list,
        alias="downregulatedGenes",
        description="Downregulated genes with fold changes",
    )
    condition_a: str = Field(..., alias="conditionA", description="First condition name")
    condition_b: str = Field(..., alias="conditionB", description="Second condition name")
    experiment_type: str = Field(
        default="RNA-seq", alias="experimentType", description="Type of experiment"
    )
    organism: str = Field(default="human", description="Organism")
    additional_context: str | None = Field(
        None, alias="additionalContext", description="Additional context"
    )
    max_tool_iterations: int = Field(
        default=10,
        alias="maxToolIterations",
        ge=1,
        le=50,
        description="Maximum tool call iterations",
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "upregulatedGenes": [
                    {"geneSymbol": "TP53", "log2FoldChange": 2.5, "pValue": 0.001},
                    {"geneSymbol": "BRCA1", "log2FoldChange": 1.8, "pValue": 0.005},
                ],
                "downregulatedGenes": [
                    {"geneSymbol": "MYC", "log2FoldChange": -2.1, "pValue": 0.002}
                ],
                "conditionA": "treated",
                "conditionB": "control",
                "experimentType": "RNA-seq",
                "organism": "human",
                "additionalContext": "Cancer cell line study",
            }
        }


class InterpretDEGResponse(BaseModel):
    """Response for differential expression interpretation."""

    id: str = Field(..., description="Interpretation ID")
    summary: str = Field(..., description="Executive summary")
    claims: list[ClaimResponse] = Field(
        default_factory=list, description="Extracted claims"
    )
    tool_calls: list[ToolCallSummary] = Field(
        default_factory=list, alias="toolCalls", description="Tool calls made"
    )
    open_questions: list[str] = Field(
        default_factory=list, alias="openQuestions", description="Open questions"
    )
    limitations: list[str] = Field(default_factory=list, description="Limitations")
    recommendations: list[str] = Field(default_factory=list, description="Recommendations")
    confidence_score: float = Field(
        ..., alias="confidenceScore", ge=0.0, le=1.0, description="Overall confidence"
    )
    token_usage: TokenUsageResponse = Field(..., alias="tokenUsage")
    cost_usd: float = Field(..., alias="costUsd", ge=0.0, description="Estimated cost")
    processing_time_ms: float = Field(
        ..., alias="processingTimeMs", description="Processing time"
    )
    model_used: str = Field(..., alias="modelUsed", description="Model used")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "id": "interp-123",
                "summary": "The analysis reveals significant upregulation of tumor suppressor genes...",
                "claims": [
                    {
                        "claimType": "from_data",
                        "statement": "TP53 is significantly upregulated (2.5 log2FC)",
                        "confidence": "high",
                        "genesMentioned": ["TP53"],
                        "pathwaysMentioned": [],
                        "evidenceCount": 3,
                    }
                ],
                "toolCalls": [
                    {"toolName": "get_gene_info", "status": "success", "latencyMs": 150.5, "cached": False}
                ],
                "openQuestions": ["What is the mechanism of TP53 activation?"],
                "limitations": ["Analysis limited to top 50 genes"],
                "recommendations": ["Validate with qPCR"],
                "confidenceScore": 0.85,
                "tokenUsage": {"inputTokens": 1500, "outputTokens": 800, "totalTokens": 2300},
                "costUsd": 0.05,
                "processingTimeMs": 5000.0,
                "modelUsed": "claude-sonnet-4-20250514",
            }
        }


# ============================================================================
# Pathway Enrichment Interpretation
# ============================================================================


class InterpretPathwayRequest(BaseModel):
    """Request for pathway enrichment interpretation."""

    pathways: list[PathwayEnrichmentItem] = Field(
        ..., description="Enriched pathways", min_length=1
    )
    experiment_context: str = Field(
        ..., alias="experimentContext", description="Experiment context"
    )
    gene_set_size: int | None = Field(
        None, alias="geneSetSize", description="Total genes analyzed"
    )
    max_tool_iterations: int = Field(
        default=10, alias="maxToolIterations", ge=1, le=50
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "pathways": [
                    {
                        "pathwayName": "p53 signaling pathway",
                        "pathwayId": "hsa04115",
                        "pValue": 0.0001,
                        "geneCount": 15,
                        "genes": ["TP53", "MDM2", "CDKN1A"],
                    }
                ],
                "experimentContext": "Differential expression in treated vs control",
                "geneSetSize": 500,
            }
        }


class InterpretPathwayResponse(BaseModel):
    """Response for pathway enrichment interpretation."""

    id: str = Field(..., description="Interpretation ID")
    summary: str = Field(..., description="Executive summary")
    claims: list[ClaimResponse] = Field(default_factory=list)
    tool_calls: list[ToolCallSummary] = Field(default_factory=list, alias="toolCalls")
    biological_themes: list[str] = Field(
        default_factory=list, alias="biologicalThemes", description="Key biological themes"
    )
    confidence_score: float = Field(..., alias="confidenceScore", ge=0.0, le=1.0)
    token_usage: TokenUsageResponse = Field(..., alias="tokenUsage")
    cost_usd: float = Field(..., alias="costUsd", ge=0.0)
    processing_time_ms: float = Field(..., alias="processingTimeMs")
    model_used: str = Field(..., alias="modelUsed")

    class Config:
        populate_by_name = True


# ============================================================================
# Gene Function Analysis
# ============================================================================


class AnalyzeGeneFunctionRequest(BaseModel):
    """Request for gene function analysis."""

    genes: list[str] = Field(
        ..., description="Gene symbols to analyze", min_length=1, max_length=50
    )
    analysis_context: str | None = Field(
        None, alias="analysisContext", description="Context for analysis"
    )
    max_tool_iterations: int = Field(
        default=10, alias="maxToolIterations", ge=1, le=50
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "genes": ["TP53", "BRCA1", "MYC"],
                "analysisContext": "Cancer-related gene set analysis",
            }
        }


class AnalyzeGeneFunctionResponse(BaseModel):
    """Response for gene function analysis."""

    id: str = Field(..., description="Interpretation ID")
    summary: str = Field(..., description="Executive summary")
    claims: list[ClaimResponse] = Field(default_factory=list)
    tool_calls: list[ToolCallSummary] = Field(default_factory=list, alias="toolCalls")
    gene_summaries: dict[str, str] = Field(
        default_factory=dict, alias="geneSummaries", description="Summary per gene"
    )
    confidence_score: float = Field(..., alias="confidenceScore", ge=0.0, le=1.0)
    token_usage: TokenUsageResponse = Field(..., alias="tokenUsage")
    cost_usd: float = Field(..., alias="costUsd", ge=0.0)
    processing_time_ms: float = Field(..., alias="processingTimeMs")
    model_used: str = Field(..., alias="modelUsed")

    class Config:
        populate_by_name = True


# ============================================================================
# Batch Effect Assessment
# ============================================================================


class AssessBatchEffectsRequest(BaseModel):
    """Request for batch effect assessment."""

    batch_count: int = Field(..., alias="batchCount", ge=2, description="Number of batches")
    batch_metrics: str = Field(
        ..., alias="batchMetrics", description="Description of batch effect metrics"
    )
    samples_per_batch: str | None = Field(
        None, alias="samplesPerBatch", description="Sample distribution"
    )
    pca_summary: str | None = Field(
        None, alias="pcaSummary", description="PCA analysis summary"
    )
    max_tool_iterations: int = Field(
        default=5, alias="maxToolIterations", ge=1, le=50
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "batchCount": 3,
                "batchMetrics": "PC1 variance explained: 45%, batch correlation: 0.65",
                "samplesPerBatch": "Batch1: 10, Batch2: 12, Batch3: 8",
                "pcaSummary": "First two PCs separate samples primarily by batch",
            }
        }


class AssessBatchEffectsResponse(BaseModel):
    """Response for batch effect assessment."""

    id: str = Field(..., description="Interpretation ID")
    summary: str = Field(..., description="Executive summary")
    claims: list[ClaimResponse] = Field(default_factory=list)
    tool_calls: list[ToolCallSummary] = Field(default_factory=list, alias="toolCalls")
    severity: str = Field(
        default="unknown", description="Severity (none, low, medium, high)"
    )
    correction_recommended: bool = Field(
        default=False, alias="correctionRecommended"
    )
    recommended_method: str | None = Field(None, alias="recommendedMethod")
    confidence_score: float = Field(..., alias="confidenceScore", ge=0.0, le=1.0)
    token_usage: TokenUsageResponse = Field(..., alias="tokenUsage")
    cost_usd: float = Field(..., alias="costUsd", ge=0.0)
    processing_time_ms: float = Field(..., alias="processingTimeMs")
    model_used: str = Field(..., alias="modelUsed")

    class Config:
        populate_by_name = True


# ============================================================================
# Literature Review
# ============================================================================


class ReviewLiteratureRequest(BaseModel):
    """Request for literature review."""

    topic: str = Field(..., description="Topic to review", min_length=3)
    focus_areas: str | None = Field(
        None, alias="focusAreas", description="Specific areas to focus on"
    )
    research_context: str | None = Field(
        None, alias="researchContext", description="Research context"
    )
    max_tool_iterations: int = Field(
        default=8, alias="maxToolIterations", ge=1, le=50
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "topic": "TP53 mutations in breast cancer",
                "focusAreas": "Drug resistance mechanisms",
                "researchContext": "Developing targeted therapies",
            }
        }


class ReviewLiteratureResponse(BaseModel):
    """Response for literature review."""

    id: str = Field(..., description="Interpretation ID")
    summary: str = Field(..., description="Executive summary")
    claims: list[ClaimResponse] = Field(default_factory=list)
    tool_calls: list[ToolCallSummary] = Field(default_factory=list, alias="toolCalls")
    key_findings: list[str] = Field(
        default_factory=list, alias="keyFindings", description="Key findings"
    )
    bibliography: str = Field(default="", description="Formatted bibliography")
    confidence_score: float = Field(..., alias="confidenceScore", ge=0.0, le=1.0)
    token_usage: TokenUsageResponse = Field(..., alias="tokenUsage")
    cost_usd: float = Field(..., alias="costUsd", ge=0.0)
    processing_time_ms: float = Field(..., alias="processingTimeMs")
    model_used: str = Field(..., alias="modelUsed")

    class Config:
        populate_by_name = True


# ============================================================================
# Custom Interpretation
# ============================================================================


class CustomInterpretationRequest(BaseModel):
    """Request for custom interpretation."""

    prompt: str = Field(..., description="Custom interpretation prompt", min_length=10)
    system_prompt: str | None = Field(
        None, alias="systemPrompt", description="Custom system prompt"
    )
    context: dict[str, Any] | None = Field(
        None, description="Additional context data"
    )
    max_tool_iterations: int = Field(
        default=10, alias="maxToolIterations", ge=1, le=50
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "prompt": "Analyze the relationship between these genes in the context of EMT...",
                "systemPrompt": "You are a bioinformatics expert...",
                "context": {"genes": ["CDH1", "VIM", "SNAI1"]},
            }
        }


class CustomInterpretationResponse(BaseModel):
    """Response for custom interpretation."""

    id: str = Field(..., description="Interpretation ID")
    summary: str = Field(..., description="Executive summary")
    claims: list[ClaimResponse] = Field(default_factory=list)
    tool_calls: list[ToolCallSummary] = Field(default_factory=list, alias="toolCalls")
    full_response: str = Field(
        default="", alias="fullResponse", description="Full interpretation text"
    )
    confidence_score: float = Field(..., alias="confidenceScore", ge=0.0, le=1.0)
    token_usage: TokenUsageResponse = Field(..., alias="tokenUsage")
    cost_usd: float = Field(..., alias="costUsd", ge=0.0)
    processing_time_ms: float = Field(..., alias="processingTimeMs")
    model_used: str = Field(..., alias="modelUsed")

    class Config:
        populate_by_name = True


# ============================================================================
# Shared Response Types
# ============================================================================


class InterpretationStatusResponse(BaseModel):
    """Response for interpretation status check."""

    id: str = Field(..., description="Interpretation ID")
    status: str = Field(..., description="Status (pending, processing, completed, failed)")
    progress: float | None = Field(
        None, ge=0.0, le=1.0, description="Progress (0-1)"
    )
    tool_calls_completed: int | None = Field(
        None, alias="toolCallsCompleted", description="Tool calls completed"
    )
    estimated_time_remaining_ms: int | None = Field(
        None, alias="estimatedTimeRemainingMs", description="Estimated time remaining"
    )

    class Config:
        populate_by_name = True


class InterpretationErrorResponse(BaseModel):
    """Error response for interpretation failures."""

    error: str = Field(..., description="Error message")
    error_code: str = Field(..., alias="errorCode", description="Error code")
    details: dict[str, Any] | None = Field(None, description="Error details")
    interpretation_id: str | None = Field(
        None, alias="interpretationId", description="Interpretation ID if available"
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "error": "Tool execution failed",
                "errorCode": "TOOL_EXECUTION_ERROR",
                "details": {"tool": "get_gene_info", "reason": "API timeout"},
                "interpretationId": "interp-123",
            }
        }


class AvailableToolsResponse(BaseModel):
    """Response listing available interpretation tools."""

    tools: list[str] = Field(..., description="List of available tool names")
    tool_count: int = Field(..., alias="toolCount", description="Number of tools")

    class Config:
        populate_by_name = True


class InterpretationMetricsResponse(BaseModel):
    """Response with interpretation service metrics."""

    total_interpretations: int = Field(..., alias="totalInterpretations")
    successful_interpretations: int = Field(..., alias="successfulInterpretations")
    failed_interpretations: int = Field(..., alias="failedInterpretations")
    average_processing_time_ms: float = Field(..., alias="averageProcessingTimeMs")
    total_tool_calls: int = Field(..., alias="totalToolCalls")
    tool_success_rate: float = Field(..., alias="toolSuccessRate", ge=0.0, le=1.0)
    cache_hit_rate: float = Field(..., alias="cacheHitRate", ge=0.0, le=1.0)
    total_cost_usd: float = Field(..., alias="totalCostUsd", ge=0.0)

    class Config:
        populate_by_name = True
