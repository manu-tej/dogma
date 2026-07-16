"""Metrics collection for quration platform using Prometheus."""

import logging
from typing import Any, Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    start_http_server,
)

from .config import MetricsConfig

logger = logging.getLogger(__name__)


class QurationMetrics:
    """Centralized metrics collection for quration platform."""

    def __init__(self, config: MetricsConfig) -> None:
        """Initialize metrics collectors.

        Args:
            config: Metrics configuration
        """
        self.config = config
        self._enabled = config.enabled
        self._setup_metrics()

    def _setup_metrics(self) -> None:
        """Set up all Prometheus metrics."""
        # Application info
        self.app_info = Info("quration_app", "Quration application information")
        self.app_info.info({"version": "0.1.0", "service": "quration"})

        # LLM Metrics
        self.llm_requests_total = Counter(
            "quration_llm_requests_total",
            "Total number of LLM requests",
            ["model", "provider", "status"],
        )

        self.llm_tokens_total = Counter(
            "quration_llm_tokens_total",
            "Total tokens consumed",
            ["model", "type"],  # type: input, output, cache_read, cache_write
        )

        self.llm_cost_total = Counter(
            "quration_llm_cost_usd_total",
            "Total LLM cost in USD",
            ["model", "provider"],
        )

        self.llm_latency_seconds = Histogram(
            "quration_llm_latency_seconds",
            "LLM request duration in seconds",
            ["model", "provider"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
        )

        self.llm_cache_hits_total = Counter(
            "quration_llm_cache_hits_total",
            "Total LLM cache hits",
            ["model"],
        )

        self.llm_cache_misses_total = Counter(
            "quration_llm_cache_misses_total",
            "Total LLM cache misses",
            ["model"],
        )

        # Pipeline Metrics
        self.pipeline_executions_total = Counter(
            "quration_pipeline_executions_total",
            "Total pipeline executions",
            ["pipeline_type", "status"],
        )

        self.pipeline_duration_seconds = Histogram(
            "quration_pipeline_duration_seconds",
            "Pipeline execution duration in seconds",
            ["pipeline_type", "stage"],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
        )

        self.pipeline_results_count = Histogram(
            "quration_pipeline_results_count",
            "Number of results returned by pipeline",
            ["pipeline_type"],
            buckets=[0, 1, 5, 10, 25, 50, 100, 500],
        )

        # Hypothesis Metrics
        self.hypothesis_ops_total = Counter(
            "quration_hypothesis_ops_total",
            "Hypothesis operations",
            ["op", "status"],
        )

        self.hypothesis_op_latency = Histogram(
            "quration_hypothesis_op_latency_seconds",
            "Hypothesis op latency",
            ["op"],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
        )

        # API Metrics
        self.http_requests_total = Counter(
            "quration_http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status_code"],
        )

        self.http_request_duration_seconds = Histogram(
            "quration_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
        )

        self.http_request_size_bytes = Histogram(
            "quration_http_request_size_bytes",
            "HTTP request size in bytes",
            ["method", "endpoint"],
            buckets=[100, 1000, 10000, 100000, 1000000],
        )

        self.http_response_size_bytes = Histogram(
            "quration_http_response_size_bytes",
            "HTTP response size in bytes",
            ["method", "endpoint"],
            buckets=[100, 1000, 10000, 100000, 1000000],
        )

        # Data Source Metrics
        self.ncbi_requests_total = Counter(
            "quration_ncbi_requests_total",
            "Total NCBI API requests",
            ["endpoint", "status"],
        )

        self.ncbi_rate_limit_remaining = Gauge(
            "quration_ncbi_rate_limit_remaining",
            "Remaining NCBI rate limit quota",
        )

        self.ontology_requests_total = Counter(
            "quration_ontology_requests_total",
            "Total ontology API requests",
            ["ontology", "status"],
        )

        self.ontology_cache_hits_total = Counter(
            "quration_ontology_cache_hits_total",
            "Total ontology cache hits",
            ["ontology"],
        )

        # Error Metrics
        self.errors_total = Counter(
            "quration_errors_total",
            "Total errors",
            ["component", "error_type"],
        )

        logger.info("Metrics collectors initialized")

    def start_prometheus_server(self) -> None:
        """Start Prometheus metrics HTTP server."""
        if not self._enabled or self.config.backend != "prometheus":
            return

        try:
            start_http_server(self.config.prometheus_port)
            logger.info(f"Prometheus metrics server started on port {self.config.prometheus_port}")
        except Exception as e:
            logger.error(f"Failed to start Prometheus metrics server: {e}")

    def get_metrics(self) -> bytes:
        """Get current metrics in Prometheus format.

        Returns:
            Metrics in Prometheus text format
        """
        return generate_latest()

    # LLM Metric Recording Methods
    def record_llm_request(
        self,
        model: str,
        provider: str,
        status: str = "success",
        latency: Optional[float] = None,
        tokens: Optional[dict[str, int]] = None,
        cost: Optional[float] = None,
        cache_hit: bool = False,
    ) -> None:
        """Record LLM request metrics.

        Args:
            model: Model name (e.g., "claude-sonnet-4-5")
            provider: Provider name (e.g., "anthropic")
            status: Request status ("success" or "error")
            latency: Request latency in seconds
            tokens: Token usage dict (input, output, cache_read, cache_write)
            cost: Request cost in USD
            cache_hit: Whether cache was hit
        """
        if not self._enabled:
            return

        # Record request
        self.llm_requests_total.labels(model=model, provider=provider, status=status).inc()

        # Record latency
        if latency is not None:
            self.llm_latency_seconds.labels(model=model, provider=provider).observe(latency)

        # Record tokens
        if tokens:
            for token_type, count in tokens.items():
                self.llm_tokens_total.labels(model=model, type=token_type).inc(count)

        # Record cost
        if cost is not None:
            self.llm_cost_total.labels(model=model, provider=provider).inc(cost)

        # Record cache hits/misses
        if cache_hit:
            self.llm_cache_hits_total.labels(model=model).inc()
        else:
            self.llm_cache_misses_total.labels(model=model).inc()

    # Pipeline Metric Recording Methods
    def record_pipeline_execution(
        self,
        pipeline_type: str,
        status: str = "success",
        duration: Optional[float] = None,
        stage_durations: Optional[dict[str, float]] = None,
        result_count: Optional[int] = None,
    ) -> None:
        """Record pipeline execution metrics.

        Args:
            pipeline_type: Pipeline type (e.g., "geo_search")
            status: Execution status ("success" or "error")
            duration: Total execution duration in seconds
            stage_durations: Duration of each stage in seconds
            result_count: Number of results returned
        """
        if not self._enabled:
            return

        # Record execution
        self.pipeline_executions_total.labels(pipeline_type=pipeline_type, status=status).inc()

        # Record duration
        if duration is not None:
            self.pipeline_duration_seconds.labels(
                pipeline_type=pipeline_type, stage="total"
            ).observe(duration)

        # Record stage durations
        if stage_durations:
            for stage, stage_duration in stage_durations.items():
                self.pipeline_duration_seconds.labels(
                    pipeline_type=pipeline_type, stage=stage
                ).observe(stage_duration)

        # Record result count
        if result_count is not None:
            self.pipeline_results_count.labels(pipeline_type=pipeline_type).observe(result_count)

    # Hypothesis Metric Recording Methods
    def record_hypothesis_op(
        self, op: str, status: str, latency_seconds: float = 0.0
    ) -> None:
        """Record a hypothesis operation.

        Args:
            op: Operation name (e.g., "seed", "ground", "save")
            status: Operation status (e.g., "ok", "not_found", "error")
            latency_seconds: Operation latency in seconds (0.0 to skip)
        """
        if not self._enabled:
            return

        self.hypothesis_ops_total.labels(op=op, status=status).inc()

        if latency_seconds:
            self.hypothesis_op_latency.labels(op=op).observe(latency_seconds)

    # API Metric Recording Methods
    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        duration: Optional[float] = None,
        request_size: Optional[int] = None,
        response_size: Optional[int] = None,
    ) -> None:
        """Record HTTP request metrics.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            status_code: HTTP status code
            duration: Request duration in seconds
            request_size: Request body size in bytes
            response_size: Response body size in bytes
        """
        if not self._enabled:
            return

        # Record request
        self.http_requests_total.labels(
            method=method, endpoint=endpoint, status_code=str(status_code)
        ).inc()

        # Record duration
        if duration is not None:
            self.http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(
                duration
            )

        # Record sizes
        if request_size is not None:
            self.http_request_size_bytes.labels(method=method, endpoint=endpoint).observe(
                request_size
            )
        if response_size is not None:
            self.http_response_size_bytes.labels(method=method, endpoint=endpoint).observe(
                response_size
            )

    # Data Source Metric Recording Methods
    def record_ncbi_request(
        self, endpoint: str, status: str = "success", rate_limit_remaining: Optional[int] = None
    ) -> None:
        """Record NCBI API request metrics.

        Args:
            endpoint: NCBI endpoint (e.g., "esearch", "efetch")
            status: Request status ("success" or "error")
            rate_limit_remaining: Remaining rate limit quota
        """
        if not self._enabled:
            return

        self.ncbi_requests_total.labels(endpoint=endpoint, status=status).inc()

        if rate_limit_remaining is not None:
            self.ncbi_rate_limit_remaining.set(rate_limit_remaining)

    def record_ontology_request(
        self, ontology: str, status: str = "success", cache_hit: bool = False
    ) -> None:
        """Record ontology API request metrics.

        Args:
            ontology: Ontology name (e.g., "efo", "uberon")
            status: Request status ("success" or "error")
            cache_hit: Whether cache was hit
        """
        if not self._enabled:
            return

        self.ontology_requests_total.labels(ontology=ontology, status=status).inc()

        if cache_hit:
            self.ontology_cache_hits_total.labels(ontology=ontology).inc()

    def record_error(self, component: str, error_type: str) -> None:
        """Record error metrics.

        Args:
            component: Component where error occurred (e.g., "llm_provider", "pipeline")
            error_type: Error type (e.g., "timeout", "rate_limit")
        """
        if not self._enabled:
            return

        self.errors_total.labels(component=component, error_type=error_type).inc()


# Global singleton instance
_metrics: Optional[QurationMetrics] = None


def get_metrics() -> Optional[QurationMetrics]:
    """Get the global metrics instance.

    Returns:
        QurationMetrics instance or None if not initialized
    """
    return _metrics


def initialize_metrics(config: MetricsConfig) -> QurationMetrics:
    """Initialize the global metrics instance.

    Args:
        config: Metrics configuration

    Returns:
        QurationMetrics instance
    """
    global _metrics
    _metrics = QurationMetrics(config)

    # Start Prometheus server if enabled
    if config.enabled and config.backend == "prometheus":
        _metrics.start_prometheus_server()

    return _metrics
