"""Deleting saved graphs (single + clear-all) from the durable repository."""

from quration.hypothesis.evidence import EvidenceRecord, ResolverProvenance
from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
from quration.hypothesis.store.sqlite_repository import SqliteHypothesisRepository


def _g(gid: str) -> CausalGraph:
    return CausalGraph(
        id=gid, query=f"q-{gid}",
        nodes=[Node(id="n", type=NodeType.TARGET, label="EGFR")], edges=[],
    )


def _g_with_edge(gid: str) -> CausalGraph:
    return CausalGraph(
        id=gid, query=f"q-{gid}",
        nodes=[Node(id="s", type=NodeType.TARGET, label="A"),
               Node(id="t", type=NodeType.TARGET, label="B")],
        edges=[Edge(id="e1", source_id="s", target_id="t", relation="activates")],
    )


def _rec(edge_id: str = "e1") -> EvidenceRecord:
    return EvidenceRecord(
        edge_id=edge_id, claim_signature=("s", "t", "activates"),
        measured_vs_claimed="measured x", directness="direct",
        provenance=ResolverProvenance(),
    )


def test_delete_graph_removes_only_that_graph():
    repo = SqliteHypothesisRepository(":memory:")
    repo.save_graph(_g("a"))
    repo.save_graph(_g("b"))
    assert repo.delete_graph("a") is True
    assert repo.get_graph("a") is None
    assert repo.get_graph("b") is not None
    assert {s.id for s in repo.list_graphs()} == {"b"}


def test_delete_graph_missing_returns_false():
    repo = SqliteHypothesisRepository(":memory:")
    assert repo.delete_graph("nope") is False


def test_delete_all_graphs_clears_everything():
    repo = SqliteHypothesisRepository(":memory:")
    repo.save_graph(_g("a"))
    repo.save_graph(_g("b"))
    assert repo.delete_all_graphs() == 2
    assert repo.list_graphs() == []


def test_delete_graph_cascades_evidence_records():
    """delete_graph must remove evidence_records rows to avoid orphan data."""
    repo = SqliteHypothesisRepository(":memory:")
    repo.save_graph(_g_with_edge("a"))
    repo.save_graph(_g_with_edge("b"))
    repo.add_evidence_record("a", _rec())
    repo.add_evidence_record("b", _rec())

    repo.delete_graph("a")
    assert repo.evidence_records_for("a", "e1") == []
    # graph b's record must survive
    assert len(repo.evidence_records_for("b", "e1")) == 1


def test_delete_all_graphs_cascades_evidence_records():
    """delete_all_graphs must wipe all evidence_records rows."""
    repo = SqliteHypothesisRepository(":memory:")
    repo.save_graph(_g_with_edge("a"))
    repo.save_graph(_g_with_edge("b"))
    repo.add_evidence_record("a", _rec())
    repo.add_evidence_record("b", _rec())

    repo.delete_all_graphs()
    assert repo.evidence_records_for("a", "e1") == []
    assert repo.evidence_records_for("b", "e1") == []
