"""A durable, stdlib-``sqlite3``-backed hypothesis repository + event trail.

This satisfies the sync :class:`~quration.hypothesis.repository.HypothesisRepository`
Protocol with the same semantics as ``InMemoryHypothesisRepository`` — in
particular the evidence rollup: ``save_graph`` reapplies stored evidence and
recomputes each edge's ``(state, confidence)`` before persisting, and
``add_evidence`` validates the edge exists, appends, and recomputes that edge.

It also implements the :class:`~quration.hypothesis.observability.EventSink`
Protocol (``append_event``) plus listing/inspection helpers, so a single store
can back both persistence and observability.

Concurrency: a single shared connection is guarded by a process-local lock. WAL
is enabled for on-disk databases (skipped for ``":memory:"``).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from quration.hypothesis.evidence import (
    EvidenceEntry,
    EvidenceRecord,
    edge_claim_signature,
    recompute_edge_evidence,
    refresh_execution_identity,
)
from quration.hypothesis.graph import CausalGraph
from quration.hypothesis.observability import GraphSummary, HypothesisEvent

logger = logging.getLogger("quration.hypothesis")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS graphs (
    id          TEXT PRIMARY KEY,
    query       TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    graph_json  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    graph_id    TEXT NOT NULL,
    edge_id     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    entry_json  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_evidence_ge ON evidence(graph_id, edge_id);

CREATE TABLE IF NOT EXISTS evidence_records (
    graph_id    TEXT NOT NULL,
    edge_id     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    record_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_records_ge ON evidence_records(graph_id, edge_id);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    trace_id    TEXT,
    graph_id    TEXT,
    query       TEXT,
    op          TEXT NOT NULL,
    status      TEXT NOT NULL,
    latency_ms  REAL,
    detail_json TEXT,
    raw_input   TEXT,
    raw_output  TEXT,
    error       TEXT
);
CREATE INDEX IF NOT EXISTS ix_events_graph ON events(graph_id);
CREATE INDEX IF NOT EXISTS ix_events_status ON events(status);
"""


class SqliteHypothesisRepository:
    """Durable repository backed by a single stdlib ``sqlite3`` connection."""

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        *,
        now: Callable[[], str] | None = None,
    ) -> None:
        path = str(db_path)
        self._is_memory = path == ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # Reentrant: FastAPI runs sync routes in a threadpool, so reads and writes
        # hit this one connection concurrently — every access is lock-guarded.
        self._lock = threading.RLock()
        self._now = now or (lambda: datetime.now(timezone.utc).isoformat())

        # WAL gives durable, concurrent-reader behavior for file DBs; it is
        # meaningless (and unsupported) for an in-memory database.
        if not self._is_memory:
            self._conn.execute("PRAGMA journal_mode=WAL")

        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # --- HypothesisRepository Protocol ------------------------------------

    def save_graph(self, graph: CausalGraph) -> None:
        with self._lock:
            now = self._now()
            # Reapply any stored evidence so a freshly-built graph object does not
            # silently reset edge state (mirrors InMemory). Mutate edges in-place
            # BEFORE serializing, so the persisted graph_json reflects rollup.
            for edge in graph.edges:
                refresh_execution_identity(graph, edge, self._evidence_rows(graph.id, edge.id))
                recompute_edge_evidence(edge, self._evidence_rows(graph.id, edge.id), now)
            graph_json = graph.model_dump_json()
            self._conn.execute(
                """
                INSERT INTO graphs (id, query, status, created_at, updated_at, graph_json)
                VALUES (?, ?, 'active', ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    query=excluded.query,
                    updated_at=excluded.updated_at,
                    graph_json=excluded.graph_json
                """,
                (graph.id, graph.query, now, now, graph_json),
            )
            self._conn.commit()

    def get_graph(self, graph_id: str) -> CausalGraph | None:
        with self._lock:
            return self._get_graph_unlocked(graph_id)

    def add_evidence(self, graph_id: str, entry: EvidenceEntry) -> None:
        with self._lock:
            graph = self._get_graph_unlocked(graph_id)
            edge = graph.get_edge(entry.edge_id) if graph is not None else None
            if edge is None:
                raise ValueError(f"no edge {entry.edge_id} in graph {graph_id}")

            for old in self._evidence_rows(graph_id, entry.edge_id):
                if entry.execution_receipt and getattr(old.provenance, "run_id", None) == getattr(entry.provenance, "run_id", None):
                    if old.model_dump() == entry.model_dump():
                        return
                    raise ValueError("conflicting receipt for existing execution")
            now = self._now()
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
            self._conn.execute(
                "INSERT INTO evidence (graph_id, edge_id, created_at, entry_json) "
                "VALUES (?, ?, ?, ?)",
                (graph_id, entry.edge_id, now, entry.model_dump_json()),
            )
            # Recompute this edge from ONLY the evidence matching its current claim
            # signature, then re-persist. Stale-signature evidence stays in the ledger.
            refresh_execution_identity(graph, edge, self._evidence_rows(graph_id, entry.edge_id))
            recompute_edge_evidence(edge, self._evidence_rows(graph_id, entry.edge_id), now)
            self._conn.execute(
                "UPDATE graphs SET graph_json=?, updated_at=? WHERE id=?",
                (graph.model_dump_json(), now, graph_id),
            )
            self._conn.commit()

    def evidence_for_edge(self, graph_id: str, edge_id: str) -> list[EvidenceEntry]:
        with self._lock:
            return self._evidence_rows(graph_id, edge_id)

    def add_evidence_record(self, graph_id: str, record: EvidenceRecord) -> None:
        with self._lock:
            now = self._now()
            self._conn.execute(
                "INSERT INTO evidence_records (graph_id, edge_id, created_at, record_json) "
                "VALUES (?, ?, ?, ?)",
                (graph_id, record.edge_id, now, record.model_dump_json()),
            )
            self._conn.commit()

    def evidence_records_for(self, graph_id: str, edge_id: str) -> list[EvidenceRecord]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT record_json FROM evidence_records WHERE graph_id=? AND edge_id=? "
                "ORDER BY created_at",
                (graph_id, edge_id),
            ).fetchall()
        return [EvidenceRecord.model_validate_json(r["record_json"]) for r in rows]

    def delete_graph(self, graph_id: str) -> bool:
        """Delete a graph and everything scoped to it (its evidence + event trail).
        Returns True if a graph row existed."""
        with self._lock:
            cur = self._conn.execute("DELETE FROM graphs WHERE id=?", (graph_id,))
            self._conn.execute("DELETE FROM evidence WHERE graph_id=?", (graph_id,))
            self._conn.execute("DELETE FROM evidence_records WHERE graph_id=?", (graph_id,))
            self._conn.execute("DELETE FROM events WHERE graph_id=?", (graph_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def delete_all_graphs(self) -> int:
        """Clear all saved history: every graph + its evidence + the event trail.
        Returns the number of graphs removed."""
        with self._lock:
            cur = self._conn.execute("DELETE FROM graphs")
            self._conn.execute("DELETE FROM evidence")
            self._conn.execute("DELETE FROM evidence_records")
            self._conn.execute("DELETE FROM events")
            self._conn.commit()
            return cur.rowcount

    # --- EventSink + observability helpers --------------------------------

    def append_event(self, event: HypothesisEvent) -> None:
        # Telemetry must never raise into the caller (see observability.py).
        try:
            with self._lock:
                detail_json = json.dumps(event.detail) if event.detail else None
                self._conn.execute(
                    """
                    INSERT INTO events
                        (ts, trace_id, graph_id, query, op, status,
                         latency_ms, detail_json, raw_input, raw_output, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.ts,
                        event.trace_id,
                        event.graph_id,
                        event.query,
                        event.op,
                        event.status,
                        event.latency_ms,
                        detail_json,
                        event.raw_input,
                        event.raw_output,
                        event.error,
                    ),
                )
                # A failed op on a known graph marks the whole graph errored.
                if event.status == "error" and event.graph_id is not None:
                    self._conn.execute(
                        "UPDATE graphs SET status='error' WHERE id=?",
                        (event.graph_id,),
                    )
                self._conn.commit()
        except Exception:  # pragma: no cover - defensive telemetry guard
            logger.warning("sqlite event-sink append failed", exc_info=True)

    def list_graphs(self) -> list[GraphSummary]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, query, status, created_at, updated_at, graph_json "
                "FROM graphs ORDER BY created_at DESC, rowid DESC"
            ).fetchall()
        summaries: list[GraphSummary] = []
        for row in rows:
            data = json.loads(row["graph_json"])
            summaries.append(
                GraphSummary(
                    id=row["id"],
                    query=row["query"],
                    status=row["status"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    n_nodes=len(data.get("nodes", [])),
                    n_edges=len(data.get("edges", [])),
                )
            )
        return summaries

    def events_for_graph(self, graph_id: str) -> list[HypothesisEvent]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE graph_id=? ORDER BY id ASC", (graph_id,)
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def failed_events(self, limit: int = 100) -> list[HypothesisEvent]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM events WHERE status='error' ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    # --- internals --------------------------------------------------------

    def _get_graph_unlocked(self, graph_id: str) -> CausalGraph | None:
        row = self._conn.execute(
            "SELECT graph_json FROM graphs WHERE id=?", (graph_id,)
        ).fetchone()
        if row is None:
            return None
        graph = CausalGraph.model_validate_json(row["graph_json"])
        for edge in graph.edges:
            refresh_execution_identity(graph, edge, self._evidence_rows(graph_id, edge.id))
            recompute_edge_evidence(edge, self._evidence_rows(graph_id, edge.id), self._now())
        return graph

    def _evidence_rows(self, graph_id: str, edge_id: str) -> list[EvidenceEntry]:
        rows = self._conn.execute(
            "SELECT entry_json FROM evidence WHERE graph_id=? AND edge_id=? "
            "ORDER BY rowid ASC",
            (graph_id, edge_id),
        ).fetchall()
        return [EvidenceEntry.model_validate_json(r["entry_json"]) for r in rows]

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> HypothesisEvent:
        detail = json.loads(row["detail_json"]) if row["detail_json"] else None
        return HypothesisEvent(
            ts=row["ts"],
            trace_id=row["trace_id"],
            graph_id=row["graph_id"],
            query=row["query"],
            op=row["op"],
            status=row["status"],
            latency_ms=row["latency_ms"],
            detail=detail,
            raw_input=row["raw_input"],
            raw_output=row["raw_output"],
            error=row["error"],
        )
