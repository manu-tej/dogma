"""Decoupled telemetry seam for hypothesis operations.

This module is the single place hypothesis code records "what happened" — it
defines the shared event/summary types AND the fan-out recording logic. Callers
depend only on :func:`record_event` / :func:`traced_op`; the heavy observability
backends (structured logging, Prometheus metrics, an event sink, LangFuse) are
reached best-effort and are individually fault-isolated.

Telemetry must NEVER raise into the caller: every backend write is wrapped in
its own try/except. A failing sink or an uninitialized metrics singleton degrades
to a logged warning, not an exception in the hypothesis pipeline.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Protocol, runtime_checkable

from pydantic import BaseModel

# --- Defensive cross-module imports -----------------------------------------
# These backends live in sibling packages and may be initialized lazily (or be
# mid-migration in a parallel task). Import them best-effort so this module is
# importable and usable even when they are absent.
try:  # structured logger trace context
    from quration.observability.structured_logger import get_trace_id
except Exception:  # pragma: no cover - defensive
    get_trace_id = None  # type: ignore[assignment]

try:  # Prometheus metrics singleton
    from quration.observability.metrics import get_metrics
except Exception:  # pragma: no cover - defensive
    get_metrics = None  # type: ignore[assignment]

try:  # LangFuse client singleton
    from quration.observability.langfuse_client import get_langfuse_client
except Exception:  # pragma: no cover - defensive
    get_langfuse_client = None  # type: ignore[assignment]

try:  # LLM call capture (added by a parallel task; may be None here)
    from quration.llm.providers import llm_capture_var
except ImportError:  # pragma: no cover - parallel task not merged
    llm_capture_var = None  # type: ignore[assignment]


logger = logging.getLogger("quration.hypothesis")

# Reserved LogRecord attribute names we must not collide with when using
# ``extra={...}`` (Python raises KeyError otherwise).
_RESERVED_LOG_KEYS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
    "asctime",
    "taskName",
}


# --- Shared types ------------------------------------------------------------


class HypothesisEvent(BaseModel):
    """One recorded hypothesis operation, with optional raw LLM I/O for replay."""

    ts: str
    trace_id: str | None = None
    graph_id: str | None = None
    query: str | None = None
    op: str
    status: str  # "ok" | "error" | "not_found"
    latency_ms: float | None = None
    detail: dict | None = None
    raw_input: str | None = None
    raw_output: str | None = None
    error: str | None = None


class GraphSummary(BaseModel):
    """Lightweight summary of a persisted hypothesis graph (for listings)."""

    id: str
    query: str
    status: str
    created_at: str
    updated_at: str
    n_nodes: int
    n_edges: int


@runtime_checkable
class EventSink(Protocol):
    """A durable target for :class:`HypothesisEvent` records."""

    def append_event(self, event: HypothesisEvent) -> None: ...


# --- Sink registry -----------------------------------------------------------

_event_sink: EventSink | None = None


def set_event_sink(sink: EventSink | None) -> None:
    """Register (or clear) the process-wide event sink."""
    global _event_sink
    _event_sink = sink


def get_event_sink() -> EventSink | None:
    """Return the registered event sink, or ``None``."""
    return _event_sink


# --- Clock (monkeypatchable in tests) ---------------------------------------


def _now() -> str:
    """Current UTC timestamp as an ISO-8601 string. Tests may monkeypatch this."""
    return datetime.now(timezone.utc).isoformat()


# --- Recording ---------------------------------------------------------------


def record_event(
    op: str,
    *,
    status: str = "ok",
    graph_id: str | None = None,
    query: str | None = None,
    detail: dict | None = None,
    raw_input: str | None = None,
    raw_output: str | None = None,
    latency_ms: float | None = None,
    error: str | None = None,
) -> HypothesisEvent:
    """Build a :class:`HypothesisEvent` and fan it out to all telemetry targets.

    Each target is fault-isolated: a failure in one (e.g. a raising sink, an
    uninitialized metrics singleton) is logged and skipped, never propagated.

    Returns the constructed event so callers can inspect/forward it.
    """
    trace_id: str | None = None
    if get_trace_id is not None:
        try:
            trace_id = get_trace_id()
        except Exception:  # pragma: no cover - defensive
            trace_id = None

    event = HypothesisEvent(
        ts=_now(),
        trace_id=trace_id,
        graph_id=graph_id,
        query=query,
        op=op,
        status=status,
        latency_ms=latency_ms,
        detail=detail,
        raw_input=raw_input,
        raw_output=raw_output,
        error=error,
    )

    # (a) Structured logger -------------------------------------------------
    try:
        extra = {f"hyp_{k}": v for k, v in event.model_dump().items() if k not in _RESERVED_LOG_KEYS}
        log = logger.warning if status == "error" else logger.info
        log("hypothesis op %s status=%s", op, status, extra=extra)
    except Exception:  # pragma: no cover - defensive
        logger.debug("hypothesis structured-log emit failed", exc_info=True)

    # (b) Metrics -----------------------------------------------------------
    try:
        metrics = get_metrics() if get_metrics is not None else None
        if metrics and hasattr(metrics, "record_hypothesis_op"):
            metrics.record_hypothesis_op(op, status, (latency_ms or 0) / 1000.0)
    except Exception:
        logger.warning("hypothesis metrics emit failed", exc_info=True)

    # (c) Event sink --------------------------------------------------------
    try:
        sink = get_event_sink()
        if sink is not None:
            sink.append_event(event)
    except Exception:
        logger.warning("hypothesis event-sink append failed", exc_info=True)

    # (d) LangFuse ----------------------------------------------------------
    # Events attach to the request's trace (created by ObservabilityMiddleware
    # with this same trace_id). With no trace context there is nothing to attach
    # to, so skip rather than orphan an event.
    try:
        client = get_langfuse_client() if get_langfuse_client is not None else None
        if client and event.trace_id:
            client.create_event(
                trace_id=event.trace_id,
                name=f"hypothesis.{op}",
                metadata=event.model_dump(),
            )
    except Exception:
        logger.warning("hypothesis langfuse emit failed", exc_info=True)

    return event


# --- Traced operation context manager ---------------------------------------


class _OpHandle:
    """Mutable handle yielded by :func:`traced_op` so callers can enrich the event."""

    def __init__(self, *, graph_id: str | None = None, query: str | None = None) -> None:
        self.detail: dict | None = None
        self.status: str | None = None
        self.graph_id: str | None = graph_id
        self.query: str | None = query


def _join_captured(captured: list | None) -> tuple[str | None, str | None]:
    """Collapse captured LLM calls into (raw_input, raw_output) blobs.

    Each captured item is a dict that may carry ``system``/``prompt`` (input
    side) and ``response`` (output side). Returns ``(None, None)`` when nothing
    meaningful was captured.
    """
    if not captured:
        return None, None

    inputs: list[str] = []
    outputs: list[str] = []
    for item in captured:
        if not isinstance(item, dict):
            outputs.append(str(item))
            continue
        system = item.get("system")
        prompt = item.get("prompt")
        if system:
            inputs.append(f"System: {system}")
        if prompt:
            inputs.append(str(prompt))
        response = item.get("response")
        if response:
            outputs.append(str(response))

    raw_input = "\n\n".join(inputs) if inputs else None
    raw_output = "\n\n".join(outputs) if outputs else None
    return raw_input, raw_output


@contextmanager
def traced_op(
    op: str,
    *,
    graph_id: str | None = None,
    query: str | None = None,
) -> Iterator[_OpHandle]:
    """Time a hypothesis operation and emit exactly one event on exit.

    Yields a mutable :class:`_OpHandle`; the caller may set ``handle.detail``,
    ``handle.status`` (e.g. ``"not_found"``), ``handle.graph_id`` or
    ``handle.query`` before the block exits. Any LLM calls captured via
    ``llm_capture_var`` during the block are attached as ``raw_input`` /
    ``raw_output``.

    On a raised exception the event is recorded with ``status="error"`` and the
    exception is re-raised (never swallowed).
    """
    handle = _OpHandle(graph_id=graph_id, query=query)
    start = time.perf_counter()

    token = None
    if llm_capture_var is not None:
        token = llm_capture_var.set([])

    try:
        yield handle
    except Exception as exc:
        latency_ms = (time.perf_counter() - start) * 1000.0
        captured = llm_capture_var.get() if llm_capture_var is not None else None
        raw_input, raw_output = _join_captured(captured)
        record_event(
            op,
            status="error",
            graph_id=handle.graph_id or graph_id,
            query=handle.query or query,
            detail=handle.detail,
            raw_input=raw_input,
            raw_output=raw_output,
            latency_ms=latency_ms,
            error=repr(exc),
        )
        raise
    else:
        latency_ms = (time.perf_counter() - start) * 1000.0
        captured = llm_capture_var.get() if llm_capture_var is not None else None
        raw_input, raw_output = _join_captured(captured)
        record_event(
            op,
            status=handle.status or "ok",
            graph_id=handle.graph_id or graph_id,
            query=handle.query or query,
            detail=handle.detail,
            raw_input=raw_input,
            raw_output=raw_output,
            latency_ms=latency_ms,
        )
    finally:
        if token is not None and llm_capture_var is not None:
            llm_capture_var.reset(token)
