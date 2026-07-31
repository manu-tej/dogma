"""Tests for the real pipeline loop's method selector wiring.

The hardcoded Spearman correlation executor and CorrelationSupervisor.interpret
were removed in Task 10 (the runner is now methods-graph grounding only), so the
correlation runner/supervisor/end-to-end tests that used to live here are gone.
What remains is the advisory method-selector wiring, which is independent of the
runner and still valid.
"""

import pytest

from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
from quration.hypothesis.orchestrator.checkpoint import ProposedTest
from quration.hypothesis.orchestrator.real_pipeline import build_real_loop


@pytest.fixture
def live_provider(monkeypatch):
    """A constructible provider, so `build_real_loop` reaches the live path.

    These tests used to call `build_real_loop()` with no provider at all and get a
    loop back, because an unusable provider silently degraded to the demo seams.
    That fallback is gone, so the provider now has to be stubbed explicitly.

    Only the provider is stubbed — `MethodBroker` is left real, because the point
    of these tests is what the selector recommends from the actual registry.
    """
    monkeypatch.setattr(
        "quration.llm.providers.get_provider_from_config", lambda *a, **k: object()
    )
    monkeypatch.setattr(
        "quration.llm.providers.get_model_for_config", lambda *a, **k: "m"
    )


def _graph():
    g = CausalGraph(id="g", query="does EGFR drive KRAS?")
    g.add_node(Node(id="egfr", type=NodeType.TARGET, label="EGFR"))
    g.add_node(Node(id="kras", type=NodeType.TARGET, label="KRAS"))
    g.add_edge(Edge(id="e1", source_id="egfr", target_id="kras",
                    relation="up-regulates", pending=True))
    return g


def _proposed(**kw):
    base = dict(edge_id="e1", gap="g", pipeline="nf-core/differentialabundance",
                data_accession="GSE1", source_symbol="EGFR", target_symbol="KRAS",
                relation="up-regulates")
    base.update(kw)
    return ProposedTest(**base)


def test_build_real_loop_wires_a_method_selector(live_provider):
    from quration.hypothesis.orchestrator.method_selection import BrokerMethodSelector

    loop = build_real_loop()
    assert isinstance(loop._selector, BrokerMethodSelector)


def test_real_loop_selector_recommends_a_registry_method(live_provider):
    """The wired selector, on a gene-gene RNA-seq edge, recommends a real method
    from the broker (default registry, or methods-graph when env-grounded).
    Advisory only — selecting touches no repository/runner state."""
    loop = build_real_loop()
    choice = loop._selector.select(_proposed(data_accession="GSE1"), _graph())
    assert choice is not None
    assert choice.method_id  # a real method id
    assert choice.source in ("structural", "fallback")
