import itertools

import pytest

from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
from quration.hypothesis.orchestrator.edge_chat import (
    FlipEdge,
    ResolveIsoform,
    SetProteinStateGrounding,
    SetRelation,
    SetTest,
    SplitEdge,
    apply_graph_edit,
)
from quration.hypothesis.provenance import OntologyTermProvenance, ProteinStateProvenance


def _graph() -> CausalGraph:
    g = CausalGraph(id="g", query="q")
    g.add_node(Node(id="A", type=NodeType.TARGET, label="EGFR"))
    g.add_node(Node(id="B", type=NodeType.PHENOTYPE, label="resistance"))
    g.add_edge(Edge(id="A-B", source_id="A", target_id="B", relation="drives", pending=True))
    return g


def _ids():
    counter = itertools.count(1)
    return lambda: f"new-{next(counter)}"


def test_set_relation():
    g = apply_graph_edit(_graph(), SetRelation(edge_id="A-B", relation="up-regulates"), _ids())
    assert g.get_edge("A-B").relation == "up-regulates"


def test_flip_edge():
    g = apply_graph_edit(_graph(), FlipEdge(edge_id="A-B"), _ids())
    e = g.get_edge("A-B")
    assert (e.source_id, e.target_id) == ("B", "A")


def test_set_test():
    g = apply_graph_edit(
        _graph(),
        SetTest(edge_id="A-B", pipeline="nf-core/differentialabundance", data_accession="GSE42"),
        _ids(),
    )
    pt = g.get_edge("A-B").proposed_test
    assert pt.pipeline == "nf-core/differentialabundance" and pt.data_accession == "GSE42"


def test_split_edge_inserts_mechanism():
    g = apply_graph_edit(
        _graph(),
        SplitEdge(edge_id="A-B", mechanism_label="KRAS", mechanism_type=NodeType.TARGET,
                  source_relation="up-regulates", target_relation="drives"),
        _ids(),
    )
    assert g.get_edge("A-B") is None
    assert any(n.label == "KRAS" for n in g.nodes)
    rels = sorted(e.relation for e in g.edges)
    assert rels == ["drives", "up-regulates"]
    assert all(e.pending for e in g.edges)


def test_apply_unknown_edge_raises():
    import pytest
    with pytest.raises(ValueError, match="no edge"):
        apply_graph_edit(_graph(), FlipEdge(edge_id="ghost"), _ids())


from quration.hypothesis.orchestrator.edge_chat import DemoEdgeChatService, EdgeChatService


def test_demo_explains_with_no_edit_by_default():
    svc = DemoEdgeChatService()
    turn = svc.respond(_graph(), "A-B", [], "what does this edge mean?")
    assert turn.reply
    assert turn.proposed_edit is None


def test_demo_proposes_split_on_keyword():
    svc = DemoEdgeChatService()
    turn = svc.respond(_graph(), "A-B", [], "can you split this with a mechanism?")
    assert turn.proposed_edit is not None
    assert turn.proposed_edit.op == "split_edge"
    assert turn.proposed_edit.edge_id == "A-B"


def test_demo_proposes_flip_on_keyword():
    svc = DemoEdgeChatService()
    turn = svc.respond(_graph(), "A-B", [], "I think the direction is backwards, flip it")
    assert turn.proposed_edit.op == "flip_edge"


def test_demo_satisfies_protocol():
    assert isinstance(DemoEdgeChatService(), EdgeChatService)


import json

from quration.hypothesis.orchestrator.edge_chat import LlmEdgeChatService


class _FakeProvider:
    def __init__(self, payload):
        self._payload = payload
        self.last_messages = None

    def create_message(self, messages, model, max_tokens=4096, temperature=1.0, system=None, **kwargs):
        self.last_messages = messages
        return self._payload if isinstance(self._payload, str) else json.dumps(self._payload)


def test_llm_reply_only():
    svc = LlmEdgeChatService(provider=_FakeProvider({"reply": "It means X."}), model="m")
    turn = svc.respond(_graph(), "A-B", [], "explain")
    assert turn.reply == "It means X."
    assert turn.proposed_edit is None


def test_llm_reply_with_edit():
    provider = _FakeProvider({"reply": "Let's flip it.", "edit": {"op": "flip_edge", "edge_id": "A-B"}})
    svc = LlmEdgeChatService(provider=provider, model="m")
    turn = svc.respond(_graph(), "A-B", [], "flip")
    assert turn.reply == "Let's flip it."
    assert turn.proposed_edit.op == "flip_edge"
    # the edge context (source/target labels) is included in the prompt sent to the model
    assert "EGFR" in json.dumps(provider.last_messages)


def test_llm_malformed_is_reply_only_not_raise():
    svc = LlmEdgeChatService(provider=_FakeProvider("not json"), model="m")
    turn = svc.respond(_graph(), "A-B", [], "x")
    assert turn.proposed_edit is None
    assert turn.reply  # a graceful fallback reply


from quration.hypothesis.orchestrator.edge_chat import (
    MergeNodes,
    SetGrounding,
    SetLabel,
    SetNodeType,
    SplitNode,
)


def _node_graph():
    g = CausalGraph(id="g", query="q")
    g.add_node(Node(id="A", type=NodeType.TARGET, label="EGFR"))
    g.add_node(Node(id="B", type=NodeType.TARGET, label="KRAS"))
    g.add_node(Node(id="C", type=NodeType.PHENOTYPE, label="resistance"))
    g.add_edge(Edge(id="A-B", source_id="A", target_id="B", relation="up-regulates"))
    g.add_edge(Edge(id="B-C", source_id="B", target_id="C", relation="drives"))
    return g


def test_set_label():
    g = apply_graph_edit(_node_graph(), SetLabel(node_id="A", label="EGFR (ErbB1)"), _ids())
    assert g.get_node("A").label == "EGFR (ErbB1)"


def test_set_node_type():
    g = apply_graph_edit(_node_graph(), SetNodeType(node_id="C", node_type=NodeType.DISEASE), _ids())
    assert g.get_node("C").type == NodeType.DISEASE


def test_set_grounding():
    g = apply_graph_edit(
        _node_graph(),
        SetGrounding(node_id="A", ontology="UniProt", term_id="P00533", label="EGFR"),
        _ids(),
    )
    grounding = g.get_node("A").grounding
    assert grounding is not None
    assert grounding.ontology == "UniProt" and grounding.term_id == "P00533"


def test_merge_nodes_repoints_and_drops_self_loops():
    g = apply_graph_edit(_node_graph(), MergeNodes(node_id="B", into_node_id="A"), _ids())
    assert g.get_node("B") is None
    assert g.get_edge("A-B") is None  # self-loop dropped
    bc = g.get_edge("B-C")
    assert bc.source_id == "A" and bc.target_id == "C"


def test_merge_unknown_node_raises():
    import pytest
    with pytest.raises(ValueError, match="no node"):
        apply_graph_edit(_node_graph(), MergeNodes(node_id="ghost", into_node_id="A"), _ids())


def test_merge_into_unknown_node_raises():
    import pytest
    with pytest.raises(ValueError, match="no node"):
        apply_graph_edit(_node_graph(), MergeNodes(node_id="A", into_node_id="ghost"), _ids())


def test_merge_node_into_itself_raises():
    # A self-merge must not leave edges dangling to a removed node.
    import pytest
    with pytest.raises(ValueError, match="itself"):
        apply_graph_edit(_node_graph(), MergeNodes(node_id="B", into_node_id="B"), _ids())


def test_split_node_moves_listed_edges_to_new_node():
    g = apply_graph_edit(
        _node_graph(),
        SplitNode(node_id="B", new_label="KRAS-effector", new_type=NodeType.TARGET, move_edge_ids=["B-C"]),
        _ids(),
    )
    new_nodes = [n for n in g.nodes if n.label == "KRAS-effector"]
    assert len(new_nodes) == 1
    new_id_val = new_nodes[0].id
    assert g.get_edge("B-C").source_id == new_id_val
    assert g.get_edge("A-B").target_id == "B"


def test_split_node_rejects_non_incident_edge():
    import pytest
    with pytest.raises(ValueError, match="not incident"):
        apply_graph_edit(
            _node_graph(),
            SplitNode(node_id="A", new_label="X", new_type=NodeType.OTHER, move_edge_ids=["B-C"]),
            _ids(),
        )


from quration.hypothesis.orchestrator.edge_chat import DemoNodeChatService, NodeChatService


def test_demo_node_explains_with_no_edit_by_default():
    turn = DemoNodeChatService().respond(_node_graph(), "A", [], "what is this node?")
    assert turn.reply
    assert turn.proposed_edit is None


def test_demo_node_proposes_rename_on_keyword():
    turn = DemoNodeChatService().respond(_node_graph(), "A", [], "please rename this node")
    assert turn.proposed_edit is not None
    assert turn.proposed_edit.op == "set_label"
    assert turn.proposed_edit.node_id == "A"


def test_demo_node_proposes_merge_on_keyword():
    turn = DemoNodeChatService().respond(_node_graph(), "B", [], "merge this node")
    assert turn.proposed_edit.op == "merge_nodes"
    assert turn.proposed_edit.node_id == "B"
    assert turn.proposed_edit.into_node_id in {"A", "C"}


def test_demo_node_satisfies_protocol():
    assert isinstance(DemoNodeChatService(), NodeChatService)


from quration.hypothesis.orchestrator.edge_chat import LlmNodeChatService


def test_llm_node_reply_only():
    svc = LlmNodeChatService(provider=_FakeProvider({"reply": "It's EGFR."}), model="m")
    turn = svc.respond(_node_graph(), "A", [], "what is it?")
    assert turn.reply == "It's EGFR."
    assert turn.proposed_edit is None


def test_llm_node_reply_with_edit():
    provider = _FakeProvider({"reply": "Renaming.", "edit": {"op": "set_label", "node_id": "A", "label": "ErbB1"}})
    svc = LlmNodeChatService(provider=provider, model="m")
    turn = svc.respond(_node_graph(), "A", [], "rename")
    assert turn.proposed_edit.op == "set_label"
    assert turn.proposed_edit.label == "ErbB1"
    assert "EGFR" in json.dumps(provider.last_messages)


def test_llm_node_malformed_is_reply_only():
    svc = LlmNodeChatService(provider=_FakeProvider("not json"), model="m")
    turn = svc.respond(_node_graph(), "A", [], "x")
    assert turn.proposed_edit is None
    assert turn.reply


def test_add_connected_node_adds_node_and_provenance_edge():
    from quration.hypothesis.provenance import KGEdgeProvenance
    from quration.hypothesis.orchestrator.edge_chat import AddConnectedNode
    g0 = _node_graph()  # has node A (EGFR)
    g = apply_graph_edit(
        g0,
        AddConnectedNode(anchor_node_id="A", new_label="GRB2", new_type=NodeType.TARGET,
                         relation="INTERACTS_WITH", direction="to",
                         suggested_by=[KGEdgeProvenance(source="PRIMEKG", reference="gene_gene")]),
        _ids(),
    )
    new = [n for n in g.nodes if n.label == "GRB2"]
    assert len(new) == 1
    e = next(e for e in g.edges if e.target_id == new[0].id)
    assert e.source_id == "A" and e.relation == "INTERACTS_WITH"
    assert e.pending and e.suggested_by[0].source == "PRIMEKG"


def test_connect_nodes_adds_provenance_edge_when_none_exists():
    from quration.hypothesis.provenance import KGEdgeProvenance
    from quration.hypothesis.orchestrator.edge_chat import ConnectNodes
    g0 = _node_graph()  # A(EGFR), B(KRAS), C(resistance); edges A-B, B-C — no A-C
    g = apply_graph_edit(g0, ConnectNodes(
        source_id="A", target_id="C", relation="INTERACTS_WITH",
        suggested_by=[KGEdgeProvenance(source="PRIMEKG", reference="gene_gene")]), _ids())
    e = next(e for e in g.edges if {e.source_id, e.target_id} == {"A", "C"})
    assert e.relation == "INTERACTS_WITH" and e.pending and e.suggested_by[0].source == "PRIMEKG"


def test_connect_nodes_enriches_existing_edge_provenance_no_duplicate():
    from quration.hypothesis.provenance import KGEdgeProvenance
    from quration.hypothesis.orchestrator.edge_chat import ConnectNodes
    g0 = _node_graph()  # has edge A-B already (no suggested_by)
    before = len(g0.edges)
    g = apply_graph_edit(g0, ConnectNodes(
        source_id="A", target_id="B", relation="INTERACTS_WITH",
        suggested_by=[KGEdgeProvenance(source="INTACT", reference="gene_gene")]), _ids())
    assert len(g.edges) == before  # no parallel edge added
    ab = g.get_edge("A-B")
    assert any(p.source == "INTACT" for p in ab.suggested_by)  # existing edge enriched


def test_connect_nodes_unknown_node_raises():
    import pytest
    from quration.hypothesis.orchestrator.edge_chat import ConnectNodes
    with pytest.raises(ValueError, match="no node"):
        apply_graph_edit(_node_graph(), ConnectNodes(source_id="A", target_id="ghost"), _ids())


def _akt_ids():
    n = [0]
    def _new():
        n[0] += 1
        return f"x{n[0]}"
    return _new


def _akt_graph():
    return CausalGraph(
        id="g", query="q",
        nodes=[Node(id="n", type=NodeType.PHENOTYPE, label="pAKT (phospho-AKT; S473/T308)")],
        edges=[],
    )


_AKT_EDIT = SetProteinStateGrounding(
    node_id="n",
    family_label="AKT (phospho-S473/T308)",
    members=[
        OntologyTermProvenance(ontology="UniProt", term_id="P31749", label="AKT1"),
        OntologyTermProvenance(ontology="UniProt", term_id="P31751", label="AKT2"),
        OntologyTermProvenance(ontology="UniProt", term_id="Q9Y243", label="AKT3"),
    ],
    residues=["S473", "T308"],
)


def test_apply_set_protein_state_grounding():
    g = apply_graph_edit(_akt_graph(), _AKT_EDIT, _akt_ids())
    grounding = g.get_node("n").grounding
    assert isinstance(grounding, ProteinStateProvenance)
    assert grounding.resolved_to is None
    assert [m.term_id for m in grounding.members] == ["P31749", "P31751", "Q9Y243"]
    assert grounding.modification.residues == ["S473", "T308"]


def test_resolve_isoform_sets_and_clears():
    g = apply_graph_edit(_akt_graph(), _AKT_EDIT, _akt_ids())
    g = apply_graph_edit(g, ResolveIsoform(node_id="n", resolved_to="P31751"), _akt_ids())
    assert g.get_node("n").grounding.resolved_to == "P31751"

    g = apply_graph_edit(g, ResolveIsoform(node_id="n", resolved_to=None), _akt_ids())
    assert g.get_node("n").grounding.resolved_to is None


def test_resolve_isoform_rejects_non_member():
    g = apply_graph_edit(_akt_graph(), _AKT_EDIT, _akt_ids())
    with pytest.raises(ValueError):
        apply_graph_edit(g, ResolveIsoform(node_id="n", resolved_to="P99999"), _akt_ids())


def test_resolve_isoform_rejects_node_without_protein_state():
    g = CausalGraph(id="g", query="q",
                    nodes=[Node(id="n", type=NodeType.TARGET, label="EGFR")], edges=[])
    with pytest.raises(ValueError):
        apply_graph_edit(g, ResolveIsoform(node_id="n", resolved_to="P00533"), _akt_ids())
