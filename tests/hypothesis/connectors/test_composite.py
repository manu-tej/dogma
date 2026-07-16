# tests/hypothesis/connectors/test_composite.py
"""Tests for the multi-source composite suggester."""

from quration.hypothesis.connectors.base import SuggestionResult
from quration.hypothesis.connectors.composite import CompositeEdgeSuggester
from quration.hypothesis.graph import Edge, Node, NodeType
from quration.hypothesis.provenance import KGEdgeProvenance


def _node(nid, label="x"):
    return Node(id=nid, type=NodeType.TARGET, label=label)


def _edge(eid, s, t, rel, src):
    return Edge(id=eid, source_id=s, target_id=t, relation=rel, pending=True,
                suggested_by=[KGEdgeProvenance(source=src, reference=eid)])


class Stub:
    def __init__(self, result=None, boom=False):
        self._result, self._boom = result, boom

    def expand(self, seeds, query=None):
        if self._boom:
            raise RuntimeError("x")
        return self._result

    def check_pair(self, s, t):
        return None


def test_union_dedupes_nodes_and_keeps_distinct_edges():
    a = Stub(SuggestionResult(nodes=[_node("P1"), _node("P2")],
                              edges=[_edge("a", "P1", "P2", "activates", "signor")]))
    b = Stub(SuggestionResult(nodes=[_node("P2"), _node("P3")],
                              edges=[_edge("b", "P2", "P3", "inhibits", "collectri")]))
    res = CompositeEdgeSuggester([a, b]).expand(["P1"])
    assert {n.id for n in res.nodes} == {"P1", "P2", "P3"}
    assert len(res.edges) == 2


def test_same_triple_merges_provenance():
    a = Stub(SuggestionResult(nodes=[_node("P1"), _node("P2")],
                              edges=[_edge("a", "P1", "P2", "activates", "signor")]))
    b = Stub(SuggestionResult(nodes=[_node("P1"), _node("P2")],
                              edges=[_edge("b", "P1", "P2", "activates", "collectri")]))
    res = CompositeEdgeSuggester([a, b]).expand(["P1"])
    assert len(res.edges) == 1
    assert {p.source for p in res.edges[0].suggested_by} == {"signor", "collectri"}


def test_member_failure_is_isolated():
    good = Stub(SuggestionResult(nodes=[_node("P1"), _node("P2")],
                                edges=[_edge("a", "P1", "P2", "activates", "signor")]))
    res = CompositeEdgeSuggester([Stub(boom=True), good]).expand(["P1"])
    assert len(res.edges) == 1


def test_check_pair_returns_first_hit():
    class Hit(Stub):
        def check_pair(self, s, t):
            return _edge("h", s, t, "activates", "collectri")

    composite = CompositeEdgeSuggester([Stub(), Hit()])
    assert composite.check_pair("P1", "P2").id == "h"


def test_check_pair_isolates_member_failure():
    class Boom(Stub):
        def check_pair(self, s, t):
            raise RuntimeError("x")

    class Hit(Stub):
        def check_pair(self, s, t):
            return _edge("h", s, t, "activates", "collectri")

    composite = CompositeEdgeSuggester([Boom(), Hit()])
    assert composite.check_pair("P1", "P2").id == "h"
