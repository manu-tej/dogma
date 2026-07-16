"""Observability decorators for automatic instrumentation."""

import functools
import logging
import time
from typing import Any, Callable, Optional, TypeVar, cast

from .langfuse_client import get_langfuse_client
from .metrics import get_metrics
from .structured_logger import get_trace_id, set_trace_context

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def observe_llm(
    model: str,
    provider: str,
    name: Optional[str] = None,
) -> Callable[[F], F]:
    """Decorator to observe LLM function calls.

    Args:
        model: Model name (e.g., "claude-sonnet-4-5")
        provider: Provider name (e.g., "anthropic")
        name: Optional custom name for the generation

    Returns:
        Decorated function

    Example:
        @observe_llm(model="claude-sonnet-4-5", provider="anthropic")
        def generate_query(prompt: str) -> str:
            # Your LLM call here
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            langfuse_client = get_langfuse_client()
            metrics = get_metrics()
            trace_id = get_trace_id()

            generation_name = name or func.__name__
            start_time = time.time()
            status = "success"
            error: Optional[Exception] = None

            try:
                # Call the function
                result = func(*args, **kwargs)

                # Extract token usage and cost if available
                tokens = None
                cost = None
                cache_hit = False

                if isinstance(result, dict):
                    tokens = result.get("usage")
                    cost = result.get("cost")
                    cache_hit = result.get("cache_hit", False)

                # Record in LangFuse if trace exists
                if langfuse_client and langfuse_client.enabled and trace_id:
                    prompt = kwargs.get("prompt") or (args[0] if args else None)
                    completion = result.get("completion") if isinstance(result, dict) else result

                    langfuse_client.create_generation(
                        trace_id=trace_id,
                        name=generation_name,
                        model=model,
                        prompt=prompt,
                        completion=completion,
                        usage=tokens,
                        metadata={
                            "provider": provider,
                            **kwargs,
                        },
                    )

                # Record metrics
                if metrics and metrics._enabled:
                    latency = time.time() - start_time
                    metrics.record_llm_request(
                        model=model,
                        provider=provider,
                        status=status,
                        latency=latency,
                        tokens=tokens,
                        cost=cost,
                        cache_hit=cache_hit,
                    )

                return result

            except Exception as e:
                status = "error"
                error = e
                raise
            finally:
                # Record error metrics
                if error and metrics and metrics._enabled:
                    latency = time.time() - start_time
                    metrics.record_llm_request(
                        model=model,
                        provider=provider,
                        status=status,
                        latency=latency,
                    )
                    metrics.record_error(
                        component="llm_provider",
                        error_type=type(error).__name__ if error else "unknown",
                    )

                # Log completion
                logger.info(
                    f"LLM call completed: {generation_name}",
                    extra={
                        "model": model,
                        "provider": provider,
                        "status": status,
                        "latency": time.time() - start_time,
                    },
                )

        return cast(F, wrapper)

    return decorator


def observe_pipeline(
    pipeline_type: str,
    name: Optional[str] = None,
) -> Callable[[F], F]:
    """Decorator to observe pipeline function executions.

    Args:
        pipeline_type: Pipeline type (e.g., "geo_search")
        name: Optional custom name for the pipeline

    Returns:
        Decorated function

    Example:
        @observe_pipeline(pipeline_type="geo_search")
        def search_geo_datasets(query_spec: QuerySpec) -> list[GeoDataset]:
            # Your pipeline code here
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            langfuse_client = get_langfuse_client()
            metrics = get_metrics()

            pipeline_name = name or func.__name__
            start_time = time.time()
            status = "success"
            error: Optional[Exception] = None

            # Create trace
            trace = None
            if langfuse_client and langfuse_client.enabled:
                user_id = kwargs.get("user_id")
                session_id = kwargs.get("session_id")
                trace = langfuse_client.create_trace(
                    name=pipeline_name,
                    user_id=user_id,
                    session_id=session_id,
                    metadata={
                        "pipeline_type": pipeline_type,
                        **{k: v for k, v in kwargs.items() if k not in ["user_id", "session_id"]},
                    },
                    tags=[pipeline_type, "pipeline"],
                )

                # Set trace context for nested calls
                if trace:
                    set_trace_context(trace_id=trace.id, user_id=user_id)

            try:
                # Call the function
                result = func(*args, **kwargs)

                # Get result count if available
                result_count = None
                if isinstance(result, list):
                    result_count = len(result)
                elif isinstance(result, dict) and "results" in result:
                    result_count = len(result["results"])

                # Record metrics
                if metrics and metrics._enabled:
                    duration = time.time() - start_time
                    metrics.record_pipeline_execution(
                        pipeline_type=pipeline_type,
                        status=status,
                        duration=duration,
                        result_count=result_count,
                    )

                return result

            except Exception as e:
                status = "error"
                error = e
                raise
            finally:
                # Record error metrics
                if error:
                    if metrics and metrics._enabled:
                        duration = time.time() - start_time
                        metrics.record_pipeline_execution(
                            pipeline_type=pipeline_type,
                            status=status,
                            duration=duration,
                        )
                        metrics.record_error(
                            component="pipeline",
                            error_type=type(error).__name__,
                        )

                    # Update trace with error
                    if trace:
                        trace.update(
                            metadata={
                                **(trace.metadata or {}),
                                "error": str(error),
                                "error_type": type(error).__name__,
                            }
                        )

                # Flush trace
                if langfuse_client and langfuse_client.enabled:
                    langfuse_client.flush()

                # Log completion
                logger.info(
                    f"Pipeline completed: {pipeline_name}",
                    extra={
                        "pipeline_type": pipeline_type,
                        "status": status,
                        "duration": time.time() - start_time,
                    },
                )

        return cast(F, wrapper)

    return decorator


def observe_span(
    name: str,
    metadata: Optional[dict[str, Any]] = None,
) -> Callable[[F], F]:
    """Decorator to observe custom operations as spans.

    Args:
        name: Span name (e.g., "NCBI Search", "Ontology Mapping")
        metadata: Additional metadata

    Returns:
        Decorated function

    Example:
        @observe_span(name="NCBI Search")
        def ncbi_search(query: str) -> list[dict]:
            # Your code here
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            langfuse_client = get_langfuse_client()
            trace_id = get_trace_id()

            start_time = time.time()
            span = None

            # Create span if trace exists
            if langfuse_client and langfuse_client.enabled and trace_id:
                span = langfuse_client.create_span(
                    trace_id=trace_id,
                    name=name,
                    input={"args": args, "kwargs": kwargs},
                    metadata=metadata,
                )

            try:
                # Call the function
                result = func(*args, **kwargs)

                # Update span with output
                if span:
                    span.update(output=result)

                return result

            except Exception as e:
                # Update span with error
                if span:
                    span.update(
                        metadata={
                            **(span.metadata or {}),
                            "error": str(e),
                            "error_type": type(e).__name__,
                        },
                        level="ERROR",
                    )
                raise
            finally:
                # End span
                if span:
                    span.end()

                # Log completion
                logger.debug(
                    f"Span completed: {name}",
                    extra={
                        "span_name": name,
                        "duration": time.time() - start_time,
                    },
                )

        return cast(F, wrapper)

    return decorator


def observe_api(
    endpoint: str,
) -> Callable[[F], F]:
    """Decorator to observe API endpoint calls.

    Args:
        endpoint: API endpoint path

    Returns:
        Decorated function

    Example:
        @observe_api(endpoint="/geo/search")
        async def search_endpoint(request: Request) -> Response:
            # Your endpoint code here
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            metrics = get_metrics()
            start_time = time.time()

            # Extract request info
            request = args[0] if args else None
            method = request.method if hasattr(request, "method") else "UNKNOWN"

            try:
                # Call the function
                response = await func(*args, **kwargs)

                # Extract response info
                status_code = (
                    response.status_code if hasattr(response, "status_code") else 200
                )

                # Record metrics
                if metrics and metrics._enabled:
                    duration = time.time() - start_time
                    metrics.record_http_request(
                        method=method,
                        endpoint=endpoint,
                        status_code=status_code,
                        duration=duration,
                    )

                return response

            except Exception as e:
                # Record error metrics
                if metrics and metrics._enabled:
                    duration = time.time() - start_time
                    metrics.record_http_request(
                        method=method,
                        endpoint=endpoint,
                        status_code=500,
                        duration=duration,
                    )
                    metrics.record_error(
                        component="api",
                        error_type=type(e).__name__,
                    )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            metrics = get_metrics()
            start_time = time.time()

            # Extract request info
            request = args[0] if args else None
            method = request.method if hasattr(request, "method") else "UNKNOWN"

            try:
                # Call the function
                response = func(*args, **kwargs)

                # Extract response info
                status_code = (
                    response.status_code if hasattr(response, "status_code") else 200
                )

                # Record metrics
                if metrics and metrics._enabled:
                    duration = time.time() - start_time
                    metrics.record_http_request(
                        method=method,
                        endpoint=endpoint,
                        status_code=status_code,
                        duration=duration,
                    )

                return response

            except Exception as e:
                # Record error metrics
                if metrics and metrics._enabled:
                    duration = time.time() - start_time
                    metrics.record_http_request(
                        method=method,
                        endpoint=endpoint,
                        status_code=500,
                        duration=duration,
                    )
                    metrics.record_error(
                        component="api",
                        error_type=type(e).__name__,
                    )
                raise

        # Return async or sync wrapper based on function type
        if functools.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        else:
            return cast(F, sync_wrapper)

    return decorator
