"""REST API over the checkpointed hypothesis loop.

Conversational services (seeding / edge-chat / node-chat) run on the
deterministic ``Demo*`` seams by default, and on the real ``Llm*`` services
when a usable LLM provider is configured (e.g. ``QURATION_PROVIDER=claude_subscription``).
"""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from quration.config import get_config
from quration.hypothesis.epistemics import display_status
from quration.hypothesis.evidence import EvidenceEntry
from quration.hypothesis.graph import CausalGraph, NodePosition
from quration.hypothesis.observability import (
    GraphSummary,
    HypothesisEvent,
    set_event_sink,
    traced_op,
)
from quration.hypothesis.orchestrator.checkpoint import ProposedTest, StartResult
from quration.hypothesis.orchestrator.dataset_search import (
    DatasetCandidate,
    DatasetSearchService,
    DemoDatasetSearchService,
    RealDatasetSearchService,
)
from quration.hypothesis.orchestrator.demo import build_demo_loop
from quration.hypothesis.orchestrator.edge_chat import (
    DemoEdgeChatService,
    DemoNodeChatService,
    EdgeChatMessage,
    EdgeChatService,
    EdgeChatTurn,
    GraphEdit,
    LlmEdgeChatService,
    LlmNodeChatService,
    NodeChatService,
    SetGrounding,
)
from quration.hypothesis.orchestrator.grounding import (
    DemoGroundingService,
    FallbackGroundingService,
    GroundingProposal,
    GroundingService,
    OntologyGroundingService,
)
from quration.hypothesis.orchestrator.evaluation_plan import EvaluationPlan
from quration.hypothesis.orchestrator.evaluation_plan_service import EvaluationPlanService
from quration.hypothesis.orchestrator.readout_resolver import DemoReadoutResolver, RealReadoutResolver
from quration.hypothesis.orchestrator.kg_knowledge import (
    DemoKGService,
    EdgeKnowledge,
    KGService,
    Neighbor,
)
from quration.hypothesis.orchestrator.loop import HypothesisLoop
from quration.hypothesis.orchestrator.seeding import (
    DemoSeedingService,
    LlmSeedingService,
    SeedAnswer,
    SeedingService,
    SeedingStep,
    SeedSkeleton,
)
from quration.hypothesis.provenance import OntologyTermProvenance
from quration.hypothesis.store import SqliteHypothesisRepository
from quration.llm.providers import get_model_for_config, get_provider_from_config

logger = logging.getLogger(__name__)

# Providers that ``get_provider_from_config`` knows how to construct. Only an
# explicit demo sentinel keeps the synthetic Demo seams; configured but
# unsupported providers must fail visibly instead of masquerading as demo data.
_REAL_PROVIDERS = {"anthropic", "openrouter", "claude_subscription"}
_DEMO_PROVIDERS = {"demo", "offline_demo"}
_UNIMPLEMENTED_PROVIDERS = {"aws_bedrock", "gcp_vertex"}

router = APIRouter(prefix="/hypothesis", tags=["Hypothesis Engine"])

_loop: HypothesisLoop | None = None
_repo: SqliteHypothesisRepository | None = None


def _db_path() -> str:
    """Where the durable hypothesis store lives. Override with QURATION_HYPOTHESIS_DB
    (use ``:memory:`` for an ephemeral store, e.g. in tests)."""
    return os.environ.get("QURATION_HYPOTHESIS_DB", "./data/hypothesis.db")


def get_repo() -> SqliteHypothesisRepository:
    """Process-wide durable repository. Also registered as the observability event
    sink, so every hypothesis op's event trail lands in the same SQLite store."""
    global _repo
    if _repo is None:
        path = _db_path()
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        _repo = SqliteHypothesisRepository(path)
        set_event_sink(_repo)
    return _repo


def get_loop() -> HypothesisLoop:
    """Process-wide loop, backed by the durable SQLite repository so every query's
    graph survives restarts. Real (correlation-backed) runs in real mode, demo otherwise."""
    global _loop
    if _loop is None:
        repo = get_repo()
        if _real_mode():
            from quration.hypothesis.orchestrator.real_pipeline import build_real_loop

            _loop = build_real_loop(repository=repo)
        else:
            _loop = build_demo_loop(repository=repo)
    return _loop


def _real_mode() -> bool:
    """True for a supported live provider; false only for explicit demo mode.

    The single 'is this a live run?' signal: it gates both the LLM chat seams
    and live ontology grounding so the app is coherently all-demo or all-live.
    """
    provider = (get_config().llm.provider or "").lower()
    if provider in _REAL_PROVIDERS:
        return True
    if provider in _DEMO_PROVIDERS:
        return False
    if provider in _UNIMPLEMENTED_PROVIDERS:
        raise RuntimeError(
            f"LLM provider {provider!r} is configured but is not implemented by "
            "the Dogma hypothesis engine; choose a supported provider or set "
            "QURATION_PROVIDER=demo explicitly."
        )
    raise RuntimeError(f"Unknown Dogma LLM provider: {provider!r}")


def _optimuskg_active() -> bool:
    """True when the real OptimusKG knowledge-graph backend is the active KG."""
    return _real_mode() and os.environ.get("QURATION_GROUNDING", "").lower() == "optimuskg"


def with_display_status(graph: CausalGraph) -> CausalGraph:
    """Return a copy of the graph with each edge's transient `display_status` set
    from its endpoints' grounding. This is the ONLY place the
    `entity_grounded_relation_unchecked` distinction is produced — grounding a node
    never writes edge state, so the derivation lives at the read boundary."""
    view = graph.model_copy(deep=True)
    for edge in view.edges:
        src, tgt = view.get_node(edge.source_id), view.get_node(edge.target_id)
        edge.display_status = display_status(
            edge.validation_status,
            src_grounded=bool(src and src.grounding),
            tgt_grounded=bool(tgt and tgt.grounding),
        )
    return view


def _seed_tier() -> str:
    """Return the model tier to use for seeding, driven by ``QURATION_SEED_TIER``.

    Accepts ``"smart"`` (default) or ``"fast"``; any other value silently falls
    back to ``"smart"`` so misconfigured envs degrade gracefully.
    """
    tier = os.environ.get("QURATION_SEED_TIER", "smart").strip().lower()
    return tier if tier in ("smart", "fast") else "smart"


def _resolve_chat_llm() -> tuple[object, str] | None:
    """Return ``(provider, smart_model)`` when a real LLM provider is configured
    and constructible; ``None`` to fall back to the deterministic Demo seams.

    Construction failures (e.g. a missing API key) degrade to ``None`` so the app
    always starts — the demo brain is the safety net, never a crash.
    """
    if not _real_mode():
        return None
    try:
        return get_provider_from_config(), get_model_for_config(tier="smart")
    except Exception as exc:  # missing creds, unreachable CLI, etc.
        logger.warning("LLM provider unavailable, using demo seams: %s", exc)
        return None


_grounding: GroundingService | None = None


def get_grounding_service() -> GroundingService:
    """Grounding backend: OptimusKG (local KG) or live ontologies in real mode,
    deterministic Demo otherwise. `QURATION_GROUNDING=optimuskg` selects the
    local-KG backend (type-agnostic; needs the `optimuskg` package + ~49MB cache)."""
    global _grounding
    if _grounding is None:
        if not _real_mode():
            _grounding = DemoGroundingService()
        elif os.environ.get("QURATION_GROUNDING", "live").lower() == "optimuskg":
            from quration.data_sources.ontologies import OntologyMapper
            from quration.data_sources.uniprot import UniProtClient
            from quration.hypothesis.orchestrator.optimuskg_grounding import (
                OptimusKGGroundingService,
            )

            # OptimusKG first (fast local gene/disease/drug); fall back to public
            # ontologies (OLS/UniProt) so pathway/phenotype/disease nodes the local
            # KG can't ground still resolve to a standard ontology term.
            _grounding = FallbackGroundingService([
                OptimusKGGroundingService(),
                OntologyGroundingService(mapper=OntologyMapper(), uniprot=UniProtClient()),
            ])
        else:
            from quration.data_sources.ontologies import OntologyMapper
            from quration.data_sources.uniprot import UniProtClient

            _grounding = OntologyGroundingService(mapper=OntologyMapper(), uniprot=UniProtClient())
    return _grounding


def _build_grounder() -> GroundingService | None:
    """The FAST, local grounding backend to apply at build time (genes/proteins/
    drugs/diseases) — no network. Returns None when only a network backend (OLS)
    is available, so build never blocks on remote lookups; those stay on-demand."""
    svc = get_grounding_service()
    if isinstance(svc, FallbackGroundingService):
        return svc._services[0] if svc._services else None  # the local KG backend
    if isinstance(svc, DemoGroundingService):
        return svc
    return None  # live OLS-only: network-bound, skip auto-grounding at build


def _autoground_skeleton(skeleton: SeedSkeleton) -> int:
    """Pre-ground a skeleton's nodes with the fast local backend, in place. Only
    the molecular/disease nodes it recognizes get grounded; pathways/phenotypes
    miss locally and are left for the on-demand (OLS) button. Best-effort: any
    failure leaves the node ungrounded, never breaks the build."""
    try:
        grounder = _build_grounder()
    except Exception:
        return 0
    if grounder is None:
        return 0
    grounded = 0
    for node in skeleton.nodes:
        if node.grounding is not None:
            continue
        try:
            proposal = grounder.ground(node)
        except Exception:
            continue
        edit = proposal.proposed_edit
        if proposal.found and isinstance(edit, SetGrounding):
            node.grounding = OntologyTermProvenance(
                ontology=edit.ontology, term_id=edit.term_id, label=edit.label
            )
            grounded += 1
    return grounded


_dataset_search: DatasetSearchService | None = None


def get_dataset_search_service() -> DatasetSearchService:
    """Live GEO search in real mode, deterministic Demo otherwise."""
    global _dataset_search
    if _dataset_search is None:
        _dataset_search = RealDatasetSearchService() if _real_mode() else DemoDatasetSearchService()
    return _dataset_search


_plan_service: EvaluationPlanService | None = None


def get_plan_service() -> EvaluationPlanService:
    """EvaluationPlanService singleton. Real resolver + methods-graph provider in real mode,
    Demo twins otherwise so no-API-key CI stays green."""
    global _plan_service
    if _plan_service is None:
        if _real_mode():
            from quration.broker.method_broker import _provider_from_env

            resolver = RealReadoutResolver(
                provider=get_provider_from_config(),
                model=get_model_for_config(tier="smart"),
            )
            _plan_service = EvaluationPlanService(
                resolver=resolver,
                grounding_provider=_provider_from_env(),
            )
        else:
            _plan_service = EvaluationPlanService(
                resolver=DemoReadoutResolver(),
                grounding_provider=None,
            )
    return _plan_service


_seeding: SeedingService | None = None


def get_seeding_service() -> SeedingService:
    """Process-wide seeding service. Real LlmSeedingService when a provider resolves, else Demo.

    The model tier is controlled by ``QURATION_SEED_TIER`` (``"smart"`` by default,
    ``"fast"`` for lower-latency seeding). Other services (edge-chat, node-chat) are
    unaffected and always use the smart tier.
    """
    global _seeding
    if _seeding is None:
        llm = _resolve_chat_llm()
        if llm is not None:
            provider, _ = llm
            model = get_model_for_config(tier=_seed_tier())
            _seeding = LlmSeedingService(provider, model)
        else:
            _seeding = DemoSeedingService()
    return _seeding


_edge_chat: EdgeChatService | None = None


def get_edge_chat_service() -> EdgeChatService:
    """Process-wide edge-chat service.

    Real LlmEdgeChatService when a provider resolves, else Demo.
    """
    global _edge_chat
    if _edge_chat is None:
        llm = _resolve_chat_llm()
        _edge_chat = LlmEdgeChatService(*llm) if llm else DemoEdgeChatService()
    return _edge_chat


_node_chat: NodeChatService | None = None


def get_node_chat_service() -> NodeChatService:
    """Process-wide node-chat service.

    Real LlmNodeChatService when a provider resolves, else Demo.
    """
    global _node_chat
    if _node_chat is None:
        llm = _resolve_chat_llm()
        _node_chat = LlmNodeChatService(*llm) if llm else DemoNodeChatService()
    return _node_chat


_kg: KGService | None = None


def get_kg_service() -> KGService:
    """KG knowledge ('what's known' + neighbor expansion). The real OptimusKG
    backend when `QURATION_GROUNDING=optimuskg` in real mode; deterministic Demo
    otherwise (so demo mode and tests never need the optional `optimuskg` dep)."""
    global _kg
    if _kg is None:
        if _real_mode() and os.environ.get("QURATION_GROUNDING", "").lower() == "optimuskg":
            from quration.hypothesis.orchestrator.optimuskg_kg import OptimusKGKnowledgeService

            _kg = OptimusKGKnowledgeService()
        else:
            _kg = DemoKGService()
    return _kg


class StartRequest(BaseModel):
    query: str


class SeedRequest(BaseModel):
    query: str
    answers: list[SeedAnswer] = []


class BuildRequest(BaseModel):
    query: str
    skeleton: SeedSkeleton


class NextResponse(BaseModel):
    proposed: ProposedTest | None = None


class ApproveRequest(BaseModel):
    proposed: ProposedTest


class EdgeChatRequest(BaseModel):
    history: list[EdgeChatMessage] = []
    message: str


class NodeChatRequest(BaseModel):
    history: list[EdgeChatMessage] = []
    message: str


class ApplyEditRequest(BaseModel):
    edit: GraphEdit


class LayoutRequest(BaseModel):
    positions: dict[str, NodePosition]  # node_id -> position


@router.post("/start", response_model=StartResult)
def start(req: StartRequest, loop: HypothesisLoop = Depends(get_loop)) -> StartResult:
    with traced_op("start", query=req.query) as op:
        result = loop.start(req.query)
        op.graph_id = result.graph_id
        graph = loop.get_graph(result.graph_id) if result.graph_id else None
        edges = graph.edges if graph else []
        sources = sorted({p.source for e in edges for p in e.suggested_by})
        if not edges:
            path = "empty"
        elif sources:
            path = "kg"
        else:
            path = "llm_fallback"
        op.detail = {
            "kind": getattr(result.kind, "value", result.kind),
            "n_nodes": len(graph.nodes) if graph else 0,
            "n_edges": len(edges),
            "sources_used": sources,
            "suggester_path": path,
            "noncommercial_allowed": os.environ.get(
                "QURATION_ALLOW_NONCOMMERCIAL_KG", "1"
            ).strip().lower() not in ("0", "false", "no", ""),
        }
        return result


@router.post("/seed", response_model=None)
def seed(
    req: SeedRequest, svc: SeedingService = Depends(get_seeding_service)
) -> SeedingStep:
    # Seeding has no graph yet; a failure here is recorded with graph_id=None and
    # surfaces in /events/failed (the raw claude -p exchange captured for debugging).
    with traced_op("seed", query=req.query) as op:
        step = svc.next_step(req.query, req.answers)
        op.detail = {"kind": getattr(step, "kind", None)}
        return step


@router.post("/build", response_model=StartResult)
def build(req: BuildRequest, loop: HypothesisLoop = Depends(get_loop)) -> StartResult:
    with traced_op("build", query=req.query) as op:
        # Pre-ground molecular nodes with the fast local backend so the canvas
        # comes up grounded; conceptual nodes stay on the on-demand button.
        n_grounded = _autoground_skeleton(req.skeleton)
        result = loop.build_from_skeleton(req.query, req.skeleton)
        op.graph_id = result.graph_id
        op.detail = {
            "n_nodes": len(req.skeleton.nodes),
            "n_edges": len(req.skeleton.edges),
            "n_grounded": n_grounded,
        }
        return result


@router.get("/{graph_id}", response_model=CausalGraph)
def get_graph(graph_id: str, loop: HypothesisLoop = Depends(get_loop)) -> CausalGraph:
    graph = loop.get_graph(graph_id)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"unknown graph: {graph_id}")
    return with_display_status(graph)


@router.put("/{graph_id}/layout", response_model=CausalGraph)
def set_layout(
    graph_id: str, req: LayoutRequest, loop: HypothesisLoop = Depends(get_loop)
) -> CausalGraph:
    """Persist cosmetic node positions. Deliberately NOT wrapped in traced_op — a
    layout change is not an epistemic claim and must not enter the claim audit."""
    try:
        return with_display_status(loop.set_layout(graph_id, req.positions))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{graph_id}/next", response_model=NextResponse)
def next_proposal(graph_id: str, loop: HypothesisLoop = Depends(get_loop)) -> NextResponse:
    try:
        return NextResponse(proposed=loop.next_proposal(graph_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{graph_id}/approve", response_model=EvidenceEntry)
def approve(
    graph_id: str, req: ApproveRequest, loop: HypothesisLoop = Depends(get_loop)
) -> EvidenceEntry:
    with traced_op("approve", graph_id=graph_id) as h:
        try:
            result = loop.approve(graph_id, req.proposed)
            h.detail = {"edge_id": req.proposed.edge_id}
            return result
        except KeyError as exc:
            h.status = "not_found"
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{graph_id}/edges/{edge_id}/chat", response_model=EdgeChatTurn)
def edge_chat(
    graph_id: str, edge_id: str, req: EdgeChatRequest,
    loop: HypothesisLoop = Depends(get_loop),
    svc: EdgeChatService = Depends(get_edge_chat_service),
) -> EdgeChatTurn:
    graph = loop.get_graph(graph_id)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"unknown graph: {graph_id}")
    if graph.get_edge(edge_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown edge: {edge_id}")
    with traced_op("edge_chat", graph_id=graph_id, query=graph.query) as op:
        turn = svc.respond(graph, edge_id, req.history, req.message)
        op.detail = {"has_edit": turn.proposed_edit is not None}
        return turn


@router.post("/{graph_id}/apply-edit", response_model=CausalGraph)
def apply_edit(
    graph_id: str, req: ApplyEditRequest, loop: HypothesisLoop = Depends(get_loop)
) -> CausalGraph:
    try:
        return with_display_status(loop.apply_edge_edit(graph_id, req.edit))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{graph_id}/nodes/{node_id}/chat", response_model=EdgeChatTurn)
def node_chat(
    graph_id: str, node_id: str, req: NodeChatRequest,
    loop: HypothesisLoop = Depends(get_loop),
    svc: NodeChatService = Depends(get_node_chat_service),
) -> EdgeChatTurn:
    graph = loop.get_graph(graph_id)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"unknown graph: {graph_id}")
    if graph.get_node(node_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown node: {node_id}")
    with traced_op("node_chat", graph_id=graph_id, query=graph.query) as op:
        turn = svc.respond(graph, node_id, req.history, req.message)
        op.detail = {"has_edit": turn.proposed_edit is not None}
        return turn


@router.post("/{graph_id}/nodes/{node_id}/ground", response_model=GroundingProposal)
def ground_node(
    graph_id: str, node_id: str,
    loop: HypothesisLoop = Depends(get_loop),
    svc: GroundingService = Depends(get_grounding_service),
) -> GroundingProposal:
    """Look up the node's canonical ontology term and propose a set_grounding edit."""
    graph = loop.get_graph(graph_id)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"unknown graph: {graph_id}")
    node = graph.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"unknown node: {node_id}")
    with traced_op("ground", graph_id=graph_id, query=graph.query) as op:
        proposal = svc.ground(node)
        op.status = "ok" if proposal.found else "not_found"
        op.detail = {"node": node.label, "found": proposal.found, "summary": proposal.summary}
        return proposal


@router.post("/{graph_id}/edges/{edge_id}/known", response_model=EdgeKnowledge)
def edge_known(
    graph_id: str, edge_id: str,
    loop: HypothesisLoop = Depends(get_loop),
    kg: KGService = Depends(get_kg_service),
) -> EdgeKnowledge:
    """What the knowledge graph knows about this edge (relation + source DBs)."""
    graph = loop.get_graph(graph_id)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"unknown graph: {graph_id}")
    edge = graph.get_edge(edge_id)
    if edge is None:
        raise HTTPException(status_code=404, detail=f"unknown edge: {edge_id}")
    src, tgt = graph.get_node(edge.source_id), graph.get_node(edge.target_id)
    if src is None or tgt is None:
        raise HTTPException(status_code=404, detail="edge endpoints not found")
    with traced_op("known", graph_id=graph_id, query=graph.query) as op:
        knowledge = kg.known(src, tgt)
        # Record the check as an edge validation (kg_supported_direct / unsupported),
        # separate from any node grounding. The edge stays visible either way.
        kg_source = "optimuskg" if _optimuskg_active() else "demo-kg"
        loop.record_known(graph_id, edge_id, knowledge, kg_source=kg_source)
        op.status = "ok" if knowledge.found else "not_found"
        op.detail = {
            "found": knowledge.found,
            "n_sources": len(knowledge.sources),
            "validation_status": (
                "kg_supported_direct" if knowledge.found else "unsupported"
            ),
        }
        return knowledge


class ExpandResponse(BaseModel):
    neighbors: list[Neighbor]


@router.post("/{graph_id}/nodes/{node_id}/expand", response_model=ExpandResponse)
def expand_node(
    graph_id: str, node_id: str,
    loop: HypothesisLoop = Depends(get_loop),
    kg: KGService = Depends(get_kg_service),
) -> ExpandResponse:
    """Top real KG neighbors of this node, offerable as new connected nodes."""
    graph = loop.get_graph(graph_id)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"unknown graph: {graph_id}")
    node = graph.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"unknown node: {node_id}")
    # Annotate neighbors already in the graph with their node id (the UI offers a
    # provenance edge to the existing node instead of a duplicate). Never suggest
    # the anchor node itself.
    with traced_op("expand", graph_id=graph_id, query=graph.query) as op:
        present = {_norm_label(n.label): n.id for n in graph.nodes}
        anchor_norm = _norm_label(node.label)
        neighbors = []
        for nb in kg.expand(node):
            norm = _norm_label(nb.symbol)
            if norm == anchor_norm:
                continue
            nb.existing_node_id = present.get(norm)
            neighbors.append(nb)
        op.detail = {"node": node.label, "n_neighbors": len(neighbors)}
        return ExpandResponse(neighbors=neighbors)


def _norm_label(label: str) -> str:
    """Normalize a label/symbol for dedup: drop a parenthetical, trim, lowercase.
    e.g. 'GRB2 (adapter)' and 'GRB2' both -> 'grb2'."""
    return label.split("(")[0].strip().lower()


class FindDataResponse(BaseModel):
    candidates: list[DatasetCandidate]


@router.post("/{graph_id}/edges/{edge_id}/find-data", response_model=FindDataResponse)
def find_data(
    graph_id: str, edge_id: str,
    loop: HypothesisLoop = Depends(get_loop),
    svc: DatasetSearchService = Depends(get_dataset_search_service),
) -> FindDataResponse:
    """Search GEO for datasets relevant to this edge; attach via /apply-edit (SetTest)."""
    graph = loop.get_graph(graph_id)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"unknown graph: {graph_id}")
    if graph.get_edge(edge_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown edge: {edge_id}")
    return FindDataResponse(candidates=svc.find(graph, edge_id))


@router.get("/{graph_id}/edges/{edge_id}/plan", response_model=EvaluationPlan)
def edge_plan(
    graph_id: str, edge_id: str,
    loop: HypothesisLoop = Depends(get_loop),
    svc: EvaluationPlanService = Depends(get_plan_service),
) -> EvaluationPlan:
    """Return the biology-derived evaluation plan skeleton for one edge (no dataset resolved yet)."""
    graph = loop.get_graph(graph_id)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"unknown graph: {graph_id}")
    with traced_op("edge_plan", graph_id=graph_id) as h:
        try:
            plan = svc.build_skeleton(graph, edge_id)
        except KeyError as exc:
            h.status = "not_found"
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        h.detail = {"edge_id": edge_id, "modality": plan.ideal_readout.modality}
        return plan


@router.post("/{graph_id}/edges/{edge_id}/resolve", response_model=EvaluationPlan)
def resolve_edge(
    graph_id: str, edge_id: str,
    loop: HypothesisLoop = Depends(get_loop),
    svc: EvaluationPlanService = Depends(get_plan_service),
    search: DatasetSearchService = Depends(get_dataset_search_service),
) -> EvaluationPlan:
    """Resolve the ideal readout to the best available public dataset (GEO + PRIDE).

    Persists exactly one EvidenceRecord via svc.resolve; does NOT flip edge state.
    """
    graph = loop.get_graph(graph_id)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"unknown graph: {graph_id}")
    if graph.get_edge(edge_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown edge: {edge_id}")
    with traced_op("resolve_readout", graph_id=graph_id) as h:
        candidates = search.find_multi(graph, edge_id)
        plan = svc.resolve(graph, edge_id, candidates, loop._repo)
        h.detail = {"edge_id": edge_id, "directness": plan.directness}
        return plan


# --- History + observability (durable store) --------------------------------


@router.get("", response_model=list[GraphSummary])
def list_graphs(repo: SqliteHypothesisRepository = Depends(get_repo)) -> list[GraphSummary]:
    """Every stored query's graph, newest first — the history rail. `status` is
    'error' for graphs whose ops failed, so failed runs are revisitable."""
    return repo.list_graphs()


@router.delete("", response_model=None)
def clear_history(repo: SqliteHypothesisRepository = Depends(get_repo)) -> dict:
    """Delete ALL saved graphs (and their evidence + event trail). Clean slate."""
    return {"deleted": repo.delete_all_graphs()}


@router.delete("/{graph_id}", response_model=None)
def delete_graph(
    graph_id: str, repo: SqliteHypothesisRepository = Depends(get_repo)
) -> dict:
    """Delete one saved graph (and its evidence + event trail)."""
    if not repo.delete_graph(graph_id):
        raise HTTPException(status_code=404, detail=f"unknown graph: {graph_id}")
    return {"deleted": True}


@router.get("/events/failed", response_model=list[HypothesisEvent])
def failed_events(
    limit: int = 100, repo: SqliteHypothesisRepository = Depends(get_repo)
) -> list[HypothesisEvent]:
    """Recent failed operations across all queries — including failed seeds that
    never produced a graph (graph_id is null)."""
    return repo.failed_events(limit)


@router.get("/{graph_id}/events", response_model=list[HypothesisEvent])
def graph_events(
    graph_id: str, repo: SqliteHypothesisRepository = Depends(get_repo)
) -> list[HypothesisEvent]:
    """The full operation trail for one graph (seed/build/ground/expand/known/chat),
    with captured raw LLM I/O — the 'why did this fail' view."""
    return repo.events_for_graph(graph_id)
