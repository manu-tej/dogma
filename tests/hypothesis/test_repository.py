"""Tests for the in-memory hypothesis repository (recompute-on-add behavior)."""

import pytest

from quration.hypothesis.evidence import EvidenceDirection, EvidenceEntry, EvidenceKind
from quration.hypothesis.graph import CausalGraph, Edge, EdgeState, Node, NodeType
from quration.hypothesis.provenance import PipelineRunProvenance
from quration.hypothesis.repository import HypothesisRepository, InMemoryHypothesisRepository


def _graph_with_one_edge() -> CausalGraph:
    g = CausalGraph(id="g1", query="does X drive Y?")
    g.add_node(Node(id="n1", type=NodeType.TARGET, label="X"))
    g.add_node(Node(id="n2", type=NodeType.PHENOTYPE, label="Y"))
    g.add_edge(Edge(id="e1", source_id="n1", target_id="n2", relation="drives"))
    return g


def _evidence(direction: EvidenceDirection) -> EvidenceEntry:
    return EvidenceEntry(
        kind=EvidenceKind.MEASUREMENT,
        edge_id="e1",
        direction=direction,
        provenance=PipelineRunProvenance(run_id="r1", data_accession="GSE1"),
    )


def test_save_and_get_graph():
    repo = InMemoryHypothesisRepository()
    repo.save_graph(_graph_with_one_edge())
    assert repo.get_graph("g1").query == "does X drive Y?"
    assert repo.get_graph("missing") is None


def test_add_evidence_recomputes_edge_state():
    repo = InMemoryHypothesisRepository()
    repo.save_graph(_graph_with_one_edge())
    assert repo.get_graph("g1").get_edge("e1").state == EdgeState.UNTESTED

    repo.add_evidence("g1", _evidence(EvidenceDirection.SUPPORTS))

    edge = repo.get_graph("g1").get_edge("e1")
    assert edge.state == EdgeState.EXAMINED
    assert edge.confidence == 0.0
    assert len(repo.evidence_for_edge("g1", "e1")) == 1


def test_conflicting_evidence_is_examined_not_a_verdict():
    repo = InMemoryHypothesisRepository()
    repo.save_graph(_graph_with_one_edge())
    repo.add_evidence("g1", _evidence(EvidenceDirection.SUPPORTS))
    repo.add_evidence("g1", _evidence(EvidenceDirection.REFUTES))
    # Conflicting records do not produce CONTESTED — the edge is EXAMINED and both
    # records (the disagreement) live in the ledger.
    assert repo.get_graph("g1").get_edge("e1").state == EdgeState.EXAMINED
    assert len(repo.evidence_for_edge("g1", "e1")) == 2


def test_public_exports_importable_from_package():
    import quration.hypothesis as h

    for name in (
        "CausalGraph", "Node", "Edge", "NodeType", "EdgeState",
        "EvidenceEntry", "EvidenceDirection", "rollup_edge",
        "Provenance", "OntologyTermProvenance", "KGEdgeProvenance",
        "LiteratureProvenance", "PipelineRunProvenance",
        "HypothesisRepository", "InMemoryHypothesisRepository",
    ):
        assert hasattr(h, name), f"missing export: {name}"


def test_save_graph_reapplies_existing_evidence():
    repo = InMemoryHypothesisRepository()
    repo.save_graph(_graph_with_one_edge())
    repo.add_evidence("g1", _evidence(EvidenceDirection.SUPPORTS))
    # Re-save a freshly built graph object with the same id/edge (its edges start UNTESTED).
    repo.save_graph(_graph_with_one_edge())
    edge = repo.get_graph("g1").get_edge("e1")
    assert edge.state == EdgeState.EXAMINED
    assert edge.confidence == 0.0


def test_add_evidence_for_unknown_edge_raises():
    repo = InMemoryHypothesisRepository()
    repo.save_graph(_graph_with_one_edge())
    with pytest.raises(ValueError, match="no edge"):
        repo.add_evidence(
            "g1",
            EvidenceEntry(
                kind=EvidenceKind.MEASUREMENT,
                edge_id="ghost",
                direction=EvidenceDirection.SUPPORTS,
                provenance=PipelineRunProvenance(run_id="r", data_accession="GSE1"),
            ),
        )


def test_same_edge_id_in_two_graphs_is_independent():
    """Two investigations may reuse an edge id; evidence stays scoped per graph."""
    repo = InMemoryHypothesisRepository()
    repo.save_graph(_graph_with_one_edge())  # g1 with edge e1
    g2 = CausalGraph(id="g2", query="other")
    g2.add_node(Node(id="m1", type=NodeType.TARGET, label="A"))
    g2.add_node(Node(id="m2", type=NodeType.PHENOTYPE, label="B"))
    g2.add_edge(Edge(id="e1", source_id="m1", target_id="m2", relation="drives"))
    repo.save_graph(g2)  # same edge id "e1" in a different graph — now allowed

    # Record evidence on g1's e1 only.
    repo.add_evidence("g1", _evidence(EvidenceDirection.SUPPORTS))

    # g1's edge is examined; g2's identically-named edge is untouched.
    assert repo.get_graph("g1").get_edge("e1").state == EdgeState.EXAMINED
    assert repo.get_graph("g2").get_edge("e1").state == EdgeState.UNTESTED
    assert len(repo.evidence_for_edge("g1", "e1")) == 1
    assert len(repo.evidence_for_edge("g2", "e1")) == 0


def test_repository_protocol_is_runtime_checkable():
    assert isinstance(InMemoryHypothesisRepository(), HypothesisRepository)
