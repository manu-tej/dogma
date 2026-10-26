"""Hypothesis persistence interface + an in-memory implementation.

The repository owns the one cross-cutting behavior: when evidence is added for an
edge, that edge's (state, confidence) is recomputed from its full ledger via
`rollup_edge`. A SQLAlchemy-backed implementation can satisfy the same protocol later.

Evidence is scoped per (graph_id, edge_id): each investigation owns its own ledger,
so two graphs may legitimately reuse an edge id without cross-contaminating state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from datetime import datetime, timezone

from quration.hypothesis.evidence import (
    EvidenceEntry,
    edge_claim_signature,
    recompute_edge_evidence,
    refresh_execution_identity,
)
from quration.hypothesis.graph import CausalGraph

if TYPE_CHECKING:
    from quration.hypothesis.evidence import EvidenceRecord


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@runtime_checkable
class HypothesisRepository(Protocol):
    """Storage contract for causal graphs and their edge evidence."""

    def save_graph(self, graph: CausalGraph) -> None: ...

    def get_graph(self, graph_id: str) -> CausalGraph | None: ...

    def add_evidence(self, graph_id: str, entry: EvidenceEntry) -> None: ...

    def evidence_for_edge(self, graph_id: str, edge_id: str) -> list[EvidenceEntry]: ...

    def add_evidence_record(self, graph_id: str, record: "EvidenceRecord") -> None: ...

    def evidence_records_for(self, graph_id: str, edge_id: str) -> "list[EvidenceRecord]": ...


class InMemoryHypothesisRepository:
    """Dict-backed repository for tests and the early loop orchestrator."""

    def __init__(self) -> None:
        self._graphs: dict[str, CausalGraph] = {}
        # Evidence keyed by (graph_id, edge_id) so investigations stay independent.
        self._evidence: dict[tuple[str, str], list[EvidenceEntry]] = {}
        # EvidenceRecord store — grounding/resolution facts; never triggers rollup.
        self._records: dict[tuple[str, str], list[EvidenceRecord]] = {}

    def save_graph(self, graph: CausalGraph) -> None:
        self._graphs[graph.id] = graph
        # Reapply any evidence already accumulated for this graph's edges, so a
        # freshly-constructed graph object does not silently reset edge state.
        for edge in graph.edges:
            self._recompute_edge(graph.id, edge.id)

    def get_graph(self, graph_id: str) -> CausalGraph | None:
        graph = self._graphs.get(graph_id)
        if graph is not None:
            for edge in graph.edges:
                self._recompute_edge(graph_id, edge.id)
        return graph

    def add_evidence(self, graph_id: str, entry: EvidenceEntry) -> None:
        graph = self._graphs.get(graph_id)
        edge = graph.get_edge(entry.edge_id) if graph is not None else None
        if edge is None:
            raise ValueError(f"no edge {entry.edge_id} in graph {graph_id}")
        for old in self._evidence.get((graph_id, entry.edge_id), []):
            if entry.execution_receipt and getattr(old.provenance, "run_id", None) == getattr(entry.provenance, "run_id", None):
                if old.model_dump() == entry.model_dump():
                    return
                raise ValueError("conflicting receipt for existing execution")
        # Stamp the claim signature the evidence was gathered against.
        if entry.claim_signature is not None and tuple(entry.claim_signature) != edge_claim_signature(edge):
            raise ValueError("evidence claim identity differs from current edge")
        from quration.hypothesis.evidence import execution_context_current
        if not execution_context_current(entry):
            raise ValueError("evidence pinned inputs have changed")
        if entry.execution_context_digest is not None and entry.execution_context_digest != edge.execution_context_digest:
            raise ValueError("evidence execution context is stale")
        if entry.claim_signature is None:
            entry.claim_signature = edge_claim_signature(edge)
        self._evidence.setdefault((graph_id, entry.edge_id), []).append(entry)
        self._recompute_edge(graph_id, entry.edge_id)

    def evidence_for_edge(self, graph_id: str, edge_id: str) -> list[EvidenceEntry]:
        return list(self._evidence.get((graph_id, edge_id), []))

    def add_evidence_record(self, graph_id: str, record: EvidenceRecord) -> None:
        self._records.setdefault((graph_id, record.edge_id), []).append(record)

    def evidence_records_for(self, graph_id: str, edge_id: str) -> list[EvidenceRecord]:
        return list(self._records.get((graph_id, edge_id), []))

    def _recompute_edge(self, graph_id: str, edge_id: str) -> None:
        graph = self._graphs.get(graph_id)
        if graph is None:
            return
        edge = graph.get_edge(edge_id)
        if edge is None:
            return
        # Recompute state + dataset validation from ONLY the evidence matching the
        # edge's current claim signature (idempotent). Evidence gathered under an old
        # signature stays in the ledger but won't re-promote the edited claim.
        refresh_execution_identity(graph, edge, self._evidence.get((graph_id, edge_id), []))
        recompute_edge_evidence(edge, self._evidence.get((graph_id, edge_id), []), _now_iso())
