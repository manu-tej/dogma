"""FastAPI middleware for observability."""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .langfuse_client import get_langfuse_client
from .metrics import get_metrics
from .structured_logger import set_trace_context

logger = logging.getLogger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically trace all HTTP requests."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Process HTTP request with observability.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler

        Returns:
            HTTP response
        """
        langfuse_client = get_langfuse_client()
        metrics = get_metrics()

        # Generate or extract trace ID
        trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
        user_id = self._extract_user_id(request)
        session_id = request.headers.get("X-Session-ID")

        # Set trace context for logging
        set_trace_context(trace_id=trace_id, user_id=user_id)

        # Start time
        start_time = time.time()

        # Create trace in LangFuse
        trace = None
        if langfuse_client and langfuse_client.enabled:
            trace = langfuse_client.create_trace(
                name=f"{request.method} {request.url.path}",
                trace_id=trace_id,
                user_id=user_id,
                session_id=session_id,
                metadata={
                    "method": request.method,
                    "url": str(request.url),
                    "path": request.url.path,
                    "query_params": dict(request.query_params),
                    "headers": self._safe_headers(request.headers),
                    "client": {
                        "host": request.client.host if request.client else None,
                        "port": request.client.port if request.client else None,
                    },
                },
                tags=["api", "http"],
            )

        # Process request
        response = None
        status_code = 500
        error: Exception | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code

            # Add trace ID to response headers
            response.headers["X-Trace-ID"] = trace_id

            return response

        except Exception as e:
            error = e
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                exc_info=True,
                extra={
                    "trace_id": trace_id,
                    "user_id": user_id,
                    "error_type": type(e).__name__,
                },
            )
            raise

        finally:
            # Calculate metrics
            duration = time.time() - start_time

            # Update trace
            if trace:
                trace.update(
                    metadata={
                        **(trace.metadata or {}),
                        "status_code": status_code,
                        "duration_seconds": duration,
                        "error": str(error) if error else None,
                        "error_type": type(error).__name__ if error else None,
                    }
                )

            # Record metrics
            if metrics and metrics._enabled:
                # Simplify endpoint path for metrics (remove IDs)
                endpoint = self._simplify_endpoint(request.url.path)

                # Get request/response sizes
                request_size = request.headers.get("content-length")
                request_size = int(request_size) if request_size else None

                response_size = None
                if response:
                    response_size = response.headers.get("content-length")
                    response_size = int(response_size) if response_size else None

                metrics.record_http_request(
                    method=request.method,
                    endpoint=endpoint,
                    status_code=status_code,
                    duration=duration,
                    request_size=request_size,
                    response_size=response_size,
                )

                # Record error if occurred
                if error:
                    metrics.record_error(
                        component="api",
                        error_type=type(error).__name__,
                    )

            # Flush trace
            if langfuse_client and langfuse_client.enabled:
                langfuse_client.flush()

            # Log request completion
            logger.info(
                f"Request completed: {request.method} {request.url.path}",
                extra={
                    "trace_id": trace_id,
                    "user_id": user_id,
                    "status_code": status_code,
                    "duration_seconds": duration,
                },
            )

    def _extract_user_id(self, request: Request) -> str | None:
        """Extract user ID from request.

        Args:
            request: HTTP request

        Returns:
            User ID or None
        """
        # Check for user ID in headers
        user_id = request.headers.get("X-User-ID")
        if user_id:
            return user_id

        # Check for authorization header (extract from JWT, etc.)
        # This is a placeholder - implement actual user extraction logic
        auth_header = request.headers.get("Authorization")
        if auth_header:
            # TODO: Extract user from JWT token
            pass

        # Check for session cookie
        # TODO: Extract user from session

        return None

    def _safe_headers(self, headers: dict) -> dict:
        """Filter sensitive headers.

        Args:
            headers: Request headers

        Returns:
            Filtered headers dict
        """
        sensitive_headers = {
            "authorization",
            "cookie",
            "x-api-key",
            "x-auth-token",
        }

        return {
            k: v if k.lower() not in sensitive_headers else "[REDACTED]"
            for k, v in headers.items()
        }

    def _simplify_endpoint(self, path: str) -> str:
        """Simplify endpoint path for metrics by removing IDs.

        Args:
            path: URL path

        Returns:
            Simplified path

        Example:
            /geo/datasets/GSE123456 -> /geo/datasets/{id}
            /users/user123/profile -> /users/{id}/profile
        """
        # Split path into segments
        segments = path.split("/")

        # Replace segments that look like IDs with {id}
        simplified = []
        for segment in segments:
            if not segment:
                continue

            # Check if segment looks like an ID
            if (
                segment.startswith("GSE")
                or segment.startswith("GSM")
                or segment.isdigit()
                or len(segment) > 20
            ):
                simplified.append("{id}")
            else:
                simplified.append(segment)

        return "/" + "/".join(simplified)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to expose Prometheus metrics endpoint."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """Process request and expose metrics if requested.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or route handler

        Returns:
            HTTP response
        """
        # Check if this is a metrics request
        if request.url.path == "/metrics":
            metrics = get_metrics()
            if metrics:
                metrics_data = metrics.get_metrics()
                return Response(
                    content=metrics_data,
                    media_type="text/plain; version=0.0.4; charset=utf-8",
                )

        # Pass through to next middleware
        return await call_next(request)
