"""Observability API endpoints for metrics and trace data."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/observability", tags=["observability"])


# Response models
class TokenUsageResponse(BaseModel):
    """LLM token usage response."""

    model: str
    total_tokens: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int


class CostSummaryResponse(BaseModel):
    """Cost summary response."""

    total_cost_usd: float
    cost_by_model: Dict[str, float]
    cost_by_provider: Dict[str, float]
    period_start: datetime
    period_end: datetime


class LLMMetricsResponse(BaseModel):
    """LLM metrics response."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    average_latency_seconds: float
    cache_hit_rate: float
    token_usage: List[TokenUsageResponse]


class PipelineMetricsResponse(BaseModel):
    """Pipeline metrics response."""

    total_executions: int
    successful_executions: int
    failed_executions: int
    average_duration_seconds: float
    average_results_count: float


class APIMetricsResponse(BaseModel):
    """API metrics response."""

    total_requests: int
    requests_by_endpoint: Dict[str, int]
    average_latency_seconds: float
    error_rate: float


class HealthMetricsResponse(BaseModel):
    """Health metrics response."""

    status: str
    llm_metrics: LLMMetricsResponse
    pipeline_metrics: PipelineMetricsResponse
    api_metrics: APIMetricsResponse


# API Endpoints
@router.get("/health")
async def observability_health() -> Dict[str, Any]:
    """Check observability health status.

    Returns:
        Health status
    """
    try:
        from quration.observability import get_langfuse_client, get_metrics

        langfuse_client = get_langfuse_client()
        metrics = get_metrics()

        return {
            "status": "ok",
            "langfuse_enabled": langfuse_client is not None and langfuse_client.enabled,
            "metrics_enabled": metrics is not None and metrics._enabled,
        }
    except ImportError:
        return {
            "status": "unavailable",
            "message": "Observability module not installed",
        }


@router.get("/metrics/llm/usage", response_model=Dict[str, Any])
async def get_llm_usage(
    time_range: str = Query(
        default="24h",
        description="Time range (e.g., '1h', '24h', '7d')",
    ),
    model: Optional[str] = Query(
        default=None,
        description="Filter by specific model",
    ),
) -> Dict[str, Any]:
    """Get LLM token usage metrics.

    Args:
        time_range: Time range for metrics
        model: Optional model filter

    Returns:
        LLM usage metrics
    """
    try:
        from quration.observability import get_metrics

        metrics_collector = get_metrics()
        if not metrics_collector or not metrics_collector._enabled:
            raise HTTPException(
                status_code=503,
                detail="Metrics collection not enabled",
            )

        # For now, return the raw Prometheus metrics
        # In production, this should query TimescaleDB or similar
        metrics_data = metrics_collector.get_metrics()

        return {
            "time_range": time_range,
            "model_filter": model,
            "metrics": metrics_data.decode("utf-8") if metrics_data else "No metrics available",
        }
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Observability module not available",
        )


@router.get("/metrics/llm/costs", response_model=Dict[str, Any])
async def get_llm_costs(
    time_range: str = Query(
        default="24h",
        description="Time range (e.g., '1h', '24h', '7d', '30d')",
    ),
    group_by: str = Query(
        default="model",
        description="Group by 'model', 'provider', or 'day'",
    ),
) -> Dict[str, Any]:
    """Get LLM cost metrics.

    Args:
        time_range: Time range for cost analysis
        group_by: Grouping dimension

    Returns:
        Cost breakdown
    """
    try:
        from quration.observability import get_metrics

        metrics_collector = get_metrics()
        if not metrics_collector or not metrics_collector._enabled:
            raise HTTPException(
                status_code=503,
                detail="Metrics collection not enabled",
            )

        # Get Prometheus metrics
        metrics_data = metrics_collector.get_metrics()

        # Parse cost metrics from Prometheus format
        # In production, query TimescaleDB with SQL for aggregations
        return {
            "time_range": time_range,
            "group_by": group_by,
            "message": "Cost metrics available via Prometheus /metrics endpoint",
            "prometheus_metrics": metrics_data.decode("utf-8") if metrics_data else None,
        }
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Observability module not available",
        )


@router.get("/metrics/pipeline/performance", response_model=Dict[str, Any])
async def get_pipeline_performance(
    pipeline_type: Optional[str] = Query(
        default=None,
        description="Filter by pipeline type",
    ),
    time_range: str = Query(
        default="24h",
        description="Time range",
    ),
) -> Dict[str, Any]:
    """Get pipeline performance metrics.

    Args:
        pipeline_type: Optional pipeline type filter
        time_range: Time range for metrics

    Returns:
        Pipeline performance metrics
    """
    try:
        from quration.observability import get_metrics

        metrics_collector = get_metrics()
        if not metrics_collector or not metrics_collector._enabled:
            raise HTTPException(
                status_code=503,
                detail="Metrics collection not enabled",
            )

        metrics_data = metrics_collector.get_metrics()

        return {
            "pipeline_type": pipeline_type,
            "time_range": time_range,
            "message": "Pipeline metrics available via Prometheus /metrics endpoint",
            "prometheus_metrics": metrics_data.decode("utf-8") if metrics_data else None,
        }
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Observability module not available",
        )


@router.get("/traces", response_model=Dict[str, Any])
async def get_traces(
    limit: int = Query(default=50, ge=1, le=1000),
    user_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
) -> Dict[str, Any]:
    """Get recent traces from LangFuse.

    Args:
        limit: Maximum number of traces to return
        user_id: Filter by user ID
        status: Filter by status

    Returns:
        List of traces
    """
    try:
        from quration.observability import get_langfuse_client

        langfuse_client = get_langfuse_client()
        if not langfuse_client or not langfuse_client.enabled:
            raise HTTPException(
                status_code=503,
                detail="LangFuse not enabled or configured",
            )

        # Note: LangFuse Python SDK doesn't have a direct API to query traces
        # Users should access the LangFuse web UI or use the LangFuse HTTP API
        return {
            "message": "Trace data available in LangFuse web UI",
            "langfuse_host": langfuse_client.config.host,
            "note": "Use LangFuse web UI or HTTP API to query traces",
            "api_docs": f"{langfuse_client.config.host}/docs",
        }
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Observability module not available",
        )


@router.get("/costs/summary", response_model=Dict[str, Any])
async def get_cost_summary(
    days: int = Query(default=7, ge=1, le=90),
) -> Dict[str, Any]:
    """Get cost summary for the specified period.

    Args:
        days: Number of days to analyze

    Returns:
        Cost summary
    """
    try:
        from quration.observability import get_metrics

        metrics_collector = get_metrics()
        if not metrics_collector or not metrics_collector._enabled:
            raise HTTPException(
                status_code=503,
                detail="Metrics collection not enabled",
            )

        # In production, query TimescaleDB for cost aggregations
        metrics_data = metrics_collector.get_metrics()

        return {
            "period_days": days,
            "period_start": (datetime.now() - timedelta(days=days)).isoformat(),
            "period_end": datetime.now().isoformat(),
            "message": "Cost data available via Prometheus /metrics endpoint",
            "note": "For detailed cost analysis, query TimescaleDB directly or use Grafana dashboards",
        }
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Observability module not available",
        )


# Include router in FastAPI app:
# app.include_router(observability_routes.router)
