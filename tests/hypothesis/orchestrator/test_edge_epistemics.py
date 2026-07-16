"""apply_graph_edit stamps proposal source + validation status on created edges."""

import itertools

from quration.hypothesis.epistemics import (
    EdgeValidation,
    EdgeValidationStatus as S,
    ProposalSource,
    record_validation,
)
from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
from quration.hypothesis.orchestrator.edge_chat import (
    AddConnectedNode,
    ConnectNodes,
    FlipEdge,
    MergeNodes,
    SetRelation,
    SplitEdge,
    SplitNode,
    apply_graph_edit,
)
from quration.hypothesis.provenance import KGEdgeProvenance


def _kg(reference="x"):
    return KGEdgeProvenance(source="optimuskg", reference=reference)


def _kg_validated_edge(eid, source_id, target_id, relation="activates"):
    e = Edge(id=eid, source_id=source_id, target_id=target_id, relation=relation)
    record_validation(e, EdgeValidation(
        status=S.KG_SUPPORTED_DIRECT, source=ProposalSource.KG,
        evidence=_kg(), created_at="t0"))
    return e

_ids = None


def _new_id():
    return f"n{next(_ids)}"


def _graph():
    global _ids
    _ids = itertools.count(1)
    g = CausalGraph(id="g", query="q")
    g.add_node(Node(id="a", type=NodeType.TARGET, label="A"))
    g.add_node(Node(id="b", type=NodeType.TARGET, label="B"))
    g.add_edge(Edge(id="e1", source_id="a", target_id="b", relation="activates"))
    return g


def test_split_edge_mechanism_edges_are_system_unvalidated():
    g = apply_graph_edit(_graph(), SplitEdge(
        edge_id="e1", mechanism_label="M", mechanism_type=NodeType.TARGET,
        source_relation="r1", target_relation="r2"), _new_id, now=lambda: "t")
    assert len(g.edges) == 2
    for e in g.edges:
        assert e.proposal_source == ProposalSource.SYSTEM
        assert e.validation_status == S.UNVALIDATED


def test_add_connected_node_from_kg_is_kg_supported_direct():
    prov = KGEdgeProvenance(source="optimuskg", reference="gene_gene:a-c")
    g = apply_graph_edit(_graph(), AddConnectedNode(
        anchor_node_id="a", new_label="C", new_type=NodeType.TARGET,
        relation="INTERACTS_WITH", suggested_by=[prov]), _new_id, now=lambda: "t")
    new_edge = next(e for e in g.edges if e.id != "e1")
    assert new_edge.proposal_source == ProposalSource.KG
    assert new_edge.validation_status == S.KG_SUPPORTED_DIRECT
    assert len(new_edge.validations) == 1
    assert new_edge.validations[0].evidence == prov


def test_add_connected_node_without_kg_is_llm_unvalidated():
    g = apply_graph_edit(_graph(), AddConnectedNode(
        anchor_node_id="a", new_label="C", new_type=NodeType.TARGET,
        relation="linked", suggested_by=[]), _new_id, now=lambda: "t")
    new_edge = next(e for e in g.edges if e.id != "e1")
    assert new_edge.proposal_source == ProposalSource.LLM
    assert new_edge.validation_status == S.UNVALIDATED


def test_connect_nodes_new_edge_is_kg_supported_direct():
    g0 = _graph()
    g0.add_node(Node(id="c", type=NodeType.TARGET, label="C"))
    prov = KGEdgeProvenance(source="optimuskg", reference="gene_gene:a-c")
    g = apply_graph_edit(g0, ConnectNodes(
        source_id="a", target_id="c", relation="INTERACTS_WITH",
        suggested_by=[prov]), _new_id, now=lambda: "t")
    new_edge = next(e for e in g.edges if e.id != "e1")
    assert new_edge.proposal_source == ProposalSource.KG
    assert new_edge.validation_status == S.KG_SUPPORTED_DIRECT


def test_connect_nodes_enriches_existing_edge_validation():
    prov = KGEdgeProvenance(source="optimuskg", reference="gene_gene:a-b")
    g = apply_graph_edit(_graph(), ConnectNodes(
        source_id="a", target_id="b", relation="activates",
        suggested_by=[prov]), _new_id, now=lambda: "t")
    assert len(g.edges) == 1  # no parallel edge
    e = g.get_edge("e1")
    assert e.validation_status == S.KG_SUPPORTED_DIRECT
    assert any(v.evidence == prov for v in e.validations)


def test_set_relation_does_not_touch_validation_status():
    g = apply_graph_edit(_graph(), SetRelation(edge_id="e1", relation="inhibits"),
                         _new_id, now=lambda: "t")
    assert g.get_edge("e1").validation_status == S.UNVALIDATED
    assert g.get_edge("e1").validations == []


# --- claim-changing edits invalidate prior validations (preserving the audit) ---

def _kg_graph():
    global _ids
    _ids = itertools.count(1)
    g = CausalGraph(id="g", query="q")
    for nid in ("a", "b", "c"):
        g.add_node(Node(id=nid, type=NodeType.TARGET, label=nid.upper()))
    return g


def test_set_relation_invalidates_kg_support_but_keeps_audit():
    g = _kg_graph()
    g.add_edge(_kg_validated_edge("e1", "a", "b"))
    out = apply_graph_edit(g, SetRelation(edge_id="e1", relation="inhibits"),
                           _new_id, now=lambda: "t1")
    e = out.get_edge("e1")
    assert e.validation_status == S.UNVALIDATED            # no longer summarizes as supported
    assert any(v.status == S.KG_SUPPORTED_DIRECT for v in e.validations)  # history preserved
    assert e.validations[-1].supersedes_prior is True
    assert e.proposal_source == ProposalSource.LLM         # proposal origin untouched


def test_flip_edge_invalidates_kg_support():
    g = _kg_graph()
    g.add_edge(_kg_validated_edge("e1", "a", "b"))
    out = apply_graph_edit(g, FlipEdge(edge_id="e1"), _new_id, now=lambda: "t1")
    assert out.get_edge("e1").validation_status == S.UNVALIDATED


def test_split_node_invalidates_only_moved_edges():
    g = _kg_graph()
    g.add_edge(_kg_validated_edge("e1", "a", "b"))  # will be moved
    g.add_edge(_kg_validated_edge("e2", "c", "a"))  # NOT moved
    out = apply_graph_edit(g, SplitNode(
        node_id="a", new_label="A2", new_type=NodeType.TARGET, move_edge_ids=["e1"]),
        _new_id, now=lambda: "t1")
    assert out.get_edge("e1").validation_status == S.UNVALIDATED          # moved → invalidated
    assert out.get_edge("e2").validation_status == S.KG_SUPPORTED_DIRECT  # untouched


def test_merge_nodes_invalidates_affected_surviving_edge():
    g = _kg_graph()
    g.add_edge(_kg_validated_edge("e1", "a", "b"))  # target b will be rewritten to c
    out = apply_graph_edit(g, MergeNodes(node_id="b", into_node_id="c"),
                           _new_id, now=lambda: "t1")
    e1 = out.get_edge("e1")
    assert e1.target_id == "c"                       # endpoint changed
    assert e1.validation_status == S.UNVALIDATED     # so prior support invalidated


# --- ConnectNodes matches exact direction (fix #3) ---

def test_connect_nodes_does_not_enrich_reverse_edge():
    g = _graph()  # has e1: a -> b
    # a forward b->a proposal must NOT validate the reverse a->b claim
    out = apply_graph_edit(g, ConnectNodes(
        source_id="b", target_id="a", relation="activates", suggested_by=[_kg()]),
        _new_id, now=lambda: "t")
    assert out.get_edge("e1").validation_status == S.UNVALIDATED  # a->b untouched
    new = next(e for e in out.edges if e.id != "e1")
    assert (new.source_id, new.target_id) == ("b", "a")          # new directed edge
    assert new.validation_status == S.KG_SUPPORTED_DIRECT
