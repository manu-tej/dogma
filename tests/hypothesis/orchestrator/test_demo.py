"""Tests for the deterministic demo loop."""

from quration.hypothesis.graph import EdgeState
from quration.hypothesis.orchestrator.checkpoint import QueryKind
from quration.hypothesis.orchestrator.demo import build_demo_loop


def test_demo_start_builds_three_node_two_edge_graph():
    loop = build_demo_loop()
    start = loop.start("does EGFR drive resistance?")
    assert start.kind == QueryKind.INVESTIGATIVE
    graph = loop.get_graph(start.graph_id)
    assert len(graph.nodes) == 3
    assert {e.id for e in graph.edges} == {"e-egfr-kras", "e-kras-resist"}
    assert all(e.state == EdgeState.UNTESTED for e in graph.edges)


def test_demo_full_loop_records_evidence_on_first_proposed_edge():
    loop = build_demo_loop()
    start = loop.start("does EGFR drive resistance?")
    proposed = loop.next_proposal(start.graph_id)
    assert proposed is not None
    entry = loop.approve(start.graph_id, proposed)
    edge = loop.get_graph(start.graph_id).get_edge(proposed.edge_id)
    assert edge.state == EdgeState.EXAMINED  # has a ledger record, not a verdict
    assert edge.confidence == 0.0
    assert entry.edge_id == proposed.edge_id


def test_demo_get_graph_unknown_returns_none():
    assert build_demo_loop().get_graph("nope") is None


def test_propose_test_prefers_edge_proposed_test():
    from quration.hypothesis.orchestrator.demo import build_demo_loop
    from quration.hypothesis.orchestrator.edge_chat import SetTest
    loop = build_demo_loop()
    start = loop.start("does EGFR drive resistance?")
    edge = loop.get_graph(start.graph_id).untested_edges()[0]
    # Set the test through the proper persistence path (robust to a non-in-memory repo).
    loop.apply_edge_edit(start.graph_id, SetTest(
        edge_id=edge.id, pipeline="nf-core/custom", data_accession="GSE999"))
    proposed = loop.next_proposal(start.graph_id)
    assert proposed.pipeline == "nf-core/custom"
    assert proposed.data_accession == "GSE999"
