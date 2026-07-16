# tests/hypothesis/orchestrator/test_pathfinding.py
"""Tests for shortest_paths (pure bidirectional BFS over a fake Network)."""

from quration.hypothesis.connectors.network import Neighbor
from quration.hypothesis.graph import Edge
from quration.hypothesis.orchestrator.pathfinding import shortest_paths


def _edge(s, t):
    return Edge(id=f"{s}-{t}", source_id=s, target_id=t, relation="activates")


class FakeNetwork:
    """A directed graph from an adjacency list of (src, tgt) pairs."""

    def __init__(self, pairs, labels=None):
        self._pairs = list(pairs)
        self._labels = labels or {}
        self.fetches = []  # node ids whose neighbors were requested

    def out_edges(self, node_id):
        self.fetches.append(("out", node_id))
        return [
            Neighbor(t, self._labels.get(t, t), _edge(s, t))
            for s, t in self._pairs if s == node_id
        ]

    def in_edges(self, node_id):
        self.fetches.append(("in", node_id))
        return [
            Neighbor(s, self._labels.get(s, s), _edge(s, t))
            for s, t in self._pairs if t == node_id
        ]

    def label(self, node_id):
        return self._labels.get(node_id, node_id)


def _ids(path):
    return [e.id for e in path]


def test_direct_edge():
    net = FakeNetwork([("A", "B")])
    paths = shortest_paths(net, "A", "B")
    assert [_ids(p) for p in paths] == [["A-B"]]


def test_two_hop_via_shared_neighbor_costs_two_fetches():
    net = FakeNetwork([("A", "C"), ("C", "B")])
    paths = shortest_paths(net, "A", "B")
    assert [_ids(p) for p in paths] == [["A-C", "C-B"]]
    # 2-hop found from A's out-neighbors and B's in-neighbors only — C is never expanded.
    expanded = {nid for _, nid in net.fetches}
    assert "C" not in expanded


def test_multiple_shortest_paths_are_candidates():
    net = FakeNetwork([("A", "C1"), ("C1", "B"), ("A", "C2"), ("C2", "B")])
    paths = shortest_paths(net, "A", "B", max_candidates=4)
    got = sorted(_ids(p) for p in paths)
    assert got == [["A-C1", "C1-B"], ["A-C2", "C2-B"]]


def test_three_hop_chain():
    net = FakeNetwork([("A", "C"), ("C", "D"), ("D", "B")])
    paths = shortest_paths(net, "A", "B", max_hops=4)
    assert [_ids(p) for p in paths] == [["A-C", "C-D", "D-B"]]


def test_no_path_returns_empty():
    net = FakeNetwork([("A", "C"), ("X", "B")])
    assert shortest_paths(net, "A", "B") == []


def test_directed_does_not_traverse_backwards():
    net = FakeNetwork([("B", "A")])  # only B->A exists; no directed A->B
    assert shortest_paths(net, "A", "B", directed=True) == []


def test_undirected_fallback_finds_reverse_edge():
    net = FakeNetwork([("B", "A")])
    paths = shortest_paths(net, "A", "B", directed=False)
    assert [_ids(p) for p in paths] == [["B-A"]]  # edge keeps its original direction


def test_node_budget_bounds_expansion():
    # a star: A -> many spokes, none reaching B; budget should cap work
    pairs = [("A", f"S{i}") for i in range(100)]
    net = FakeNetwork(pairs)
    shortest_paths(net, "A", "B", node_budget=5)
    assert len(net.fetches) <= 12  # bounded (a few per side), not ~100


def test_deterministic():
    net = FakeNetwork([("A", "C1"), ("C1", "B"), ("A", "C2"), ("C2", "B")])
    a = shortest_paths(net, "A", "B")
    b = shortest_paths(net, "A", "B")
    assert [_ids(p) for p in a] == [_ids(p) for p in b]


def test_max_hops_rejects_too_long_path():
    net = FakeNetwork([("A", "C"), ("C", "D"), ("D", "E"), ("E", "B")])  # only a 4-hop path
    assert shortest_paths(net, "A", "B", max_hops=3) == []
    four_hop = shortest_paths(net, "A", "B", max_hops=4)
    assert [_ids(p) for p in four_hop] == [["A-C", "C-D", "D-E", "E-B"]]


def test_max_candidates_caps_results():
    pairs = []
    for i in range(5):
        pairs += [("A", f"C{i}"), (f"C{i}", "B")]   # 5 distinct 2-hop paths
    net = FakeNetwork(pairs)
    assert len(shortest_paths(net, "A", "B", max_candidates=3)) == 3


def test_four_hop_chain():
    net = FakeNetwork([("A", "C"), ("C", "D"), ("D", "E"), ("E", "B")])
    paths = shortest_paths(net, "A", "B", max_hops=4)
    assert [_ids(p) for p in paths] == [["A-C", "C-D", "D-E", "E-B"]]
