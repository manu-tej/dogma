"""Tests for connector base types."""

from quration.hypothesis.connectors.base import SuggestionResult
from quration.hypothesis.graph import Edge, Node, NodeType


def test_suggestion_result_defaults_empty():
    r = SuggestionResult()
    assert r.nodes == []
    assert r.edges == []


def test_suggestion_result_holds_nodes_and_edges():
    n = Node(id="P00533", type=NodeType.TARGET, label="EGFR")
    e = Edge(id="s1", source_id="P00533", target_id="P01112", relation="up-regulates")
    r = SuggestionResult(nodes=[n], edges=[e])
    assert r.nodes[0].label == "EGFR"
    assert r.edges[0].relation == "up-regulates"


def test_public_exports_importable():
    import quration.hypothesis.connectors as c

    for name in (
        "EdgeSuggester", "SuggestionResult", "SignorConnectorError",
        "SignorClient", "SignorEdgeSuggester", "SignorRecord", "default_signor_fetch",
    ):
        assert hasattr(c, name), f"missing export: {name}"
