"""Observability integration for the interpretation layer.

This module provides Prometheus metrics and LangFuse traces specifically
for monitoring interpretation operations.
"""

import logging
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from prometheus_client import Counter, Gauge, Histogram

from quration.interpretation.models import (
    InterpretationResult,
    InterpretationType,
    ToolCallRecord,
    ToolCallStatus,
)
from quration.observability.langfuse_client import get_langfuse_client
from quration.observability.metrics import get_metrics

logger = logging.getLogger(__name__)


# ============================================================================
# Prometheus Metrics
# ============================================================================

# Request metrics
interpretation_requests_total = Counter(
    "quration_interpretation_requests_total",
    "Total interpretation requests",
    ["type", "status"],
)

interpretation_latency_seconds = Histogram(
    "quration_interpretation_latency_seconds",
    "Interpretation request duration in seconds",
    ["type"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0],
)

# Tool metrics
interpretation_tool_calls_total = Counter(
    "quration_interpretation_tool_calls_total",
    "Total tool calls during interpretation",
    ["tool", "status"],
)

interpretation_tool_latency_seconds = Histogram(
    "quration_interpretation_tool_latency_seconds",
    "Tool call duration in seconds",
    ["tool"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)

# Claim metrics
interpretation_claims_total = Counter(
    "quration_interpretation_claims_total",
    "Total claims extracted",
    ["type", "claim_type", "confidence"],
)

interpretation_confidence_histogram = Histogram(
    "quration_interpretation_confidence",
    "Interpretation confidence score distribution",
    ["type"],
    buckets=[0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0],
)

# Cost metrics
interpretation_cost_usd_total = Counter(
    "quration_interpretation_cost_usd_total",
    "Total interpretation cost in USD",
    ["type", "model"],
)

interpretation_tokens_total = Counter(
    "quration_interpretation_tokens_total",
    "Total tokens used for interpretation",
    ["type", "token_type"],  # input, output
)

# Cache metrics
interpretation_cache_hits_total = Counter(
    "quration_interpretation_cache_hits_total",
    "Total interpretation cache hits",
    ["type"],
)

interpretation_cache_misses_total = Counter(
    "quration_interpretation_cache_misses_total",
    "Total interpretation cache misses",
    ["type"],
)

# Active interpretations gauge
interpretation_active = Gauge(
    "quration_interpretation_active",
    "Currently active interpretations",
    ["type"],
)


class InterpretationObserver:
    """Observer for interpretation operations.

    This class provides a unified interface for both Prometheus metrics
    and LangFuse traces for interpretation operations.

    Example:
        ```python
        observer = InterpretationObserver()

        with observer.trace_interpretation(
            interpretation_type="deg_analysis",
            user_id="user-123",
        ) as context:
            # Run interpretation
            result = await interpreter.interpret(...)

            # Record tool calls
            for tool_call in result.tool_calls:
                observer.record_tool_call(context, tool_call)

            # Complete trace
            observer.complete_interpretation(context, result)
        ```
    """

    def __init__(self):
        """Initialize the interpretation observer."""
        self._langfuse = get_langfuse_client()
        self._metrics = get_metrics()

    @contextmanager
    def trace_interpretation(
        self,
        interpretation_type: str | InterpretationType,
        user_id: UUID | str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Context manager for tracing an interpretation operation.

        Args:
            interpretation_type: Type of interpretation
            user_id: User ID
            session_id: Session ID for grouping
            metadata: Additional metadata

        Yields:
            TraceContext with trace_id and start_time
        """
        if isinstance(interpretation_type, InterpretationType):
            type_str = interpretation_type.value
        else:
            type_str = interpretation_type

        # Create trace context
        context = TraceContext(
            interpretation_type=type_str,
            user_id=str(user_id) if user_id else None,
            session_id=session_id,
            start_time=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

        # Start LangFuse trace
        if self._langfuse and self._langfuse.enabled:
            context.trace_id = self._langfuse.create_trace(
                name=f"interpretation:{type_str}",
                user_id=context.user_id,
                session_id=session_id,
                metadata={
                    "interpretation_type": type_str,
                    **(metadata or {}),
                },
                tags=["interpretation", type_str],
            )

        # Increment active gauge
        interpretation_active.labels(type=type_str).inc()

        try:
            yield context
        except Exception as e:
            # Record error
            context.error = str(e)
            context.status = "error"
            self._record_error(context, e)
            raise
        finally:
            # Decrement active gauge
            interpretation_active.labels(type=type_str).dec()

            # Flush LangFuse
            if self._langfuse:
                self._langfuse.flush()

    @asynccontextmanager
    async def trace_interpretation_async(
        self,
        interpretation_type: str | InterpretationType,
        user_id: UUID | str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Async context manager for tracing an interpretation operation.

        Same as trace_interpretation but for async contexts.
        """
        if isinstance(interpretation_type, InterpretationType):
            type_str = interpretation_type.value
        else:
            type_str = interpretation_type

        context = TraceContext(
            interpretation_type=type_str,
            user_id=str(user_id) if user_id else None,
            session_id=session_id,
            start_time=datetime.now(timezone.utc),
            metadata=metadata or {},
        )

        if self._langfuse and self._langfuse.enabled:
            context.trace_id = self._langfuse.create_trace(
                name=f"interpretation:{type_str}",
                user_id=context.user_id,
                session_id=session_id,
                metadata={
                    "interpretation_type": type_str,
                    **(metadata or {}),
                },
                tags=["interpretation", type_str],
            )

        interpretation_active.labels(type=type_str).inc()

        try:
            yield context
        except Exception as e:
            context.error = str(e)
            context.status = "error"
            self._record_error(context, e)
            raise
        finally:
            interpretation_active.labels(type=type_str).dec()
            if self._langfuse:
                self._langfuse.flush()

    def record_tool_call(
        self,
        context: "TraceContext",
        tool_call: ToolCallRecord,
    ) -> None:
        """Record a tool call during interpretation.

        Args:
            context: Trace context
            tool_call: Tool call record
        """
        tool_name = tool_call.tool_name
        status = tool_call.status.value
        latency_sec = tool_call.latency_ms / 1000.0

        # Record Prometheus metrics
        interpretation_tool_calls_total.labels(tool=tool_name, status=status).inc()
        interpretation_tool_latency_seconds.labels(tool=tool_name).observe(latency_sec)

        # Record LangFuse span
        if self._langfuse and context.trace_id:
            self._langfuse.create_span(
                trace_id=context.trace_id,
                name=f"tool:{tool_name}",
                input=tool_call.tool_input,
                output=tool_call.tool_output,
                metadata={
                    "status": status,
                    "latency_ms": tool_call.latency_ms,
                    "cached": tool_call.cached,
                    "error": tool_call.error_message,
                },
            )

    def record_llm_generation(
        self,
        context: "TraceContext",
        model: str,
        prompt: str | list[dict[str, Any]],
        completion: str,
        usage: dict[str, int],
        latency_sec: float,
    ) -> None:
        """Record an LLM generation.

        Args:
            context: Trace context
            model: Model name
            prompt: Input prompt
            completion: Output completion
            usage: Token usage dict
            latency_sec: Latency in seconds
        """
        # Record LangFuse generation
        if self._langfuse and context.trace_id:
            self._langfuse.create_generation(
                trace_id=context.trace_id,
                name="llm_generation",
                model=model,
                prompt=prompt,
                completion=completion,
                usage=usage,
                metadata={"latency_sec": latency_sec},
            )

    def complete_interpretation(
        self,
        context: "TraceContext",
        result: InterpretationResult,
        cache_hit: bool = False,
    ) -> None:
        """Complete an interpretation trace with results.

        Args:
            context: Trace context
            result: Interpretation result
            cache_hit: Whether result was from cache
        """
        type_str = context.interpretation_type
        end_time = datetime.now(timezone.utc)
        duration_sec = (end_time - context.start_time).total_seconds()

        # Determine status
        status = "success" if result.confidence_score > 0 else "error"
        context.status = status

        # Record request metrics
        interpretation_requests_total.labels(type=type_str, status=status).inc()
        interpretation_latency_seconds.labels(type=type_str).observe(duration_sec)

        # Record confidence
        interpretation_confidence_histogram.labels(type=type_str).observe(
            result.confidence_score
        )

        # Record cost and tokens
        interpretation_cost_usd_total.labels(
            type=type_str, model=result.model_used
        ).inc(result.cost_usd)

        interpretation_tokens_total.labels(type=type_str, token_type="input").inc(
            result.token_usage.input_tokens
        )
        interpretation_tokens_total.labels(type=type_str, token_type="output").inc(
            result.token_usage.output_tokens
        )

        # Record claims
        for claim in result.claims:
            interpretation_claims_total.labels(
                type=type_str,
                claim_type=claim.claim_type.value,
                confidence=claim.confidence.value,
            ).inc()

        # Record cache metrics
        if cache_hit:
            interpretation_cache_hits_total.labels(type=type_str).inc()
        else:
            interpretation_cache_misses_total.labels(type=type_str).inc()

        # Record tool calls to metrics
        for tool_call in result.tool_calls:
            self.record_tool_call(context, tool_call)

        # Complete LangFuse trace
        if self._langfuse and context.trace_id:
            # Add final event
            self._langfuse.create_event(
                trace_id=context.trace_id,
                name="interpretation_complete",
                metadata={
                    "duration_sec": duration_sec,
                    "claims_count": len(result.claims),
                    "tool_calls_count": len(result.tool_calls),
                    "confidence_score": result.confidence_score,
                    "cost_usd": result.cost_usd,
                    "cache_hit": cache_hit,
                },
            )

            # Add confidence score
            self._langfuse.score(
                trace_id=context.trace_id,
                name="confidence",
                value=result.confidence_score,
                comment=f"{len(result.claims)} claims extracted",
            )

    def record_cache_hit(
        self,
        interpretation_type: str | InterpretationType,
    ) -> None:
        """Record a cache hit.

        Args:
            interpretation_type: Type of interpretation
        """
        if isinstance(interpretation_type, InterpretationType):
            type_str = interpretation_type.value
        else:
            type_str = interpretation_type

        interpretation_cache_hits_total.labels(type=type_str).inc()

    def record_cache_miss(
        self,
        interpretation_type: str | InterpretationType,
    ) -> None:
        """Record a cache miss.

        Args:
            interpretation_type: Type of interpretation
        """
        if isinstance(interpretation_type, InterpretationType):
            type_str = interpretation_type.value
        else:
            type_str = interpretation_type

        interpretation_cache_misses_total.labels(type=type_str).inc()

    def _record_error(
        self,
        context: "TraceContext",
        error: Exception,
    ) -> None:
        """Record an error during interpretation.

        Args:
            context: Trace context
            error: The exception
        """
        type_str = context.interpretation_type

        # Record Prometheus error
        interpretation_requests_total.labels(type=type_str, status="error").inc()

        # Record LangFuse error event
        if self._langfuse and context.trace_id:
            self._langfuse.create_event(
                trace_id=context.trace_id,
                name="interpretation_error",
                metadata={
                    "error": str(error),
                    "error_type": type(error).__name__,
                },
            )

            # Add error score
            self._langfuse.score(
                trace_id=context.trace_id,
                name="success",
                value=0.0,
                comment=f"Error: {type(error).__name__}",
            )


class TraceContext:
    """Context for an interpretation trace."""

    def __init__(
        self,
        interpretation_type: str,
        user_id: str | None = None,
        session_id: str | None = None,
        start_time: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Initialize trace context.

        Args:
            interpretation_type: Type of interpretation
            user_id: User ID
            session_id: Session ID
            start_time: Start time
            metadata: Additional metadata
        """
        self.interpretation_type = interpretation_type
        self.user_id = user_id
        self.session_id = session_id
        self.start_time = start_time or datetime.now(timezone.utc)
        self.metadata = metadata or {}
        self.trace_id: str | None = None
        self.status: str = "pending"
        self.error: str | None = None


# Global singleton
_observer: InterpretationObserver | None = None


def get_interpretation_observer() -> InterpretationObserver:
    """Get or create the global interpretation observer.

    Returns:
        InterpretationObserver instance
    """
    global _observer
    if _observer is None:
        _observer = InterpretationObserver()
    return _observer


def initialize_interpretation_observer() -> InterpretationObserver:
    """Initialize the global interpretation observer.

    Returns:
        InterpretationObserver instance
    """
    global _observer
    _observer = InterpretationObserver()
    return _observer


# ============================================================================
# Decorator for easy integration
# ============================================================================


def observe_interpretation(
    interpretation_type: str | InterpretationType,
):
    """Decorator for observing interpretation functions.

    Args:
        interpretation_type: Type of interpretation

    Example:
        ```python
        @observe_interpretation("deg_analysis")
        async def interpret_deg_results(...) -> InterpretationResult:
            ...
        ```
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            observer = get_interpretation_observer()
            user_id = kwargs.get("user_id")

            async with observer.trace_interpretation_async(
                interpretation_type=interpretation_type,
                user_id=user_id,
            ) as context:
                result = await func(*args, **kwargs)

                if isinstance(result, InterpretationResult):
                    observer.complete_interpretation(context, result)

                return result

        return wrapper
    return decorator
