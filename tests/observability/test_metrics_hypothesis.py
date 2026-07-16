"""Tests for QurationMetrics.record_hypothesis_op."""

import pytest
from prometheus_client import REGISTRY, CollectorRegistry

from quration.observability.config import MetricsConfig
from quration.observability.metrics import QurationMetrics


@pytest.fixture(autouse=True)
def _clean_registry():
    """Isolate each test from the shared default Prometheus registry.

    QurationMetrics registers its collectors on the default REGISTRY at
    construction time, so re-instantiating it within a test session would
    raise "Duplicated timeseries". We snapshot the collectors, let the test
    run, then restore the registry to its original state.
    """
    saved = list(REGISTRY._collector_to_names.keys())
    yield
    for collector in list(REGISTRY._collector_to_names.keys()):
        if collector not in saved:
            REGISTRY.unregister(collector)


def _counter_value(metrics: QurationMetrics, op: str, status: str) -> float:
    """Read the current value of the hypothesis ops counter for given labels."""
    return (
        metrics.hypothesis_ops_total.labels(op=op, status=status)._value.get()
    )


def test_record_hypothesis_op_enabled_increments_counter():
    config = MetricsConfig(enabled=True)
    metrics = QurationMetrics(config)

    metrics.record_hypothesis_op("seed", "ok", 0.5)
    metrics.record_hypothesis_op("ground", "not_found")

    assert _counter_value(metrics, "seed", "ok") == 1.0
    assert _counter_value(metrics, "ground", "not_found") == 1.0

    # Latency histogram observed for the call that supplied a latency.
    seed_hist = metrics.hypothesis_op_latency.labels(op="seed")
    assert seed_hist._sum.get() == pytest.approx(0.5)


def test_record_hypothesis_op_accumulates():
    config = MetricsConfig(enabled=True)
    metrics = QurationMetrics(config)

    metrics.record_hypothesis_op("seed", "ok", 0.1)
    metrics.record_hypothesis_op("seed", "ok", 0.2)

    assert _counter_value(metrics, "seed", "ok") == 2.0
    assert metrics.hypothesis_op_latency.labels(op="seed")._sum.get() == pytest.approx(0.3)


def test_record_hypothesis_op_zero_latency_skips_histogram():
    config = MetricsConfig(enabled=True)
    metrics = QurationMetrics(config)

    metrics.record_hypothesis_op("ground", "ok")  # default latency 0.0

    assert _counter_value(metrics, "ground", "ok") == 1.0
    # No observation recorded when latency is falsy.
    assert metrics.hypothesis_op_latency.labels(op="ground")._sum.get() == 0.0


def test_record_hypothesis_op_disabled_is_noop():
    config = MetricsConfig(enabled=False)
    metrics = QurationMetrics(config)

    # Should not raise and should not touch metric state.
    metrics.record_hypothesis_op("seed", "ok", 0.5)
    metrics.record_hypothesis_op("ground", "not_found")

    assert _counter_value(metrics, "seed", "ok") == 0.0
    assert _counter_value(metrics, "ground", "not_found") == 0.0
