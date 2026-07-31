"""API routes for bioinformatics data interpretation."""

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse

from quration.api.dependencies import get_current_user_id, get_optional_user_id
from quration.api.schemas.interpretation import (
    AnalyzeGeneFunctionRequest,
    AnalyzeGeneFunctionResponse,
    AssessBatchEffectsRequest,
    AssessBatchEffectsResponse,
    AvailableToolsResponse,
    ClaimResponse,
    CustomInterpretationRequest,
    CustomInterpretationResponse,
    InterpretationErrorResponse,
    InterpretationMetricsResponse,
    InterpretDEGRequest,
    InterpretDEGResponse,
    InterpretPathwayRequest,
    InterpretPathwayResponse,
    ReviewLiteratureRequest,
    ReviewLiteratureResponse,
    TokenUsageResponse,
    ToolCallSummary,
)
from quration.interpretation.models import InterpretationResult, ToolCallStatus
from quration.interpretation.service import InterpretationService, create_interpretation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/interpretations", tags=["Interpretation"])

# Service singleton (could be replaced with proper DI)
_interpretation_service: InterpretationService | None = None


def get_interpretation_service() -> InterpretationService:
    """Get or create the interpretation service.

    Returns:
        InterpretationService instance
    """
    global _interpretation_service
    if _interpretation_service is None:
        _interpretation_service = create_interpretation_service()
    return _interpretation_service


def _result_to_claims(result: InterpretationResult) -> list[ClaimResponse]:
    """Convert InterpretationResult claims to API response format."""
    return [
        ClaimResponse(
            claim_type=claim.claim_type.value,
            statement=claim.statement,
            confidence=claim.confidence.value,
            genes_mentioned=claim.genes_mentioned,
            pathways_mentioned=claim.pathways_mentioned,
            evidence_count=len(claim.evidence),
        )
        for claim in result.claims
    ]


def _result_to_tool_calls(result: InterpretationResult) -> list[ToolCallSummary]:
    """Convert InterpretationResult tool calls to API response format."""
    return [
        ToolCallSummary(
            tool_name=call.tool_name,
            status=call.status.value,
            latency_ms=call.latency_ms,
            cached=call.cached,
        )
        for call in result.tool_calls
    ]


def _result_to_token_usage(result: InterpretationResult) -> TokenUsageResponse:
    """Convert token usage to API response format."""
    return TokenUsageResponse(
        input_tokens=result.token_usage.input_tokens,
        output_tokens=result.token_usage.output_tokens,
        total_tokens=result.token_usage.total_tokens,
    )


@router.post(
    "/deg",
    response_model=InterpretDEGResponse,
    summary="Interpret differential expression results",
    description="Analyze DEG results with tool-augmented LLM interpretation",
    responses={
        500: {"model": InterpretationErrorResponse, "description": "Interpretation failed"},
    },
)
async def interpret_deg(
    request: InterpretDEGRequest,
    background_tasks: BackgroundTasks,
    user_id: UUID | None = Depends(get_optional_user_id),
    service: InterpretationService = Depends(get_interpretation_service),
) -> InterpretDEGResponse:
    """Interpret differential expression analysis results.

    This endpoint analyzes DEG results using:
    - Gene database lookups (NCBI Gene, UniProt)
    - Pathway enrichment (Reactome, KEGG)
    - Literature search (PubMed)
    - Protein interactions (STRING)

    Args:
        request: DEG interpretation request
        background_tasks: Background task runner
        user_id: Optional authenticated user ID
        service: Interpretation service

    Returns:
        Interpretation result with claims and evidence
    """
    try:
        # Convert request to service format
        # Carry the adjusted p-value through. The request schema has accepted
        # `adjustedPValue` all along and this conversion dropped it, so the UI
        # collected a number the backend could not use and the prompt listed bare
        # fold changes. Falls back to the nominal p-value only if that is all the
        # caller sent; None means "not provided", which the prompt states explicitly.
        def _entries(items):
            return [
                (
                    item.gene_symbol,
                    item.log2_fold_change,
                    item.adjusted_p_value if item.adjusted_p_value is not None else item.p_value,
                )
                for item in items
            ]

        upregulated = _entries(request.upregulated_genes)
        downregulated = _entries(request.downregulated_genes)

        # Run interpretation
        result = await service.interpret_deg_results(
            upregulated=upregulated,
            downregulated=downregulated,
            condition_a=request.condition_a,
            condition_b=request.condition_b,
            experiment_type=request.experiment_type,
            organism=request.organism,
            additional_context=request.additional_context or "",
            max_iterations=request.max_tool_iterations,
        )

        return InterpretDEGResponse(
            id=str(result.id),
            summary=result.summary,
            claims=_result_to_claims(result),
            tool_calls=_result_to_tool_calls(result),
            open_questions=result.open_questions,
            limitations=result.limitations,
            recommendations=result.recommendations,
            confidence_score=result.confidence_score,
            token_usage=_result_to_token_usage(result),
            cost_usd=result.cost_usd,
            processing_time_ms=result.processing_time_ms,
            model_used=result.model_used,
        )

    except Exception as e:
        logger.exception(f"DEG interpretation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Interpretation failed: {str(e)}",
        )


@router.post(
    "/pathway",
    response_model=InterpretPathwayResponse,
    summary="Interpret pathway enrichment results",
    description="Analyze pathway enrichment results with biological context",
)
async def interpret_pathway(
    request: InterpretPathwayRequest,
    user_id: UUID | None = Depends(get_optional_user_id),
    service: InterpretationService = Depends(get_interpretation_service),
) -> InterpretPathwayResponse:
    """Interpret pathway enrichment analysis results.

    Args:
        request: Pathway enrichment interpretation request
        user_id: Optional authenticated user ID
        service: Interpretation service

    Returns:
        Interpretation result with biological themes
    """
    try:
        # Convert pathways to dict format
        pathways = [
            {
                "name": p.pathway_name,
                "pathway_id": p.pathway_id,
                "p_value": p.p_value,
                "adjusted_p_value": p.adjusted_p_value,
                "gene_count": p.gene_count,
                "genes": p.genes,
            }
            for p in request.pathways
        ]

        result = await service.interpret_pathway_enrichment(
            pathways=pathways,
            experiment_context=request.experiment_context,
            gene_set_size=request.gene_set_size,
            max_iterations=request.max_tool_iterations,
        )

        # Extract biological themes from metadata if available
        biological_themes = result.metadata.get("biological_themes", [])
        if not biological_themes and result.claims:
            # Extract themes from pathways mentioned in claims
            themes = set()
            for claim in result.claims:
                themes.update(claim.pathways_mentioned)
            biological_themes = list(themes)[:10]

        return InterpretPathwayResponse(
            id=str(result.id),
            summary=result.summary,
            claims=_result_to_claims(result),
            tool_calls=_result_to_tool_calls(result),
            biological_themes=biological_themes,
            confidence_score=result.confidence_score,
            token_usage=_result_to_token_usage(result),
            cost_usd=result.cost_usd,
            processing_time_ms=result.processing_time_ms,
            model_used=result.model_used,
        )

    except Exception as e:
        logger.exception(f"Pathway interpretation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Interpretation failed: {str(e)}",
        )


@router.post(
    "/genes",
    response_model=AnalyzeGeneFunctionResponse,
    summary="Analyze gene function",
    description="Get functional analysis of a gene set",
)
async def analyze_gene_function(
    request: AnalyzeGeneFunctionRequest,
    user_id: UUID | None = Depends(get_optional_user_id),
    service: InterpretationService = Depends(get_interpretation_service),
) -> AnalyzeGeneFunctionResponse:
    """Analyze function and role of specific genes.

    Args:
        request: Gene function analysis request
        user_id: Optional authenticated user ID
        service: Interpretation service

    Returns:
        Interpretation result with gene summaries
    """
    try:
        result = await service.analyze_gene_function(
            genes=request.genes,
            analysis_context=request.analysis_context or "",
            max_iterations=request.max_tool_iterations,
        )

        # Extract gene summaries from metadata if available
        gene_summaries = result.metadata.get("gene_summaries", {})
        if not gene_summaries:
            # Build from claims mentioning each gene
            for gene in request.genes:
                for claim in result.claims:
                    if gene in claim.genes_mentioned:
                        gene_summaries[gene] = claim.statement
                        break

        return AnalyzeGeneFunctionResponse(
            id=str(result.id),
            summary=result.summary,
            claims=_result_to_claims(result),
            tool_calls=_result_to_tool_calls(result),
            gene_summaries=gene_summaries,
            confidence_score=result.confidence_score,
            token_usage=_result_to_token_usage(result),
            cost_usd=result.cost_usd,
            processing_time_ms=result.processing_time_ms,
            model_used=result.model_used,
        )

    except Exception as e:
        logger.exception(f"Gene function analysis failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}",
        )


@router.post(
    "/batch",
    response_model=AssessBatchEffectsResponse,
    summary="Assess batch effects",
    description="Evaluate batch effects in a dataset",
)
async def assess_batch_effects(
    request: AssessBatchEffectsRequest,
    user_id: UUID | None = Depends(get_optional_user_id),
    service: InterpretationService = Depends(get_interpretation_service),
) -> AssessBatchEffectsResponse:
    """Assess batch effects in a dataset.

    Args:
        request: Batch effect assessment request
        user_id: Optional authenticated user ID
        service: Interpretation service

    Returns:
        Interpretation result with severity assessment
    """
    try:
        result = await service.assess_batch_effects(
            batch_count=request.batch_count,
            batch_metrics=request.batch_metrics,
            samples_per_batch=request.samples_per_batch or "",
            pca_summary=request.pca_summary or "",
            max_iterations=request.max_tool_iterations,
        )

        # Extract batch effect specifics from metadata/claims
        severity = result.metadata.get("severity", "unknown")
        correction_recommended = result.metadata.get("correction_recommended", False)
        recommended_method = result.metadata.get("recommended_method")

        # Infer from summary if not in metadata
        summary_lower = result.summary.lower()
        if severity == "unknown":
            if "severe" in summary_lower or "strong" in summary_lower:
                severity = "high"
            elif "moderate" in summary_lower:
                severity = "medium"
            elif "minimal" in summary_lower or "no significant" in summary_lower:
                severity = "low"

        return AssessBatchEffectsResponse(
            id=str(result.id),
            summary=result.summary,
            claims=_result_to_claims(result),
            tool_calls=_result_to_tool_calls(result),
            severity=severity,
            correction_recommended=correction_recommended,
            recommended_method=recommended_method,
            confidence_score=result.confidence_score,
            token_usage=_result_to_token_usage(result),
            cost_usd=result.cost_usd,
            processing_time_ms=result.processing_time_ms,
            model_used=result.model_used,
        )

    except Exception as e:
        logger.exception(f"Batch effect assessment failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Assessment failed: {str(e)}",
        )


@router.post(
    "/literature",
    response_model=ReviewLiteratureResponse,
    summary="Review literature",
    description="Get a literature review on a biological topic",
)
async def review_literature(
    request: ReviewLiteratureRequest,
    user_id: UUID | None = Depends(get_optional_user_id),
    service: InterpretationService = Depends(get_interpretation_service),
) -> ReviewLiteratureResponse:
    """Review literature on a biological topic.

    Args:
        request: Literature review request
        user_id: Optional authenticated user ID
        service: Interpretation service

    Returns:
        Interpretation result with key findings and bibliography
    """
    try:
        result = await service.review_literature(
            topic=request.topic,
            focus_areas=request.focus_areas or "",
            research_context=request.research_context or "",
            max_iterations=request.max_tool_iterations,
        )

        # Extract key findings
        key_findings = result.metadata.get("key_findings", [])
        if not key_findings:
            # Use top claims as key findings
            key_findings = [claim.statement for claim in result.claims[:5]]

        # Get bibliography
        bibliography = result.metadata.get("bibliography", "")

        return ReviewLiteratureResponse(
            id=str(result.id),
            summary=result.summary,
            claims=_result_to_claims(result),
            tool_calls=_result_to_tool_calls(result),
            key_findings=key_findings,
            bibliography=bibliography,
            confidence_score=result.confidence_score,
            token_usage=_result_to_token_usage(result),
            cost_usd=result.cost_usd,
            processing_time_ms=result.processing_time_ms,
            model_used=result.model_used,
        )

    except Exception as e:
        logger.exception(f"Literature review failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Review failed: {str(e)}",
        )


@router.post(
    "/custom",
    response_model=CustomInterpretationResponse,
    summary="Custom interpretation",
    description="Run a custom interpretation with user-defined prompt",
)
async def custom_interpretation(
    request: CustomInterpretationRequest,
    user_id: UUID | None = Depends(get_optional_user_id),
    service: InterpretationService = Depends(get_interpretation_service),
) -> CustomInterpretationResponse:
    """Run a custom interpretation with user-defined prompt.

    Args:
        request: Custom interpretation request
        user_id: Optional authenticated user ID
        service: Interpretation service

    Returns:
        Interpretation result with full response text
    """
    try:
        result = await service.custom_interpretation(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            context=request.context,
            max_iterations=request.max_tool_iterations,
        )

        # Get full interpretation text
        full_response = result.metadata.get("interpretation_text", result.summary)

        return CustomInterpretationResponse(
            id=str(result.id),
            summary=result.summary,
            claims=_result_to_claims(result),
            tool_calls=_result_to_tool_calls(result),
            full_response=full_response,
            confidence_score=result.confidence_score,
            token_usage=_result_to_token_usage(result),
            cost_usd=result.cost_usd,
            processing_time_ms=result.processing_time_ms,
            model_used=result.model_used,
        )

    except Exception as e:
        logger.exception(f"Custom interpretation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Interpretation failed: {str(e)}",
        )


@router.get(
    "/tools",
    response_model=AvailableToolsResponse,
    summary="List available tools",
    description="Get list of available interpretation tools",
)
async def list_available_tools(
    service: InterpretationService = Depends(get_interpretation_service),
) -> AvailableToolsResponse:
    """List available interpretation tools.

    Returns:
        List of available tool names
    """
    tools = service.get_available_tools()
    return AvailableToolsResponse(
        tools=tools,
        tool_count=len(tools),
    )


@router.get(
    "/metrics",
    response_model=InterpretationMetricsResponse,
    summary="Get service metrics",
    description="Get interpretation service metrics",
)
async def get_metrics(
    service: InterpretationService = Depends(get_interpretation_service),
) -> InterpretationMetricsResponse:
    """Get interpretation service metrics.

    Returns:
        Service metrics including success rates and costs
    """
    metrics = service.get_metrics()
    executor_metrics = metrics.get("executor_metrics", {})

    return InterpretationMetricsResponse(
        total_interpretations=executor_metrics.get("total_calls", 0),
        successful_interpretations=executor_metrics.get("successful_calls", 0),
        failed_interpretations=executor_metrics.get("failed_calls", 0),
        average_processing_time_ms=executor_metrics.get("average_latency_ms", 0.0),
        total_tool_calls=executor_metrics.get("total_tool_calls", 0),
        tool_success_rate=executor_metrics.get("success_rate", 1.0),
        cache_hit_rate=executor_metrics.get("cache_hit_rate", 0.0),
        total_cost_usd=executor_metrics.get("total_cost_usd", 0.0),
    )
