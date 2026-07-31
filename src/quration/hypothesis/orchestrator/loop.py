"""The checkpointed hypothesis loop and its injectable seams."""

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable
from uuid import uuid4

from quration.hypothesis.connectors.base import EdgeSuggester, SuggestionResult
from quration.hypothesis.epistemics import (
    EdgeValidation,
    EdgeValidationStatus,
    ProposalSource,
    record_validation,
)
from quration.hypothesis.evidence import EvidenceEntry
from quration.hypothesis.graph import CausalGraph, NodePosition, mark_llm_authored
from quration.hypothesis.orchestrator.checkpoint import (
    MethodChoice,
    PipelineResult,
    ProposedTest,
    QueryKind,
    StartResult,
)
from quration.hypothesis.orchestrator.edge_chat import GraphEdit, apply_graph_edit
from quration.hypothesis.orchestrator.kg_knowledge import EdgeKnowledge
from quration.hypothesis.orchestrator.seeding import SeedSkeleton
from quration.hypothesis.provenance import KGEdgeProvenance
from quration.hypothesis.repository import HypothesisRepository

logger = logging.getLogger(__name__)


@runtime_checkable
class Supervisor(Protocol):
    """The LLM judgment seam. Every method is a proposal; nothing here runs a pipeline."""

    def triage(self, query: str) -> QueryKind: ...

    def seeds_for(self, query: str) -> list[str]: ...

    def propose_test(self, graph: CausalGraph) -> ProposedTest | None: ...

    def interpret(self, proposed: ProposedTest, result: PipelineResult) -> EvidenceEntry: ...


@runtime_checkable
class PipelineRunner(Protocol):
    """The pipeline-execution seam (broker + Nextflow)."""

    def run(self, proposed: ProposedTest) -> PipelineResult: ...


@runtime_checkable
class MethodSelector(Protocol):
    """Recommends which method fits a proposed test. Advisory; never runs anything."""

    def select(self, proposed: ProposedTest, graph: CausalGraph) -> MethodChoice | None: ...


class NullMethodSelector:
    """Default selector: recommends nothing (loop behaves exactly as before)."""

    def select(self, proposed: ProposedTest, graph: CausalGraph) -> MethodChoice | None:
        return None


class HypothesisLoop:
    """Step-driven orchestrator. The caller advances one checkpoint at a time."""

    def __init__(
        self,
        repository: HypothesisRepository,
        suggester: EdgeSuggester,
        supervisor: Supervisor,
        runner: PipelineRunner,
        selector: MethodSelector | None = None,
        id_factory: Callable[[], str] | None = None,
        empty_seed_fallback: Callable[[str], SuggestionResult] | None = None,
    ):
        self._repo = repository
        self._suggester = suggester
        self._supervisor = supervisor
        self._runner = runner
        self._selector = selector or NullMethodSelector()
        self._id_factory = id_factory or (lambda: uuid4().hex)
        self._empty_seed_fallback = empty_seed_fallback

    def get_graph(self, graph_id: str) -> CausalGraph | None:
        """Read a stored graph (for API/UI rendering). None if unknown."""
        return self._repo.get_graph(graph_id)

    def start(self, query: str) -> StartResult:
        kind = self._supervisor.triage(query)
        if kind == QueryKind.SIMPLE:
            return StartResult(kind=kind)
        seeds = (
            self._supervisor.seeds_for(query)
            if getattr(self._suggester, "uses_seeds", True)
            else []
        )
        suggestion: SuggestionResult = self._suggester.expand(seeds, query=query)
        if not suggestion.edges and self._empty_seed_fallback is not None:
            # KGs returned nothing for these seeds — author a live LLM skeleton
            # instead of persisting a blank canvas.
            suggestion = self._empty_seed_fallback(query)
        graph_id = self._id_factory()
        graph = CausalGraph(
            id=graph_id,
            query=query,
            nodes=list(suggestion.nodes),
            edges=list(suggestion.edges),
        )
        self._repo.save_graph(graph)
        return StartResult(kind=kind, graph_id=graph_id)

    def build_from_skeleton(self, query: str, skeleton: SeedSkeleton) -> StartResult:
        """Persist an already-authored seed skeleton as the candidate graph.

        Unlike `start`, this skips triage + auto-seeding: the caller supplies the
        nodes/edges (from conversational seeding).
        """
        graph_id = self._id_factory()
        # Drop any authored edge whose endpoints aren't in the skeleton (an LLM can
        # reference a node it didn't include) — keep the graph internally consistent.
        node_ids = {node.id for node in skeleton.nodes}
        edges = [
            edge for edge in skeleton.edges
            if edge.source_id in node_ids and edge.target_id in node_ids
        ]
        # A seed is the LLM's *proposal*: every seed edge is an unvalidated draft,
        # regardless of how the skeleton arrived. Validation happens later (KG /
        # dataset / literature), never at seed time.
        #
        # Shared with the `/start` suggesters rather than repeated here — this was
        # the only site that stamped, so `start` silently reported model-authored
        # edges as SYSTEM.
        mark_llm_authored(edges)
        graph = CausalGraph(
            id=graph_id,
            query=query,
            nodes=list(skeleton.nodes),
            edges=edges,
        )
        self._repo.save_graph(graph)
        return StartResult(kind=QueryKind.INVESTIGATIVE, graph_id=graph_id)

    def apply_edge_edit(self, graph_id: str, edit: GraphEdit) -> CausalGraph:
        """Apply a structured edge edit (from edge-chat) to a stored graph and save it."""
        graph = self._repo.get_graph(graph_id)
        if graph is None:
            raise KeyError(f"unknown graph: {graph_id}")
        updated = apply_graph_edit(graph, edit, self._id_factory)
        self._repo.save_graph(updated)
        return updated

    def record_known(
        self, graph_id: str, edge_id: str, knowledge: EdgeKnowledge,
        kg_source: str = "knowledge_graph",
    ) -> CausalGraph:
        """Record a KG known-check as an edge validation (separate from grounding).

        A direct hit → `kg_supported_direct`, meaning the KG reports a *direct link*
        between the two entities — NOT confirmation of the edge's specific causal
        relation/direction (the KG relation is captured in the evidence + rationale).
        A miss → `unsupported` (the edge stays visible, explicitly marked). Idempotent:
        a re-check overwrites the KG channel's prior result via the validation summary."""
        graph = self._repo.get_graph(graph_id)
        if graph is None:
            raise KeyError(f"unknown graph: {graph_id}")
        edge = graph.get_edge(edge_id)
        if edge is None:
            raise KeyError(f"edge {edge_id!r} not in graph {graph_id!r}")
        now = datetime.now(timezone.utc).isoformat()
        if knowledge.found:
            kg_relation = knowledge.relations[0] if knowledge.relations else "direct"
            validation = EdgeValidation(
                status=EdgeValidationStatus.KG_SUPPORTED_DIRECT,
                source=ProposalSource.KG,
                # reference is the KG's OWN relation, so it's never confused with the
                # edge's displayed relation.
                evidence=KGEdgeProvenance(
                    source=kg_source, reference=kg_relation,
                    statement_count=len(knowledge.sources)),
                rationale=(
                    f"KG reports a direct link ('{kg_relation}') vs the claim "
                    f"'{edge.relation}'; supports a direct connection, not the specific "
                    f"relation. {len(knowledge.sources)} source(s): "
                    + ", ".join(knowledge.sources[:5])),
                kg_source=kg_source,
                created_at=now,
            )
        else:
            validation = EdgeValidation(
                status=EdgeValidationStatus.UNSUPPORTED,
                source=ProposalSource.KG,
                rationale=knowledge.summary,
                kg_source=kg_source,
                created_at=now,
            )
        record_validation(edge, validation)
        self._repo.save_graph(graph)
        return graph

    def next_proposal(self, graph_id: str) -> ProposedTest | None:
        graph = self._repo.get_graph(graph_id)
        if graph is None:
            raise KeyError(f"unknown graph: {graph_id}")
        proposed = self._supervisor.propose_test(graph)
        if proposed is not None:
            try:
                proposed.method = self._selector.select(proposed, graph)
            except Exception:  # advisory only — never break test proposal
                logger.warning("method selection failed for %s", graph_id, exc_info=True)
                proposed.method = None
        return proposed

    def approve(self, graph_id: str, proposed: ProposedTest) -> EvidenceEntry:
        graph = self._repo.get_graph(graph_id)
        if graph is None:
            raise KeyError(f"unknown graph: {graph_id}")
        if graph.get_edge(proposed.edge_id) is None:
            raise KeyError(f"edge {proposed.edge_id!r} not in graph {graph_id!r}")
        result = self._runner.run(proposed)
        entry = self._supervisor.interpret(proposed, result)
        self._repo.add_evidence(graph_id, entry)
        return entry

    def set_layout(
        self, graph_id: str, positions: dict[str, NodePosition]
    ) -> CausalGraph:
        """Persist cosmetic node positions. Not a claim edit: no event, no validation
        change. Unknown node ids are ignored."""
        graph = self._repo.get_graph(graph_id)
        if graph is None:
            raise KeyError(f"unknown graph: {graph_id}")
        for node in graph.nodes:
            pos = positions.get(node.id)
            if pos is not None:
                node.position = pos
        self._repo.save_graph(graph)
        return graph
