"""Tests for the hypothesis observability telemetry seam."""

from __future__ import annotations

import contextvars

import pytest

from quration.hypothesis import observability as obs
from quration.hypothesis.observability import (
    HypothesisEvent,
    record_event,
    set_event_sink,
    traced_op,
)


class _ListSink:
    """In-memory EventSink that just collects events into a list."""

    def __init__(self) -> None:
        self.events: list[HypothesisEvent] = []

    def append_event(self, event: HypothesisEvent) -> None:
        self.events.append(event)


class _RaisingSink:
    """EventSink whose append_event always blows up (to test best-effort)."""

    def append_event(self, event: HypothesisEvent) -> None:
        raise RuntimeError("sink exploded")


@pytest.fixture(autouse=True)
def _reset_sink():
    """Ensure each test starts and ends with a clean sink registry."""
    set_event_sink(None)
    yield
    set_event_sink(None)


def test_record_event_populates_ts_and_reaches_sink():
    sink = _ListSink()
    set_event_sink(sink)

    event = record_event("seed", status="ok", graph_id="g1", query="why?")

    assert len(sink.events) == 1
    captured = sink.events[0]
    assert captured is event
    assert event.op == "seed"
    assert event.status == "ok"
    assert event.graph_id == "g1"
    assert event.query == "why?"
    assert isinstance(event.ts, str) and event.ts  # populated, non-empty
    # trace_id is best-effort; it is either None or a string, never raises.
    assert event.trace_id is None or isinstance(event.trace_id, str)


def test_record_event_is_best_effort_when_sink_raises():
    set_event_sink(_RaisingSink())

    # Must NOT propagate the sink's RuntimeError.
    event = record_event("expand", status="ok")

    assert isinstance(event, HypothesisEvent)
    assert event.op == "expand"


def test_traced_op_success_emits_ok_with_latency():
    sink = _ListSink()
    set_event_sink(sink)

    with traced_op("grow", graph_id="g2", query="q2") as handle:
        handle.detail = {"n": 3}

    assert len(sink.events) == 1
    event = sink.events[0]
    assert event.op == "grow"
    assert event.status == "ok"
    assert event.graph_id == "g2"
    assert event.query == "q2"
    assert event.detail == {"n": 3}
    assert event.latency_ms is not None and event.latency_ms >= 0.0


def test_traced_op_caller_can_override_status_not_found():
    sink = _ListSink()
    set_event_sink(sink)

    with traced_op("lookup", graph_id="g3") as handle:
        handle.status = "not_found"

    assert len(sink.events) == 1
    assert sink.events[0].status == "not_found"


def test_traced_op_error_emits_error_and_reraises():
    sink = _ListSink()
    set_event_sink(sink)

    with pytest.raises(ValueError, match="boom"):
        with traced_op("grow", graph_id="g4"):
            raise ValueError("boom")

    assert len(sink.events) == 1
    event = sink.events[0]
    assert event.status == "error"
    assert event.error is not None and "boom" in event.error
    assert event.latency_ms is not None


def test_traced_op_captures_llm_io(monkeypatch):
    sink = _ListSink()
    set_event_sink(sink)

    # Install a local ContextVar so the capture/join logic is exercised even
    # if the parallel llm_capture_var task is not merged into this tree.
    capture_var: contextvars.ContextVar[list | None] = contextvars.ContextVar(
        "test_llm_capture", default=None
    )
    monkeypatch.setattr(obs, "llm_capture_var", capture_var)

    with traced_op("grow", graph_id="g5"):
        captured = capture_var.get()
        assert captured is not None  # traced_op should have set a fresh list
        captured.append(
            {
                "system": "you are a bio assistant",
                "prompt": "hypothesize about gene X",
                "response": "X may regulate Y",
            }
        )

    assert len(sink.events) == 1
    event = sink.events[0]
    assert event.raw_input is not None
    assert "you are a bio assistant" in event.raw_input
    assert "hypothesize about gene X" in event.raw_input
    assert event.raw_output is not None
    assert "X may regulate Y" in event.raw_output


def test_record_event_uses_monkeypatched_now(monkeypatch):
    sink = _ListSink()
    set_event_sink(sink)

    monkeypatch.setattr(obs, "_now", lambda: "2026-06-08T00:00:00+00:00")

    event = record_event("seed")

    assert event.ts == "2026-06-08T00:00:00+00:00"
