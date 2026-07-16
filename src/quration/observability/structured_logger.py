"""Structured logging setup for quration platform."""

import contextvars
import logging
import re
import sys
from pathlib import Path
from typing import Any, Optional

from pythonjsonlogger import jsonlogger
from rich.logging import RichHandler

from .config import StructuredLoggingConfig

# Context variable for trace ID
trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "trace_id", default=None
)
span_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("span_id", default=None)
user_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "user_id", default=None
)

# PII patterns for redaction
PII_PATTERNS = [
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b\d{16}\b"), "[CREDIT_CARD]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP_ADDRESS]"),
]


class QurationJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with trace ID and PII redaction."""

    def __init__(
        self,
        *args: Any,
        include_trace_id: bool = True,
        redact_pii: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize the formatter.

        Args:
            include_trace_id: Whether to include trace ID in logs
            redact_pii: Whether to redact PII from logs
            *args: Positional arguments for JsonFormatter
            **kwargs: Keyword arguments for JsonFormatter
        """
        super().__init__(*args, **kwargs)
        self.include_trace_id = include_trace_id
        self.redact_pii = redact_pii

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        """Add custom fields to log record.

        Args:
            log_record: Dictionary to add fields to
            record: Original LogRecord
            message_dict: Message dictionary
        """
        super().add_fields(log_record, record, message_dict)

        # Add timestamp
        log_record["timestamp"] = self.formatTime(record, self.datefmt)

        # Add trace context
        if self.include_trace_id:
            trace_id = trace_id_var.get()
            span_id = span_id_var.get()
            user_id = user_id_var.get()

            if trace_id:
                log_record["trace_id"] = trace_id
            if span_id:
                log_record["span_id"] = span_id
            if user_id:
                log_record["user_id"] = user_id

        # Add service info
        log_record["service"] = "quration"
        log_record["logger"] = record.name

        # Redact PII if enabled
        if self.redact_pii:
            self._redact_pii_from_dict(log_record)

    def _redact_pii_from_dict(self, data: dict[str, Any]) -> None:
        """Recursively redact PII from dictionary.

        Args:
            data: Dictionary to redact PII from
        """
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = self._redact_pii(value)
            elif isinstance(value, dict):
                self._redact_pii_from_dict(value)
            elif isinstance(value, list):
                data[key] = [
                    self._redact_pii(item) if isinstance(item, str) else item for item in value
                ]

    def _redact_pii(self, text: str) -> str:
        """Redact PII from text.

        Args:
            text: Text to redact PII from

        Returns:
            Redacted text
        """
        for pattern, replacement in PII_PATTERNS:
            text = pattern.sub(replacement, text)
        return text


def setup_structured_logging(config: StructuredLoggingConfig) -> None:
    """Set up structured logging for the application.

    Args:
        config: Structured logging configuration
    """
    # Create logs directory if it doesn't exist
    log_file = Path(config.file_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add console handler
    if config.format == "rich":
        # Rich handler for beautiful terminal output
        console_handler = RichHandler(
            rich_tracebacks=True,
            show_time=True,
            show_path=True,
            markup=True,
        )
        console_handler.setLevel(getattr(logging, config.level))
        root_logger.addHandler(console_handler)
    elif config.format == "json":
        # JSON handler for production
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.level))
        json_formatter = QurationJsonFormatter(
            fmt="%(levelname)s %(name)s %(message)s",
            include_trace_id=config.include_trace_id,
            redact_pii=config.redact_pii,
        )
        console_handler.setFormatter(json_formatter)
        root_logger.addHandler(console_handler)
    else:
        # Simple handler for basic logging
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.level))
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # Add file handler with JSON format
    if config.enabled:
        file_handler = logging.FileHandler(config.file_path)
        file_handler.setLevel(getattr(logging, config.level))
        json_formatter = QurationJsonFormatter(
            fmt="%(levelname)s %(name)s %(message)s",
            include_trace_id=config.include_trace_id,
            redact_pii=config.redact_pii,
        )
        file_handler.setFormatter(json_formatter)
        root_logger.addHandler(file_handler)

    # Log initial message
    root_logger.info(
        f"Structured logging initialized: level={config.level}, format={config.format}"
    )


def set_trace_context(
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> None:
    """Set trace context for logging.

    Args:
        trace_id: Trace ID from LangFuse
        span_id: Span ID from LangFuse
        user_id: User identifier
    """
    if trace_id:
        trace_id_var.set(trace_id)
    if span_id:
        span_id_var.set(span_id)
    if user_id:
        user_id_var.set(user_id)


def clear_trace_context() -> None:
    """Clear trace context."""
    trace_id_var.set(None)
    span_id_var.set(None)
    user_id_var.set(None)


def get_trace_id() -> Optional[str]:
    """Get current trace ID from context.

    Returns:
        Current trace ID or None
    """
    return trace_id_var.get()


def get_span_id() -> Optional[str]:
    """Get current span ID from context.

    Returns:
        Current span ID or None
    """
    return span_id_var.get()


def get_user_id() -> Optional[str]:
    """Get current user ID from context.

    Returns:
        Current user ID or None
    """
    return user_id_var.get()
