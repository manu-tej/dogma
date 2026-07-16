"""LangFuse client wrapper for quration platform."""

import logging
import uuid
from contextlib import contextmanager
from typing import Any, Optional

from langfuse import Langfuse

from .config import LangFuseConfig

logger = logging.getLogger(__name__)


class QurationLangFuseClient:
    """Wrapper around LangFuse client with quration-specific functionality."""

    def __init__(self, config: LangFuseConfig) -> None:
        """Initialize LangFuse client.

        Args:
            config: LangFuse configuration
        """
        self.config = config
        self._client: Optional[Langfuse] = None
        self._enabled = config.enabled

        if self._enabled and config.public_key and config.secret_key:
            self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the LangFuse client."""
        try:
            self._client = Langfuse(
                public_key=self.config.public_key,
                secret_key=self.config.secret_key,
                host=self.config.host,
                debug=self.config.debug,
                tracing_enabled=self.config.enabled,  # Note: parameter is tracing_enabled, not enabled
                sample_rate=self.config.sample_rate,
                flush_interval=self.config.flush_interval,
                release=self.config.release or None,
                environment=self.config.environment,
            )
            logger.info(
                f"LangFuse client initialized: host={self.config.host}, "
                f"environment={self.config.environment}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize LangFuse client: {e}")
            self._enabled = False
            self._client = None

    @property
    def enabled(self) -> bool:
        """Check if LangFuse is enabled and initialized."""
        return self._enabled and self._client is not None

    def create_trace(
        self,
        name: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        trace_id: Optional[str] = None,
    ) -> Optional[str]:
        """Create a new trace and return its ID.

        Args:
            name: Trace name (e.g., "GEO Search Pipeline")
            user_id: User identifier (e.g., email, user ID)
            session_id: Session identifier for grouping related traces
            metadata: Additional metadata (e.g., query_spec, filters)
            tags: Tags for filtering (e.g., ["production", "geo", "curation"])
            trace_id: Optional trace ID (auto-generated if not provided)

        Returns:
            Trace ID if enabled, None otherwise
        """
        if not self.enabled or not self._client:
            return None

        try:
            # Generate trace ID if not provided
            if not trace_id:
                trace_id = str(uuid.uuid4())

            # Create trace using the low-level API
            # LangFuse v2+ uses event() method for trace creation
            self._client.create_event(
                trace_id=trace_id,
                name=name,
                user_id=user_id,
                session_id=session_id,
                metadata=metadata or {},
            )

            return trace_id
        except Exception as e:
            logger.error(f"Failed to create trace: {e}")
            return None

    @contextmanager
    def trace(
        self,
        name: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
    ):
        """Context manager for creating and managing a trace.

        Usage:
            with langfuse_client.trace(name="My Pipeline", user_id="user@example.com") as trace_id:
                # Your code here with trace_id
                pass

        Args:
            name: Trace name
            user_id: User identifier
            session_id: Session identifier
            metadata: Additional metadata
            tags: Tags for filtering

        Yields:
            Trace ID string or None
        """
        trace_id = self.create_trace(
            name=name,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
            tags=tags,
        )

        try:
            yield trace_id
        except Exception as e:
            if trace_id:
                # Log the error as an event
                self.create_event(
                    trace_id=trace_id,
                    name="Error",
                    metadata={
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
            raise
        finally:
            if self._client:
                self._client.flush()

    def create_generation(
        self,
        trace_id: str,
        name: str,
        model: str,
        prompt: Optional[str | list[dict[str, Any]]] = None,
        completion: Optional[str] = None,
        usage: Optional[dict[str, int]] = None,
        metadata: Optional[dict[str, Any]] = None,
        parent_observation_id: Optional[str] = None,
    ) -> Optional[str]:
        """Create a generation (LLM call) observation.

        Args:
            trace_id: Parent trace ID
            name: Generation name (e.g., "Query Generation")
            model: Model identifier (e.g., "claude-sonnet-4-5")
            prompt: Prompt sent to LLM (string or messages array)
            completion: LLM completion/response
            usage: Token usage dict (input, output, cache_read, cache_write)
            metadata: Additional metadata (e.g., temperature, max_tokens)
            parent_observation_id: Parent span/generation ID for nesting

        Returns:
            Generation ID if enabled, None otherwise
        """
        if not self.enabled or not self._client:
            return None

        try:
            # Use start_as_current_generation for the low-level API
            generation_id = str(uuid.uuid4())

            # Convert usage to LangFuse format
            langfuse_usage = None
            if usage:
                langfuse_usage = {
                    "input": usage.get("input", 0),
                    "output": usage.get("output", 0),
                    "total": usage.get("input", 0) + usage.get("output", 0),
                }
                # Add cache tokens if present
                if "cache_read" in usage:
                    langfuse_usage["cache_read"] = usage["cache_read"]
                if "cache_write" in usage:
                    langfuse_usage["cache_write"] = usage["cache_write"]

            # Create generation using low-level API
            span = self._client.start_generation(
                trace_id=trace_id,
                name=name,
                model=model,
                input=prompt,
                metadata=metadata,
            )

            # Update with output and usage
            if span:
                if completion:
                    span.output = completion
                if langfuse_usage:
                    span.usage = langfuse_usage
                span.end()

            return generation_id
        except Exception as e:
            logger.error(f"Failed to create generation: {e}", exc_info=True)
            # Silently continue if LangFuse fails - don't break the application
            return None

    def create_span(
        self,
        trace_id: str,
        name: str,
        input: Optional[Any] = None,
        output: Optional[Any] = None,
        metadata: Optional[dict[str, Any]] = None,
        parent_observation_id: Optional[str] = None,
    ) -> Optional[str]:
        """Create a span (custom operation) observation.

        Args:
            trace_id: Parent trace ID
            name: Span name (e.g., "NCBI Search", "Ontology Mapping")
            input: Operation input data
            output: Operation output data
            metadata: Additional metadata
            parent_observation_id: Parent span/generation ID for nesting

        Returns:
            Span ID if enabled, None otherwise
        """
        if not self.enabled or not self._client:
            return None

        try:
            span_id = str(uuid.uuid4())

            # Create span using low-level API
            span = self._client.start_span(
                trace_id=trace_id,
                name=name,
                input=input,
                metadata=metadata,
            )

            # Update with output and end
            if span:
                if output:
                    span.output = output
                span.end()

            return span_id
        except Exception as e:
            logger.error(f"Failed to create span: {e}", exc_info=True)
            return None

    @contextmanager
    def span(
        self,
        trace_id: str,
        name: str,
        metadata: Optional[dict[str, Any]] = None,
        parent_observation_id: Optional[str] = None,
    ):
        """Context manager for creating and managing a span.

        Usage:
            with langfuse_client.span(trace_id=trace_id, name="NCBI Search"):
                results = ncbi_search(query)

        Args:
            trace_id: Parent trace ID
            name: Span name
            metadata: Additional metadata
            parent_observation_id: Parent observation ID

        Yields:
            Span ID or None
        """
        span_id = self.create_span(
            trace_id=trace_id,
            name=name,
            metadata=metadata,
            parent_observation_id=parent_observation_id,
        )

        try:
            yield span_id
        except Exception as e:
            if span_id:
                self.create_event(
                    trace_id=trace_id,
                    name="Span Error",
                    metadata={
                        "span_name": name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
            raise

    def create_event(
        self,
        trace_id: str,
        name: str,
        metadata: Optional[dict[str, Any]] = None,
        parent_observation_id: Optional[str] = None,
    ) -> None:
        """Create an event (milestone or checkpoint).

        Args:
            trace_id: Parent trace ID
            name: Event name (e.g., "Cache Hit", "Rate Limit", "Retry")
            metadata: Additional metadata
            parent_observation_id: Parent observation ID
        """
        if not self.enabled or not self._client:
            return

        try:
            self._client.create_event(
                trace_id=trace_id,
                name=name,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Failed to create event: {e}")

    def score(
        self,
        trace_id: str,
        name: str,
        value: float,
        comment: Optional[str] = None,
        observation_id: Optional[str] = None,
    ) -> None:
        """Add a score to a trace or observation.

        Args:
            trace_id: Parent trace ID
            name: Score name (e.g., "result_quality", "user_rating")
            value: Score value (numeric)
            comment: Optional comment explaining the score
            observation_id: Optional observation ID to score specific generation/span
        """
        if not self.enabled or not self._client:
            return

        try:
            self._client.create_score(
                trace_id=trace_id,
                name=name,
                value=value,
                comment=comment,
                observation_id=observation_id,
            )
        except Exception as e:
            logger.error(f"Failed to create score: {e}")

    def flush(self) -> None:
        """Flush all pending traces to the server."""
        if self._client:
            try:
                self._client.flush()
            except Exception as e:
                logger.error(f"Failed to flush traces: {e}")

    def shutdown(self) -> None:
        """Shutdown the client and flush all pending traces."""
        if self._client:
            try:
                self._client.shutdown()
                logger.info("LangFuse client shutdown successfully")
            except Exception as e:
                logger.error(f"Failed to shutdown LangFuse client: {e}")


# Global singleton instance
_langfuse_client: Optional[QurationLangFuseClient] = None


def get_langfuse_client() -> Optional[QurationLangFuseClient]:
    """Get the global LangFuse client instance.

    Returns:
        QurationLangFuseClient instance or None if not initialized
    """
    return _langfuse_client


def initialize_langfuse(config: LangFuseConfig) -> QurationLangFuseClient:
    """Initialize the global LangFuse client.

    Args:
        config: LangFuse configuration

    Returns:
        QurationLangFuseClient instance
    """
    global _langfuse_client
    _langfuse_client = QurationLangFuseClient(config)
    return _langfuse_client
