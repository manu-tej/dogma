"""Observability module for quration platform.

This module provides comprehensive observability for LLM usage tracking,
pipeline execution monitoring, and API analytics using LangFuse, structured
logging, and Prometheus metrics.

Usage:
    from quration.observability import initialize_observability, observe_pipeline

    # Initialize observability
    initialize_observability(config)

    # Use decorators for automatic instrumentation
    @observe_pipeline(pipeline_type="geo_search")
    def search_datasets(query_spec):
        ...
"""

import logging
from typing import Optional

from .config import (
    LangFuseConfig,
    MetricsConfig,
    ObservabilityConfig,
    StructuredLoggingConfig,
)
from .decorators import observe_api, observe_llm, observe_pipeline, observe_span
from .langfuse_client import (
    QurationLangFuseClient,
    get_langfuse_client,
    initialize_langfuse,
)
from .metrics import QurationMetrics, get_metrics, initialize_metrics
from .middleware import ObservabilityMiddleware, PrometheusMiddleware
from .structured_logger import (
    clear_trace_context,
    get_trace_id,
    set_trace_context,
    setup_structured_logging,
)
from .interpretation import (
    InterpretationObserver,
    TraceContext,
    get_interpretation_observer,
    initialize_interpretation_observer,
    observe_interpretation,
)

logger = logging.getLogger(__name__)

__all__ = [
    # Configuration
    "ObservabilityConfig",
    "LangFuseConfig",
    "StructuredLoggingConfig",
    "MetricsConfig",
    # LangFuse
    "QurationLangFuseClient",
    "initialize_langfuse",
    "get_langfuse_client",
    # Metrics
    "QurationMetrics",
    "initialize_metrics",
    "get_metrics",
    # Logging
    "setup_structured_logging",
    "set_trace_context",
    "clear_trace_context",
    "get_trace_id",
    # Decorators
    "observe_llm",
    "observe_pipeline",
    "observe_span",
    "observe_api",
    # Middleware
    "ObservabilityMiddleware",
    "PrometheusMiddleware",
    # Interpretation observability
    "InterpretationObserver",
    "TraceContext",
    "get_interpretation_observer",
    "initialize_interpretation_observer",
    "observe_interpretation",
    # Initialization
    "initialize_observability",
]


def initialize_observability(
    config: Optional[ObservabilityConfig] = None,
) -> tuple[
    Optional[QurationLangFuseClient],
    Optional[QurationMetrics],
]:
    """Initialize all observability components.

    This function sets up:
    - LangFuse client for LLM tracing
    - Structured logging with trace context
    - Prometheus metrics collection

    Args:
        config: Observability configuration (uses defaults if not provided)

    Returns:
        Tuple of (LangFuse client, Metrics instance)

    Example:
        from quration.observability import initialize_observability
        from quration.observability.config import ObservabilityConfig

        config = ObservabilityConfig()
        langfuse_client, metrics = initialize_observability(config)
    """
    if config is None:
        config = ObservabilityConfig()

    if not config.enabled:
        logger.info("Observability is disabled")
        return None, None

    # Initialize structured logging
    if config.logging.enabled:
        try:
            setup_structured_logging(config.logging)
            logger.info("Structured logging initialized")
        except Exception as e:
            logger.error(f"Failed to initialize structured logging: {e}")

    # Initialize LangFuse
    langfuse_client = None
    if config.langfuse.enabled:
        try:
            langfuse_client = initialize_langfuse(config.langfuse)
            if langfuse_client.enabled:
                logger.info("LangFuse client initialized successfully")
            else:
                logger.warning("LangFuse client failed to initialize (check API keys)")
        except Exception as e:
            logger.error(f"Failed to initialize LangFuse: {e}")

    # Initialize metrics
    metrics = None
    if config.metrics.enabled:
        try:
            metrics = initialize_metrics(config.metrics)
            logger.info("Metrics collection initialized")
        except Exception as e:
            logger.error(f"Failed to initialize metrics: {e}")

    logger.info(
        f"Observability initialized: "
        f"langfuse={langfuse_client is not None and langfuse_client.enabled}, "
        f"metrics={metrics is not None and metrics._enabled}, "
        f"logging={config.logging.enabled}"
    )

    return langfuse_client, metrics
