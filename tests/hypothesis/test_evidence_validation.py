"""The dataset channel records facts in the ledger and asserts no verdict.

Pre-abolition this file checked that the pipeline rollup mapped onto a
DATASET_SUPPORTED/CONTRADICTED/AMBIGUOUS verdict. Those verdicts are abolished
(north-star §2.2): `dataset_validation_for` now contributes nothing, and an edge
with evidence is simply EXAMINED — the per-run facts live in the ledger.
"""

from quration.hypothesis.epistemics import EdgeValidationStatus as S, ProposalSource
from quration.hypothesis.evidence import EvidenceDirection, EvidenceEntry, dataset_validation_for
from quration.hypothesis.graph import EdgeState
from quration.hypothesis.provenance import PipelineRunProvenance


def _entry(direction, weight=1.0):
    return EvidenceEntry(
        edge_id="e1", direction=direction, weight=weight,
        provenance=PipelineRunProvenance(run_id="r1", data_accession="GSE1"))


def test_dataset_validation_is_always_none():
    # No direction (or mix) produces a dataset verdict — support/contradiction/ambiguity
    # are abolished; the records carry the facts.
    assert dataset_validation_for([], "t") is None
    assert dataset_validation_for([_entry(EvidenceDirection.SUPPORTS)], "t") is None
    assert dataset_validation_for([_entry(EvidenceDirection.REFUTES)], "t") is None
    assert dataset_validation_for(
        [_entry(EvidenceDirection.SUPPORTS), _entry(EvidenceDirection.REFUTES)], "t") is None
    assert dataset_validation_for([_entry(EvidenceDirection.INCONCLUSIVE)], "t") is None


def test_add_evidence_examines_edge_and_adds_no_dataset_validation():
    from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
    from quration.hypothesis.orchestrator.edge_chat import SetGrounding, apply_graph_edit
    from quration.hypothesis.repository import InMemoryHypothesisRepository

    repo = InMemoryHypothesisRepository()
    g = CausalGraph(id="g", query="q")
    g.add_node(Node(id="a", type=NodeType.TARGET, label="A"))
    g.add_node(Node(id="b", type=NodeType.TARGET, label="B"))
    g.add_edge(Edge(id="e1", source_id="a", target_id="b", relation="activates"))
    repo.save_graph(g)

    repo.add_evidence("g", _entry(EvidenceDirection.SUPPORTS))
    e = repo.get_graph("g").get_edge("e1")
    assert e.state == EdgeState.EXAMINED                                  # has a ledger record
    assert e.validation_status != S.DATASET_SUPPORTED                     # no dataset verdict
    assert [v for v in e.validations if v.source == ProposalSource.DATASET] == []

    # Adding more evidence still adds no dataset validation and stays EXAMINED.
    repo.add_evidence("g", _entry(EvidenceDirection.SUPPORTS))
    e = repo.get_graph("g").get_edge("e1")
    assert e.state == EdgeState.EXAMINED
    assert [v for v in e.validations if v.source == ProposalSource.DATASET] == []

    # Grounding a node is independent of the (now verdict-free) dataset channel.
    grounded = apply_graph_edit(
        repo.get_graph("g"),
        SetGrounding(node_id="a", ontology="UniProt", term_id="P12345"),
        new_id=lambda: "x", now=lambda: "t")
    repo.save_graph(grounded)
    assert repo.get_graph("g").get_node("a").grounding is not None
    assert repo.get_graph("g").get_edge("e1").state == EdgeState.EXAMINED
