# tests/hypothesis/connectors/test_path_suggester.py
"""Tests for PathEdgeSuggester (pairwise judged shortest paths -> SuggestionResult)."""

from quration.hypothesis.connectors.network import Neighbor
from quration.hypothesis.connectors.path_suggester import PathEdgeSuggester
from quration.hypothesis.graph import Edge, NodeType


def _edge(s, t, src="signor"):
    from quration.hypothesis.provenance import KGEdgeProvenance
    return Edge(id=f"{s}-{t}", source_id=s, target_id=t, relation="activates",
                suggested_by=[KGEdgeProvenance(source=src, reference=f"{s}-{t}")])


class FakeNetwork:
    def __init__(self, pairs, labels):
        self._pairs = list(pairs)
        self._labels = labels

    def out_edges(self, node_id):
        return [
            Neighbor(t, self._labels.get(t, t), _edge(s, t))
            for s, t in self._pairs if s == node_id
        ]

    def in_edges(self, node_id):
        return [
            Neighbor(s, self._labels.get(s, s), _edge(s, t))
            for s, t in self._pairs if t == node_id
        ]

    def label(self, node_id):
        return self._labels.get(node_id, node_id)


class PickFirstJudge:
    def select(self, query, candidates, labels):
        return {pair: cands[0] for pair, cands in candidates.items() if cands}


def test_two_seeds_returns_path_graph():
    net = FakeNetwork([("A", "C"), ("C", "B")], {"A": "EGFR", "C": "MAP2K1", "B": "KRAS"})
    sug = PathEdgeSuggester(net, judge=PickFirstJudge())
    result = sug.expand(["A", "B"], query="does EGFR drive KRAS?")
    assert {e.id for e in result.edges} == {"A-C", "C-B"}
    assert {n.id for n in result.nodes} == {"A", "C", "B"}
    egfr = next(n for n in result.nodes if n.id == "A")
    assert egfr.label == "EGFR" and egfr.type == NodeType.TARGET
    assert egfr.grounding.ontology == "UniProt" and egfr.grounding.term_id == "A"


def test_single_seed_returns_capped_one_hop():
    pairs = [("A", f"S{i:02d}") for i in range(30)]
    net = FakeNetwork(pairs, {})
    sug = PathEdgeSuggester(net, judge=PickFirstJudge(), onehop_cap=5)
    result = sug.expand(["A"], query="q")
    assert 0 < len(result.edges) <= 5


def test_no_path_returns_empty():
    net = FakeNetwork([("A", "C"), ("X", "B")], {})
    sug = PathEdgeSuggester(net, judge=PickFirstJudge())
    assert sug.expand(["A", "B"], query="q").edges == []


def test_no_seeds_returns_empty():
    net = FakeNetwork([("A", "B")], {})
    assert PathEdgeSuggester(net, judge=PickFirstJudge()).expand([], query="q").edges == []


def test_provenance_preserved():
    net = FakeNetwork([("A", "B")], {})
    result = PathEdgeSuggester(net, judge=PickFirstJudge()).expand(["A", "B"], query="q")
    assert result.edges[0].suggested_by[0].source == "signor"


def test_query_forwarded_to_judge():
    seen = {}

    class SpyJudge:
        def select(self, query, candidates, labels):
            seen["query"] = query
            return {pair: cands[0] for pair, cands in candidates.items() if cands}

    net = FakeNetwork([("A", "B")], {})
    PathEdgeSuggester(net, judge=SpyJudge()).expand(["A", "B"], query="the question")
    assert seen["query"] == "the question"


def test_undirected_fallback_used_when_no_directed_path():
    net = FakeNetwork([("B", "A")], {"A": "EGFR", "B": "KRAS"})  # only B->A exists
    result = PathEdgeSuggester(net, judge=PickFirstJudge()).expand(["A", "B"], query="q")
    assert {e.id for e in result.edges} == {"B-A"}   # undirected fallback found it


def test_three_seeds_union_dedupes_shared_node_and_edge():
    # A->C->B and A->C->D share node C and edge A-C
    net = FakeNetwork([("A", "C"), ("C", "B"), ("C", "D")],
                      {"A": "EGFR", "C": "MAP2K1", "B": "KRAS", "D": "MAPK1"})
    result = PathEdgeSuggester(net, judge=PickFirstJudge()).expand(["A", "B", "D"], query="q")
    assert {"A-C", "C-B", "C-D"}.issubset({e.id for e in result.edges})
    assert len([n for n in result.nodes if n.id == "C"]) == 1        # C deduped
    assert len([e for e in result.edges if e.id == "A-C"]) == 1      # shared edge deduped


def test_judge_exception_falls_back_to_shortest():
    class BoomJudge:
        def select(self, query, candidates, labels):
            raise RuntimeError("judge down")

    net = FakeNetwork([("A", "C"), ("C", "B")], {})
    result = PathEdgeSuggester(net, judge=BoomJudge()).expand(["A", "B"], query="q")
    assert {e.id for e in result.edges} == {"A-C", "C-B"}   # shortest used despite the crash
