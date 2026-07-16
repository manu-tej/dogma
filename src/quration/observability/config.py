"""Observability configuration for quration platform."""

from typing import Literal

from pydantic import BaseModel, Field


class LangFuseConfig(BaseModel):
    """LangFuse configuration for LLM observability."""

    enabled: bool = Field(
        default=True,
        description="Enable LangFuse tracing",
    )
    host: str = Field(
        default="https://cloud.langfuse.com",
        description="LangFuse server URL (cloud or self-hosted)",
    )
    public_key: str = Field(
        default="",
        description="LangFuse public API key",
    )
    secret_key: str = Field(
        default="",
        description="LangFuse secret API key",
    )
    environment: str = Field(
        default="production",
        description="Environment name for trace grouping",
    )
    sample_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Sampling rate for traces (0.0 to 1.0)",
    )
    flush_interval: int = Field(
        default=5,
        description="Interval in seconds to flush traces to server",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug logging for LangFuse",
    )
    release: str = Field(
        default="",
        description="Release version for trace grouping",
    )


class StructuredLoggingConfig(BaseModel):
    """Structured logging configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable structured logging",
    )
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
    )
    format: Literal["json", "rich", "simple"] = Field(
        default="json",
        description="Log format (json for production, rich for development)",
    )
    file_path: str = Field(
        default="./logs/quration.log",
        description="Log file path",
    )
    rotation: str = Field(
        default="1 day",
        description="Log rotation interval (e.g., '1 day', '100 MB')",
    )
    retention: str = Field(
        default="30 days",
        description="Log retention period",
    )
    include_trace_id: bool = Field(
        default=True,
        description="Include trace ID in log records",
    )
    redact_pii: bool = Field(
        default=True,
        description="Automatically redact PII from logs",
    )


class MetricsConfig(BaseModel):
    """Metrics collection configuration."""

    enabled: bool = Field(
        default=True,
        description="Enable metrics collection",
    )
    backend: Literal["prometheus", "in_memory"] = Field(
        default="in_memory",
        description="Metrics backend (prometheus for scraping, in_memory for API export)",
    )
    export_interval: int = Field(
        default=60,
        description="Metrics export interval in seconds",
    )
    retention_days: int = Field(
        default=7,
        description="Metrics retention in days",
    )
    prometheus_port: int = Field(
        default=8001,
        description="Prometheus metrics endpoint port",
    )


class ObservabilityConfig(BaseModel):
    """Observability and monitoring configuration."""

    enabled: bool = Field(
        default=True,
        description="Master switch for observability features",
    )
    langfuse: LangFuseConfig = Field(
        default_factory=LangFuseConfig,
        description="LangFuse configuration",
    )
    logging: StructuredLoggingConfig = Field(
        default_factory=StructuredLoggingConfig,
        description="Structured logging configuration",
    )
    metrics: MetricsConfig = Field(
        default_factory=MetricsConfig,
        description="Metrics configuration",
    )
    trace_sensitive_data: bool = Field(
        default=False,
        description="Include sensitive data (prompts, responses) in traces",
    )
    auto_instrument: bool = Field(
        default=True,
        description="Automatically instrument LLM calls and pipelines",
    )

    class Config:
        """Pydantic configuration."""

        env_prefix = "QURATION_OBSERVABILITY_"
        case_sensitive = False
