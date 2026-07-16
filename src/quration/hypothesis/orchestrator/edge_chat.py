"""Per-edge conversation: explain an edge and propose one structured edit per turn.

`apply_graph_edit` is the pure graph mutation; the EdgeChatService seam authors the
conversation (deterministic demo + LLM impls), swapped via DI like seeding.
"""

import json
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

from quration.hypothesis.epistemics import (
    EdgeValidation,
    EdgeValidationStatus,
    ProposalSource,
    record_validation,
    reset_edge_validation,
)
from quration.hypothesis.graph import CausalGraph, Edge, EdgeTest, Node, NodeType
from quration.hypothesis.graph_prompt import serialize_graph_for_llm
from quration.hypothesis.provenance import (
    KGEdgeProvenance,
    OntologyTermProvenance,
    ProteinModification,
    ProteinStateProvenance,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _kg_validation(suggested_by: list[KGEdgeProvenance], now: Callable[[], str]) -> EdgeValidation:
    """A *direct-KG-link* validation built from a KG neighbor suggestion.

    `kg_supported_direct` asserts the knowledge graph reports a direct link between
    the two entities — NOT that the graph edge's specific causal relation/direction
    is confirmed. The rationale is explicit about that distinction."""
    ev = suggested_by[0] if suggested_by else None
    return EdgeValidation(
        status=EdgeValidationStatus.KG_SUPPORTED_DIRECT,
        source=ProposalSource.KG,
        evidence=ev,
        kg_source=(ev.source if ev else None),
        rationale=("knowledge graph reports a direct link between these entities "
                   "(does not confirm the specific relation or direction)"),
        created_at=now(),
    )


class SetRelation(BaseModel):
    op: Literal["set_relation"] = "set_relation"
    edge_id: str
    relation: str


class FlipEdge(BaseModel):
    op: Literal["flip_edge"] = "flip_edge"
    edge_id: str


class SetTest(BaseModel):
    op: Literal["set_test"] = "set_test"
    edge_id: str
    pipeline: str | None = None
    data_accession: str | None = None
    expected: str | None = None


class SplitEdge(BaseModel):
    op: Literal["split_edge"] = "split_edge"
    edge_id: str
    mechanism_label: str
    mechanism_type: NodeType = NodeType.OTHER
    source_relation: str
    target_relation: str


class SetLabel(BaseModel):
    op: Literal["set_label"] = "set_label"
    node_id: str
    label: str


class SetNodeType(BaseModel):
    op: Literal["set_node_type"] = "set_node_type"
    node_id: str
    node_type: NodeType


class SetGrounding(BaseModel):
    op: Literal["set_grounding"] = "set_grounding"
    node_id: str
    ontology: str
    term_id: str
    label: str | None = None


class SetProteinStateGrounding(BaseModel):
    op: Literal["set_protein_state_grounding"] = "set_protein_state_grounding"
    node_id: str
    family_label: str
    members: list[OntologyTermProvenance] = []
    residues: list[str] = []
    resolved_to: str | None = None


class ResolveIsoform(BaseModel):
    op: Literal["resolve_isoform"] = "resolve_isoform"
    node_id: str
    resolved_to: str | None = None  # None clears the resolution


class MergeNodes(BaseModel):
    op: Literal["merge_nodes"] = "merge_nodes"
    node_id: str
    into_node_id: str


class SplitNode(BaseModel):
    op: Literal["split_node"] = "split_node"
    node_id: str
    new_label: str
    new_type: NodeType = NodeType.OTHER
    move_edge_ids: list[str] = []


class AddConnectedNode(BaseModel):
    op: Literal["add_connected_node"] = "add_connected_node"
    anchor_node_id: str
    new_label: str
    new_type: NodeType = NodeType.OTHER
    relation: str = "linked"
    direction: Literal["to", "from"] = "to"  # "to": anchor->new ; "from": new->anchor
    suggested_by: list[KGEdgeProvenance] = []


class ConnectNodes(BaseModel):
    op: Literal["connect_nodes"] = "connect_nodes"
    source_id: str
    target_id: str
    relation: str = "linked"
    suggested_by: list[KGEdgeProvenance] = []
    # When a user draws the edge directly, it is a user-proposed (not LLM) claim and
    # should not be ghosted. KG-derived connects ignore these (they stay KG+pending).
    proposal_source: ProposalSource = ProposalSource.LLM
    pending: bool = True


class RemoveEdge(BaseModel):
    op: Literal["remove_edge"] = "remove_edge"
    edge_id: str


class RemoveNode(BaseModel):
    op: Literal["remove_node"] = "remove_node"
    node_id: str  # also removes every edge incident to this node (cascade)


GraphEdit = (
    SetRelation | FlipEdge | SetTest | SplitEdge
    | SetLabel | SetNodeType | SetGrounding | SetProteinStateGrounding | ResolveIsoform
    | MergeNodes | SplitNode
    | AddConnectedNode | ConnectNodes | RemoveEdge | RemoveNode
)


class EdgeChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class EdgeChatTurn(BaseModel):
    reply: str
    proposed_edit: GraphEdit | None = None


def apply_graph_edit(
    graph: CausalGraph,
    edit: GraphEdit,
    new_id: Callable[[], str],
    now: Callable[[], str] = _utcnow_iso,
) -> CausalGraph:
    """Return a mutated copy of `graph` with `edit` applied. Pure (no persistence).

    Edge-creating edits stamp `proposal_source`/`validation_status`: app-inserted
    mechanism edges are ``system``+unvalidated; KG-neighbor-derived edges are
    ``kg``+``kg_supported_direct`` (with an audit `EdgeValidation`); plain
    LLM-proposed edges stay ``llm``+unvalidated drafts. `now` is injectable for tests."""
    g = graph.model_copy(deep=True)

    if isinstance(edit, (SetRelation, FlipEdge, SetTest, SplitEdge)):
        edge = g.get_edge(edit.edge_id)
        if edge is None:
            raise ValueError(f"no edge {edit.edge_id} in graph {g.id}")
    if isinstance(edit, SetRelation):
        edge.relation = edit.relation
        reset_edge_validation(edge, f"relation changed to '{edit.relation}'", now())
    elif isinstance(edit, FlipEdge):
        edge.source_id, edge.target_id = edge.target_id, edge.source_id
        reset_edge_validation(edge, "edge direction flipped", now())
    elif isinstance(edit, SetTest):
        edge.proposed_test = EdgeTest(
            pipeline=edit.pipeline, data_accession=edit.data_accession, expected=edit.expected
        )
    elif isinstance(edit, SplitEdge):
        source_id, target_id = edge.source_id, edge.target_id
        g.remove_edge(edit.edge_id)
        mechanism = Node(id=new_id(), type=edit.mechanism_type, label=edit.mechanism_label)
        g.add_node(mechanism)
        g.add_edge(Edge(id=new_id(), source_id=source_id, target_id=mechanism.id,
                        relation=edit.source_relation, pending=True,
                        proposal_source=ProposalSource.SYSTEM))
        g.add_edge(Edge(id=new_id(), source_id=mechanism.id, target_id=target_id,
                        relation=edit.target_relation, pending=True,
                        proposal_source=ProposalSource.SYSTEM))
    elif isinstance(edit, SetLabel):
        node = _require_node(g, edit.node_id)
        node.label = edit.label
    elif isinstance(edit, SetNodeType):
        node = _require_node(g, edit.node_id)
        node.type = edit.node_type
    elif isinstance(edit, SetGrounding):
        node = _require_node(g, edit.node_id)
        node.grounding = OntologyTermProvenance(
            ontology=edit.ontology, term_id=edit.term_id, label=edit.label
        )
    elif isinstance(edit, SetProteinStateGrounding):
        node = _require_node(g, edit.node_id)
        node.grounding = ProteinStateProvenance(
            family_label=edit.family_label,
            members=list(edit.members),
            modification=ProteinModification(residues=list(edit.residues)),
            resolved_to=edit.resolved_to,
        )
    elif isinstance(edit, ResolveIsoform):
        node = _require_node(g, edit.node_id)
        grounding = node.grounding
        if not isinstance(grounding, ProteinStateProvenance):
            raise ValueError(f"node {edit.node_id} has no protein-state grounding to resolve")
        if edit.resolved_to is not None and edit.resolved_to not in {
            m.term_id for m in grounding.members
        }:
            raise ValueError(
                f"{edit.resolved_to} is not a candidate isoform of '{grounding.family_label}'"
            )
        grounding.resolved_to = edit.resolved_to
    elif isinstance(edit, MergeNodes):
        if edit.node_id == edit.into_node_id:
            raise ValueError("cannot merge a node into itself")
        _require_node(g, edit.node_id)
        _require_node(g, edit.into_node_id)
        kept = []
        for e in g.edges:
            moved = e.source_id == edit.node_id or e.target_id == edit.node_id
            if e.source_id == edit.node_id:
                e.source_id = edit.into_node_id
            if e.target_id == edit.node_id:
                e.target_id = edit.into_node_id
            if e.source_id != e.target_id:
                if moved:  # an endpoint changed → its prior validations no longer apply
                    reset_edge_validation(e, f"endpoint merged into '{edit.into_node_id}'", now())
                kept.append(e)
        g.edges = kept
        g.remove_node(edit.node_id)
    elif isinstance(edit, SplitNode):
        _require_node(g, edit.node_id)
        incident_ids = {e.id for e in g.edges_incident(edit.node_id)}
        for eid in edit.move_edge_ids:
            if eid not in incident_ids:
                raise ValueError(f"edge {eid} not incident to node {edit.node_id}")
        new_node = Node(id=new_id(), type=edit.new_type, label=edit.new_label)
        g.add_node(new_node)
        for eid in edit.move_edge_ids:
            e = g.get_edge(eid)
            if e.source_id == edit.node_id:
                e.source_id = new_node.id
            if e.target_id == edit.node_id:
                e.target_id = new_node.id
            # this edge's endpoint moved → its prior validations no longer apply
            reset_edge_validation(e, f"endpoint moved to '{new_node.id}'", now())
    elif isinstance(edit, AddConnectedNode):
        _require_node(g, edit.anchor_node_id)
        new_node = Node(id=new_id(), type=edit.new_type, label=edit.new_label)
        g.add_node(new_node)
        src, tgt = (
            (edit.anchor_node_id, new_node.id) if edit.direction == "to"
            else (new_node.id, edit.anchor_node_id)
        )
        from_kg = bool(edit.suggested_by)
        new_edge = Edge(
            id=new_id(), source_id=src, target_id=tgt, relation=edit.relation,
            pending=True, suggested_by=list(edit.suggested_by),
            proposal_source=ProposalSource.KG if from_kg else ProposalSource.LLM,
        )
        if from_kg:
            record_validation(new_edge, _kg_validation(edit.suggested_by, now))
        g.add_edge(new_edge)
    elif isinstance(edit, ConnectNodes):
        _require_node(g, edit.source_id)
        _require_node(g, edit.target_id)
        # Match by EXACT direction: a reverse edge (target->source) is a different
        # directed claim and must not be enriched as if it were this one.
        existing = next(
            (e for e in g.edges
             if e.source_id == edit.source_id and e.target_id == edit.target_id),
            None,
        )
        if existing is not None:
            # Enrich the existing same-direction edge's provenance instead of adding a
            # parallel edge, and record the KG link as a validation on it.
            seen = {(p.source, p.reference) for p in existing.suggested_by}
            for p in edit.suggested_by:
                if (p.source, p.reference) not in seen:
                    existing.suggested_by.append(p)
            if edit.suggested_by:
                record_validation(existing, _kg_validation(edit.suggested_by, now))
        else:
            from_kg = bool(edit.suggested_by)
            new_edge = Edge(
                id=new_id(), source_id=edit.source_id, target_id=edit.target_id,
                relation=edit.relation,
                pending=True if from_kg else edit.pending,
                suggested_by=list(edit.suggested_by),
                proposal_source=ProposalSource.KG if from_kg else edit.proposal_source,
            )
            if from_kg:
                record_validation(new_edge, _kg_validation(edit.suggested_by, now))
            g.add_edge(new_edge)
    elif isinstance(edit, RemoveEdge):
        if g.get_edge(edit.edge_id) is None:
            raise ValueError(f"no edge {edit.edge_id} in graph {g.id}")
        g.remove_edge(edit.edge_id)
    elif isinstance(edit, RemoveNode):
        _require_node(g, edit.node_id)
        # cascade: drop edges incident to the node so none dangle
        g.edges = [
            e for e in g.edges
            if e.source_id != edit.node_id and e.target_id != edit.node_id
        ]
        g.remove_node(edit.node_id)
    return g


def _require_node(graph: CausalGraph, node_id: str) -> Node:
    node = graph.get_node(node_id)
    if node is None:
        raise ValueError(f"no node {node_id} in graph {graph.id}")
    return node


@runtime_checkable
class EdgeChatService(Protocol):
    def respond(self, graph: CausalGraph, edge_id: str,
                history: list[EdgeChatMessage], message: str) -> EdgeChatTurn: ...


class DemoEdgeChatService:
    """Deterministic: an explanatory reply, plus a keyword-routed sample edit."""

    def respond(self, graph: CausalGraph, edge_id: str,
                history: list[EdgeChatMessage], message: str) -> EdgeChatTurn:
        edge = graph.get_edge(edge_id)
        src = graph.get_node(edge.source_id).label if edge and graph.get_node(edge.source_id) else "?"
        tgt = graph.get_node(edge.target_id).label if edge and graph.get_node(edge.target_id) else "?"
        relation = edge.relation if edge else "?"
        reply = (
            f"This edge claims {src} {relation} {tgt}. It is currently "
            f"{edge.state.value if edge else 'unknown'}. Ask me to rename, flip, set a test, "
            f"or split it with a mechanism."
        )
        text = message.lower()
        proposed_edit: GraphEdit | None = None
        if edge is not None:
            if "split" in text:
                proposed_edit = SplitEdge(
                    edge_id=edge_id, mechanism_label="KRAS", mechanism_type=NodeType.TARGET,
                    source_relation="up-regulates activity", target_relation=relation,
                )
            elif "flip" in text or "backwards" in text or "reverse" in text:
                proposed_edit = FlipEdge(edge_id=edge_id)
            elif "rename" in text or "reword" in text:
                proposed_edit = SetRelation(edge_id=edge_id, relation="modulates")
            elif "test" in text or "pipeline" in text or "data" in text:
                proposed_edit = SetTest(
                    edge_id=edge_id, pipeline="nf-core/differentialabundance", data_accession="GSE-DEMO",
                )
        return EdgeChatTurn(reply=reply, proposed_edit=proposed_edit)


_EDGE_CHAT_SYSTEM = """You are refining one edge of a causal-hypothesis graph through conversation.
Answer the user's question about the edge, and — only if they clearly want a change — propose ONE edit.

Reply with ONLY a JSON object:
{"reply":"<plain-language answer>", "edit": <one edit object or null>}

An edit is one of:
  {"op":"set_relation","edge_id":"<id>","relation":"<new claim wording>"}
  {"op":"flip_edge","edge_id":"<id>"}
  {"op":"set_test","edge_id":"<id>","pipeline":"<nf-core/...>","data_accession":"<GSE...>","expected":"<effect>"}
  {"op":"split_edge","edge_id":"<id>","mechanism_label":"<gene/process>","mechanism_type":"target","source_relation":"<verb>","target_relation":"<verb>"}
Omit "edit" (or set null) when the user is just asking a question.
The context lists the edge's neighborhood; the bracketed [id] before each edge/node is the exact handle to put in an edit's "edge_id"/"node_id"."""


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.endswith("```"):
            t = t[: t.rfind("```")]
    return t.strip()


class LlmEdgeChatService:
    """LLM-authored edge conversation returning {reply, edit?} JSON."""

    def __init__(self, provider, model: str):
        self._provider = provider
        self._model = model

    def respond(self, graph: CausalGraph, edge_id: str,
                history: list[EdgeChatMessage], message: str) -> EdgeChatTurn:
        context = serialize_graph_for_llm(graph, focus_edge_ids=(edge_id,))
        convo = "\n".join(f"{m.role}: {m.content}" for m in history)
        user = f"{context}\n\nConversation so far:\n{convo or '(none)'}\n\nUser: {message}"
        raw = self._provider.create_message(
            messages=[{"role": "user", "content": user}],
            model=self._model, system=_EDGE_CHAT_SYSTEM, temperature=0.3,
        )
        try:
            payload = json.loads(_strip_fences(raw))
            reply = str(payload.get("reply") or "")
            edit_obj = payload.get("edit")
        except (json.JSONDecodeError, AttributeError):
            return EdgeChatTurn(reply="Sorry — I couldn't form a clear answer. Try rephrasing?")
        edit = _parse_edit(edit_obj) if edit_obj else None
        return EdgeChatTurn(reply=reply or "(no reply)", proposed_edit=edit)


def _parse_edit(obj) -> GraphEdit | None:
    op = obj.get("op")
    table = {"set_relation": SetRelation, "flip_edge": FlipEdge,
             "set_test": SetTest, "split_edge": SplitEdge,
             "set_label": SetLabel, "set_node_type": SetNodeType,
             "set_grounding": SetGrounding,
             "set_protein_state_grounding": SetProteinStateGrounding,
             "resolve_isoform": ResolveIsoform,
             "merge_nodes": MergeNodes, "split_node": SplitNode}
    model = table.get(op)
    if model is None:
        return None
    try:
        return model.model_validate(obj)
    except Exception:
        return None


@runtime_checkable
class NodeChatService(Protocol):
    def respond(self, graph: CausalGraph, node_id: str,
                history: list[EdgeChatMessage], message: str) -> EdgeChatTurn: ...


class DemoNodeChatService:
    """Deterministic: an explanatory reply, plus a keyword-routed sample node edit."""

    def respond(self, graph: CausalGraph, node_id: str,
                history: list[EdgeChatMessage], message: str) -> EdgeChatTurn:
        node = graph.get_node(node_id)
        grounded = (
            f"{node.grounding.ontology}:{node.grounding.term_id}"
            if node and node.grounding else "ungrounded"
        )
        reply = (
            f"This node is {node.label if node else '?'} "
            f"(type {node.type.value if node else '?'}, {grounded}). "
            f"Ask me to rename, change its type, re-ground it, merge, or split it."
        )
        text = message.lower()
        edit: GraphEdit | None = None
        if node is not None:
            if "rename" in text or "label" in text:
                edit = SetLabel(node_id=node_id, label=f"{node.label} (refined)")
            elif "type" in text:
                edit = SetNodeType(node_id=node_id, node_type=NodeType.PATHWAY)
            elif "ground" in text or "ontology" in text:
                edit = SetGrounding(node_id=node_id, ontology="UniProt", term_id="P00533", label=node.label)
            elif "merge" in text:
                into = None
                for e in graph.edges_incident(node_id):
                    into = e.target_id if e.source_id == node_id else e.source_id
                    break
                if into:
                    edit = MergeNodes(node_id=node_id, into_node_id=into)
            elif "split" in text:
                incident = graph.edges_incident(node_id)
                move = [incident[0].id] if incident else []
                edit = SplitNode(node_id=node_id, new_label=f"{node.label}-b",
                                 new_type=node.type, move_edge_ids=move)
        return EdgeChatTurn(reply=reply, proposed_edit=edit)


_NODE_CHAT_SYSTEM = """You are refining one node of a causal-hypothesis graph through conversation.
Answer the user's question about the node, and — only if they clearly want a change — propose ONE edit.

Reply with ONLY a JSON object: {"reply":"<answer>", "edit": <one edit object or null>}
An edit is one of:
  {"op":"set_label","node_id":"<id>","label":"<new label>"}
  {"op":"set_node_type","node_id":"<id>","node_type":"<target|pathway|phenotype|cell_type|tissue|disease|compound|other>"}
  {"op":"set_grounding","node_id":"<id>","ontology":"<UniProt|EFO|MONDO|...>","term_id":"<id>","label":"<name>"}
  {"op":"merge_nodes","node_id":"<id>","into_node_id":"<other node id>"}
  {"op":"split_node","node_id":"<id>","new_label":"<name>","new_type":"target","move_edge_ids":["<edge id>"]}
Omit "edit" (or null) when the user is just asking a question.
The context lists the node's neighborhood; the bracketed [id] before each node/edge is the exact handle to put in an edit's "node_id"/"edge_id"."""


class LlmNodeChatService:
    """LLM-authored node conversation returning {reply, edit?} JSON."""

    def __init__(self, provider, model: str):
        self._provider = provider
        self._model = model

    def respond(self, graph: CausalGraph, node_id: str,
                history: list[EdgeChatMessage], message: str) -> EdgeChatTurn:
        context = serialize_graph_for_llm(graph, focus_node_ids=(node_id,))
        convo = "\n".join(f"{m.role}: {m.content}" for m in history)
        user = f"{context}\n\nConversation so far:\n{convo or '(none)'}\n\nUser: {message}"
        raw = self._provider.create_message(
            messages=[{"role": "user", "content": user}],
            model=self._model, system=_NODE_CHAT_SYSTEM, temperature=0.3,
        )
        try:
            payload = json.loads(_strip_fences(raw))
            reply = str(payload.get("reply") or "")
            edit_obj = payload.get("edit")
        except (json.JSONDecodeError, AttributeError):
            return EdgeChatTurn(reply="Sorry — I couldn't form a clear answer. Try rephrasing?")
        edit = _parse_edit(edit_obj) if edit_obj else None
        return EdgeChatTurn(reply=reply or "(no reply)", proposed_edit=edit)
