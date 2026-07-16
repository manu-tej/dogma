"""Tests for causal-graph node/edge/container types."""

import pytest

from quration.hypothesis.graph import CausalGraph, Edge, EdgeState, Node, NodeType
from quration.hypothesis.provenance import KGEdgeProvenance, OntologyTermProvenance


def _node(node_id: str, ntype: NodeType = NodeType.TARGET) -> Node:
    return Node(id=node_id, type=ntype, label=node_id)


def test_node_defaults_and_grounding():
    n = Node(
        id="n1",
        type=NodeType.DISEASE,
        label="breast carcinoma",
        grounding=OntologyTermProvenance(ontology="MONDO", term_id="MONDO:0007254"),
    )
    assert n.grounding.term_id == "MONDO:0007254"


def test_edge_defaults_untested_zero_confidence():
    e = Edge(id="e1", source_id="n1", target_id="n2", relation="activates")
    assert e.state == EdgeState.UNTESTED
    assert e.confidence == 0.0
    assert e.pending is False
    assert e.suggested_by == []


def test_edge_carries_kg_suggestions_display_only():
    e = Edge(
        id="e1",
        source_id="n1",
        target_id="n2",
        relation="activates",
        suggested_by=[KGEdgeProvenance(source="signor", reference="SIG-9")],
    )
    assert e.suggested_by[0].source == "signor"


def test_add_node_and_get():
    g = CausalGraph(id="g1", query="does X drive Y?")
    g.add_node(_node("n1"))
    assert g.get_node("n1").label == "n1"
    assert g.get_node("missing") is None


def test_add_duplicate_node_raises():
    g = CausalGraph(id="g1", query="q")
    g.add_node(_node("n1"))
    with pytest.raises(ValueError, match="duplicate node"):
        g.add_node(_node("n1"))


def test_add_edge_requires_existing_endpoints():
    g = CausalGraph(id="g1", query="q")
    g.add_node(_node("n1"))
    with pytest.raises(ValueError, match="unknown endpoint"):
        g.add_edge(Edge(id="e1", source_id="n1", target_id="n2", relation="activates"))


def test_add_edge_and_helpers():
    g = CausalGraph(id="g1", query="q")
    g.add_node(_node("n1"))
    g.add_node(_node("n2"))
    g.add_edge(Edge(id="e1", source_id="n1", target_id="n2", relation="activates"))
    assert g.get_edge("e1").relation == "activates"
    assert [e.id for e in g.untested_edges()] == ["e1"]
    assert [e.id for e in g.edges_incident("n2")] == ["e1"]


def test_add_duplicate_edge_raises():
    g = CausalGraph(id="g1", query="q")
    g.add_node(_node("n1"))
    g.add_node(_node("n2"))
    e = Edge(id="e1", source_id="n1", target_id="n2", relation="activates")
    g.add_edge(e)
    with pytest.raises(ValueError, match="duplicate edge"):
        g.add_edge(e)


def test_edge_carries_optional_proposed_test():
    from quration.hypothesis.graph import Edge, EdgeTest
    e = Edge(id="e1", source_id="a", target_id="b", relation="drives")
    assert e.proposed_test is None
    e.proposed_test = EdgeTest(pipeline="nf-core/rnaseq", data_accession="GSE1", expected="up")
    assert e.proposed_test.pipeline == "nf-core/rnaseq"


def test_remove_edge_drops_only_that_edge():
    from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
    g = CausalGraph(id="g", query="q")
    g.add_node(Node(id="a", type=NodeType.TARGET, label="A"))
    g.add_node(Node(id="b", type=NodeType.PHENOTYPE, label="B"))
    g.add_edge(Edge(id="e1", source_id="a", target_id="b", relation="drives"))
    g.remove_edge("e1")
    assert g.get_edge("e1") is None
    g.remove_edge("missing")  # no-op, no raise


def test_remove_node_drops_only_that_node():
    from quration.hypothesis.graph import CausalGraph, Node, NodeType
    g = CausalGraph(id="g", query="q")
    g.add_node(Node(id="a", type=NodeType.TARGET, label="A"))
    g.add_node(Node(id="b", type=NodeType.PHENOTYPE, label="B"))
    g.remove_node("a")
    assert g.get_node("a") is None
    assert g.get_node("b") is not None
    g.remove_node("missing")  # no-op, no raise


def test_node_accepts_protein_state_grounding_and_round_trips():
    from quration.hypothesis.graph import CausalGraph, Node, NodeType
    from quration.hypothesis.provenance import (
        OntologyTermProvenance,
        ProteinModification,
        ProteinStateProvenance,
    )

    node = Node(
        id="n",
        type=NodeType.PHENOTYPE,
        label="pAKT (phospho-AKT; S473/T308)",
        grounding=ProteinStateProvenance(
            family_label="AKT (phospho-S473/T308)",
            members=[OntologyTermProvenance(ontology="UniProt", term_id="P31749", label="AKT1")],
            modification=ProteinModification(residues=["S473", "T308"]),
        ),
    )
    g = CausalGraph(id="g", query="q", nodes=[node], edges=[])

    reparsed = CausalGraph.model_validate_json(g.model_dump_json())
    grounding = reparsed.get_node("n").grounding
    assert grounding.kind == "protein_state"          # discriminator preserved on reload
    assert grounding.members[0].term_id == "P31749"


def test_node_still_accepts_ontology_term_grounding():
    from quration.hypothesis.graph import Node, NodeType
    from quration.hypothesis.provenance import OntologyTermProvenance

    node = Node(id="n", type=NodeType.TARGET, label="EGFR",
                grounding=OntologyTermProvenance(ontology="UniProt", term_id="P00533"))
    reparsed = Node.model_validate_json(node.model_dump_json())
    assert reparsed.grounding.kind == "ontology_term"
    assert reparsed.grounding.term_id == "P00533"
