"""Causal-graph domain types: nodes (ontology-grounded), edges (mechanistic claims)."""

from enum import Enum

from pydantic import BaseModel, Field

from quration.hypothesis.epistemics import (
    EdgeValidation,
    EdgeValidationStatus,
    ProposalSource,
)
from quration.hypothesis.provenance import KGEdgeProvenance, NodeGrounding, OntologyTermProvenance


class NodeType(str, Enum):
    """The biological entity a node represents."""

    TARGET = "target"  # gene / protein
    PATHWAY = "pathway"
    PHENOTYPE = "phenotype"
    CELL_TYPE = "cell_type"
    TISSUE = "tissue"
    DISEASE = "disease"
    COMPOUND = "compound"
    OTHER = "other"


class EdgeState(str, Enum):
    """The test-status of a mechanistic claim (an edge)."""

    UNTESTED = "untested"
    # A feasibility assessment exists — we established whether this claim *could* be
    # measured — but nothing has measured it. Every entry the wired runner produces
    # is one of these, so this is the state most real edges reach. Distinguished from
    # EXAMINED because "no method exists for this readout" and "we ran the method and
    # it was inconclusive" are different scientific situations, and they were
    # collapsing to the same word.
    # See docs/decisions/2026-07-30-what-a-measurement-may-change-on-an-edge.md
    ASSESSED = "assessed"
    EXAMINED = "examined"  # a measurement landed; the ledger records carry the facts
    # Deprecated truth-stamps — no longer emitted by rollup_edge (north-star §2.2).
    # Deprecated truth-stamps — no longer emitted by rollup_edge (north-star §2.2).
    # Retained only until all call sites are migrated; do not produce these.
    CONTESTED = "contested"
    SUPPORTED = "supported"
    REFUTED = "refuted"


class NodePosition(BaseModel):
    """Canvas coordinates for a node. Cosmetic layout only — never affects claims."""

    x: float
    y: float


class Node(BaseModel):
    """A biological entity. `grounding` ties it to a canonical ontology term."""

    id: str
    type: NodeType
    label: str
    grounding: NodeGrounding | None = None
    # Canvas layout; None = unplaced (frontend falls back to auto-layout). Additive.
    position: NodePosition | None = None


class EdgeTest(BaseModel):
    """A user-refined intended test for an edge (preferred over the supervisor default)."""

    pipeline: str | None = None
    data_accession: str | None = None
    expected: str | None = None


class Edge(BaseModel):
    """A mechanistic claim: source --relation--> target.

    `state`/`confidence` are derived from the *pipeline-evidence* ledger (see
    evidence.py). `validation_status` is the broader *epistemic* summary (KG /
    literature / dataset support, or contradiction), derived from the append-only
    `validations` audit. `proposal_source` records who proposed the edge. A grounded
    endpoint never changes these — entity grounding lives on the node. `suggested_by`
    holds display-only KG provenance; `pending` marks a ghosted, not-yet-approved edge.
    """

    id: str
    source_id: str
    target_id: str
    relation: str
    state: EdgeState = EdgeState.UNTESTED
    confidence: float = 0.0  # supporting fraction; interpret only with `state` (0.0 also means UNTESTED)
    suggested_by: list[KGEdgeProvenance] = Field(default_factory=list)
    pending: bool = False
    proposed_test: EdgeTest | None = None
    # --- epistemic state (additive; see epistemics.py) ---
    # SYSTEM, not LLM. This defaulted to LLM, so 10 of the 15 Edge construction
    # sites that omit it were asserting that a language model proposed the
    # relation — including the offline demo seams, where no model runs. An
    # unstated provenance is unknown provenance; claiming a source is worse than
    # admitting none, because the epistemics layer exists to be trusted on
    # exactly this question. State it explicitly wherever it is known.
    proposal_source: ProposalSource = ProposalSource.SYSTEM
    validation_status: EdgeValidationStatus = EdgeValidationStatus.UNVALIDATED
    validations: list[EdgeValidation] = Field(default_factory=list)
    # transient: set by the API read path from endpoint grounding; never authoritative.
    display_status: EdgeValidationStatus | None = None


class CausalGraph(BaseModel):
    """A causal hypothesis: ontology-grounded nodes + mechanistic-claim edges.

    `query` is the originating natural-language question. Mutation helpers enforce
    referential integrity (no dangling edges, no duplicate ids).
    """

    id: str
    query: str
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)

    def get_node(self, node_id: str) -> Node | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def get_edge(self, edge_id: str) -> Edge | None:
        return next((e for e in self.edges if e.id == edge_id), None)

    def add_node(self, node: Node) -> None:
        if self.get_node(node.id) is not None:
            raise ValueError(f"duplicate node id: {node.id}")
        self.nodes.append(node)

    def add_edge(self, edge: Edge) -> None:
        if self.get_edge(edge.id) is not None:
            raise ValueError(f"duplicate edge id: {edge.id}")
        for endpoint in (edge.source_id, edge.target_id):
            if self.get_node(endpoint) is None:
                raise ValueError(f"unknown endpoint node: {endpoint}")
        self.edges.append(edge)

    def remove_edge(self, edge_id: str) -> None:
        self.edges = [e for e in self.edges if e.id != edge_id]

    def remove_node(self, node_id: str) -> None:
        self.nodes = [n for n in self.nodes if n.id != node_id]

    def untested_edges(self) -> list[Edge]:
        """Edges nothing has looked at yet. Excludes ASSESSED, so an edge whose only
        record is a coverage gap is not re-proposed forever."""
        return [e for e in self.edges if e.state == EdgeState.UNTESTED]

    def unmeasured_edges(self) -> list[Edge]:
        """Edges with no measurement — whether or not they were assessed.

        The primitive a loop-selection policy needs, and the honest denominator for
        "how much of this graph is actually tested". `untested_edges` deliberately
        answers a narrower question, and using it to mean "still to do" is what let
        the loop stop while every edge was unmeasured. Which of these the loop should
        re-propose is left open in the decision note; a GROUNDED assessment means a
        method exists and the edge is ready, a COVERAGE_GAP means it is not.
        """
        return [
            e
            for e in self.edges
            if e.state in (EdgeState.UNTESTED, EdgeState.ASSESSED)
        ]

    def edges_incident(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if node_id in (e.source_id, e.target_id)]


def mark_llm_authored(edges: list[Edge]) -> list[Edge]:
    """Stamp edges a model actually authored, in place, and return them.

    `Edge.proposal_source` defaults to SYSTEM — "a derivation" — because the
    previous default of LLM claimed a model had proposed a relation on every
    edge, including ones no model had touched. That default is right, but it
    means a real LLM proposal has to say so explicitly, and only the code that
    called the model knows.

    `HypothesisLoop.build_from_skeleton` did this inline while `start`'s
    suggesters did not, so the graph you get from `/hypothesis/start` reported
    `proposal_source: "system"` on edges a model had just written. That errs
    safe — it understates rather than overstates — but it erases the one
    distinction the enum exists to make: a consumer could not tell a model's
    hypothesis from a deterministic derivation. One helper, so the three call
    sites cannot drift apart again.

    Validation status is reset with it deliberately: a freshly authored seed is
    an unvalidated draft no matter how it arrived, and validation happens later
    against a KG, a dataset or the literature — never at seed time.
    """
    for edge in edges:
        edge.proposal_source = ProposalSource.LLM
        edge.validation_status = EdgeValidationStatus.UNVALIDATED
        edge.validations = []
    return edges
