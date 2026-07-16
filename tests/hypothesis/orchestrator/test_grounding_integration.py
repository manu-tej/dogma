"""End-to-end grounding against the real methods-graph Kùzu DB.

Skips unless data/methods_demo.kuzu exists and methods_graph is importable.
"""
import importlib.util
from pathlib import Path

import pytest

from quration.broker.method_broker import MethodBroker
from quration.config import get_config
from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
from quration.hypothesis.orchestrator.checkpoint import ProposedTest
from quration.hypothesis.orchestrator.method_selection import BrokerMethodSelector

_DB = Path("data/methods_demo.kuzu")
pytestmark = pytest.mark.skipif(
    not _DB.exists() or importlib.util.find_spec("methods_graph") is None,
    reason="real methods-graph DB / package not available",
)


def _graph():
    g = CausalGraph(id="g", query="does EGFR drive KRAS?")
    g.add_node(Node(id="egfr", type=NodeType.TARGET, label="EGFR"))
    g.add_node(Node(id="kras", type=NodeType.TARGET, label="KRAS"))
    g.add_edge(Edge(id="e1", source_id="egfr", target_id="kras",
                    relation="up-regulates", pending=True))
    return g


def test_real_grounding_is_populated(monkeypatch):
    monkeypatch.setenv("QURATION_METHODS_GRAPH_DB", str(_DB.resolve()))
    broker = MethodBroker(get_config())
    assert broker.method_provider is not None  # graph-grounded, not the fallback
    sel = BrokerMethodSelector(broker)
    proposed = ProposedTest(
        edge_id="e1", gap="g", pipeline="nf-core/rnaseq", data_accession="GSE1",
        source_symbol="EGFR", target_symbol="KRAS", relation="up-regulates",
    )
    choice = sel.select(proposed, _graph())
    assert choice is not None
    assert choice.grounding
    # seeded by the chosen method name → its neighborhood mentions it
    assert choice.name.split(":")[-1].lower() in choice.grounding.lower()
    # 2-hop grounding reaches the inherited assumptions (the crosslink work):
    # the rna-seq pick (salmon) inherits assumptions via its statistical method.
    assert "[Assumption]" in choice.grounding
