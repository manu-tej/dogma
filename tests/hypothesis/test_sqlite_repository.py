"""Tests for the durable sqlite-backed hypothesis repository.

Uses real sqlite files (via tmp_path) and ":memory:" — no mocks. A deterministic
``now`` is injected so created_at/updated_at ordering is assertable.
"""

import itertools
import threading

import pytest

from quration.hypothesis.evidence import EvidenceDirection, EvidenceEntry, EvidenceKind
from quration.hypothesis.graph import CausalGraph, Edge, EdgeState, Node, NodeType
from quration.hypothesis.observability import HypothesisEvent
from quration.hypothesis.provenance import OntologyTermProvenance, PipelineRunProvenance
from quration.hypothesis.repository import InMemoryHypothesisRepository
from quration.hypothesis.store import SqliteHypothesisRepository


def _counter_now():
    """Deterministic monotonically-increasing ISO-ish timestamps."""
    seq = itertools.count(1)
    return lambda: f"2026-01-01T00:00:{next(seq):02d}+00:00"


def _graph_with_one_edge(gid: str = "g1", query: str = "does X drive Y?") -> CausalGraph:
    g = CausalGraph(id=gid, query=query)
    g.add_node(Node(id="n1", type=NodeType.TARGET, label="X"))
    g.add_node(Node(id="n2", type=NodeType.PHENOTYPE, label="Y"))
    g.add_edge(Edge(id="e1", source_id="n1", target_id="n2", relation="drives"))
    return g


def _rich_graph() -> CausalGraph:
    g = CausalGraph(id="rich", query="multi-node investigation")
    g.add_node(
        Node(
            id="n1",
            type=NodeType.TARGET,
            label="TP53",
            grounding=OntologyTermProvenance(ontology="HGNC", term_id="HGNC:11998", label="TP53"),
        )
    )
    g.add_node(Node(id="n2", type=NodeType.PATHWAY, label="apoptosis"))
    g.add_node(Node(id="n3", type=NodeType.PHENOTYPE, label="tumor growth"))
    g.add_edge(Edge(id="e1", source_id="n1", target_id="n2", relation="activates"))
    g.add_edge(Edge(id="e2", source_id="n2", target_id="n3", relation="suppresses"))
    return g


def _evidence(direction: EvidenceDirection, edge_id: str = "e1") -> EvidenceEntry:
    return EvidenceEntry(
        kind=EvidenceKind.MEASUREMENT,
        edge_id=edge_id,
        direction=direction,
        provenance=PipelineRunProvenance(run_id="r1", data_accession="GSE1"),
    )


def test_save_and_get_graph_round_trips_losslessly(tmp_path):
    db = tmp_path / "h.db"
    repo = SqliteHypothesisRepository(db, now=_counter_now())
    repo.save_graph(_rich_graph())

    got = repo.get_graph("rich")
    assert got is not None
    assert got.id == "rich"
    assert got.query == "multi-node investigation"
    assert [n.id for n in got.nodes] == ["n1", "n2", "n3"]
    assert got.get_node("n1").label == "TP53"
    assert got.get_node("n1").grounding.term_id == "HGNC:11998"
    assert got.get_node("n2").type == NodeType.PATHWAY
    assert [e.id for e in got.edges] == ["e1", "e2"]
    assert got.get_edge("e1").relation == "activates"
    assert got.get_edge("e2").relation == "suppresses"
    repo.close()


def test_get_graph_unknown_returns_none(tmp_path):
    repo = SqliteHypothesisRepository(tmp_path / "h.db", now=_counter_now())
    assert repo.get_graph("nope") is None
    repo.close()


def test_add_evidence_for_unknown_edge_raises(tmp_path):
    repo = SqliteHypothesisRepository(tmp_path / "h.db", now=_counter_now())
    repo.save_graph(_graph_with_one_edge())
    with pytest.raises(ValueError, match="no edge ghost in graph g1"):
        repo.add_evidence("g1", _evidence(EvidenceDirection.SUPPORTS, edge_id="ghost"))
    repo.close()


def test_add_evidence_for_unknown_graph_raises(tmp_path):
    repo = SqliteHypothesisRepository(tmp_path / "h.db", now=_counter_now())
    with pytest.raises(ValueError, match="no edge e1 in graph missing"):
        repo.add_evidence("missing", _evidence(EvidenceDirection.SUPPORTS))
    repo.close()


def test_add_evidence_records_and_durability_across_restart(tmp_path):
    """KEY DURABILITY TEST: a fresh repo on the same file reflects recomputed state."""
    db = tmp_path / "h.db"
    repo = SqliteHypothesisRepository(db, now=_counter_now())
    repo.save_graph(_graph_with_one_edge())
    assert repo.get_graph("g1").get_edge("e1").state == EdgeState.UNTESTED

    repo.add_evidence("g1", _evidence(EvidenceDirection.SUPPORTS))
    edge = repo.get_graph("g1").get_edge("e1")
    assert edge.state == EdgeState.EXAMINED
    assert edge.confidence == 0.0
    assert len(repo.evidence_for_edge("g1", "e1")) == 1
    repo.close()

    # Simulate a process restart: brand-new repo, same file.
    repo2 = SqliteHypothesisRepository(db, now=_counter_now())
    survived = repo2.get_graph("g1").get_edge("e1")
    assert survived.state == EdgeState.EXAMINED
    assert survived.confidence == 0.0
    assert len(repo2.evidence_for_edge("g1", "e1")) == 1
    repo2.close()


def test_resave_preserves_created_at_and_bumps_updated_at(tmp_path):
    repo = SqliteHypothesisRepository(tmp_path / "h.db", now=_counter_now())
    repo.save_graph(_graph_with_one_edge())
    first = repo.list_graphs()[0]
    created_at = first.created_at
    updated_at = first.updated_at

    repo.save_graph(_graph_with_one_edge())  # update
    second = repo.list_graphs()[0]
    assert second.created_at == created_at
    assert second.updated_at != updated_at
    assert second.updated_at > updated_at
    repo.close()


def test_list_graphs_newest_first_with_counts(tmp_path):
    repo = SqliteHypothesisRepository(tmp_path / "h.db", now=_counter_now())
    repo.save_graph(_graph_with_one_edge("g1", "first"))
    repo.save_graph(_rich_graph())

    summaries = repo.list_graphs()
    assert [s.id for s in summaries] == ["rich", "g1"]  # newest (rich) first
    rich = summaries[0]
    assert rich.query == "multi-node investigation"
    assert rich.status == "active"
    assert rich.n_nodes == 3
    assert rich.n_edges == 2
    g1 = summaries[1]
    assert g1.n_nodes == 2
    assert g1.n_edges == 1
    repo.close()


def test_error_event_flips_graph_status_success_does_not(tmp_path):
    repo = SqliteHypothesisRepository(tmp_path / "h.db", now=_counter_now())
    repo.save_graph(_graph_with_one_edge())

    repo.append_event(HypothesisEvent(ts="t", op="ok_op", status="ok", graph_id="g1"))
    assert repo.list_graphs()[0].status == "active"

    repo.append_event(HypothesisEvent(ts="t", op="boom", status="error", graph_id="g1"))
    assert repo.list_graphs()[0].status == "error"
    repo.close()


def test_failed_events_includes_null_graph_seed_newest_first(tmp_path):
    repo = SqliteHypothesisRepository(tmp_path / "h.db", now=_counter_now())
    repo.append_event(HypothesisEvent(ts="t", op="seed", status="error", graph_id=None, error="first"))
    repo.append_event(HypothesisEvent(ts="t", op="seed", status="error", graph_id=None, error="second"))
    repo.append_event(HypothesisEvent(ts="t", op="ok", status="ok", graph_id=None))

    failed = repo.failed_events()
    assert len(failed) == 2
    assert failed[0].error == "second"  # newest first
    assert failed[1].error == "first"
    assert all(e.graph_id is None for e in failed)
    assert all(e.status == "error" for e in failed)
    repo.close()


def test_events_for_graph_insertion_order_with_detail(tmp_path):
    repo = SqliteHypothesisRepository(tmp_path / "h.db", now=_counter_now())
    repo.append_event(
        HypothesisEvent(ts="t", op="a", status="ok", graph_id="g1", detail={"k": 1, "nested": [1, 2]})
    )
    repo.append_event(HypothesisEvent(ts="t", op="b", status="ok", graph_id="g1", detail=None))
    repo.append_event(HypothesisEvent(ts="t", op="c", status="ok", graph_id="other"))

    events = repo.events_for_graph("g1")
    assert [e.op for e in events] == ["a", "b"]
    assert events[0].detail == {"k": 1, "nested": [1, 2]}
    assert events[1].detail is None
    repo.close()


def test_in_memory_works_too():
    repo = SqliteHypothesisRepository(":memory:", now=_counter_now())
    repo.save_graph(_graph_with_one_edge())
    repo.add_evidence("g1", _evidence(EvidenceDirection.SUPPORTS))
    assert repo.get_graph("g1").get_edge("e1").state == EdgeState.EXAMINED
    repo.close()


def test_behavioral_parity_with_in_memory(tmp_path):
    """Same ops on InMemory and Sqlite yield identical edge (state, confidence)."""
    sq = SqliteHypothesisRepository(tmp_path / "h.db", now=_counter_now())
    mem = InMemoryHypothesisRepository()

    for repo in (sq, mem):
        repo.save_graph(_graph_with_one_edge())
        repo.add_evidence("g1", _evidence(EvidenceDirection.SUPPORTS))
        repo.add_evidence("g1", _evidence(EvidenceDirection.REFUTES))

    sq_edge = sq.get_graph("g1").get_edge("e1")
    mem_edge = mem.get_graph("g1").get_edge("e1")
    assert (sq_edge.state, sq_edge.confidence) == (mem_edge.state, mem_edge.confidence)
    assert sq_edge.state == EdgeState.EXAMINED
    sq.close()


def test_state_stays_examined_as_records_accumulate(tmp_path):
    repo = SqliteHypothesisRepository(tmp_path / "h.db", now=_counter_now())
    repo.save_graph(_graph_with_one_edge())
    repo.add_evidence("g1", _evidence(EvidenceDirection.SUPPORTS))
    repo.add_evidence("g1", _evidence(EvidenceDirection.REFUTES))
    assert repo.get_graph("g1").get_edge("e1").state == EdgeState.EXAMINED
    # More records never tip the edge to a verdict — it stays EXAMINED; the ledger grows.
    for _ in range(3):
        repo.add_evidence("g1", _evidence(EvidenceDirection.SUPPORTS))
    assert repo.get_graph("g1").get_edge("e1").state == EdgeState.EXAMINED
    assert len(repo.evidence_for_edge("g1", "e1")) == 5


def test_concurrent_reads_and_writes_do_not_raise(tmp_path):
    """The shared connection is reentrant-lock-guarded, so threadpool-style
    concurrent reads (get/list/events) and writes (save/append) never collide."""
    repo = SqliteHypothesisRepository(tmp_path / "h.db")
    repo.save_graph(_graph_with_one_edge("seed"))
    errors: list[Exception] = []
    barrier = threading.Barrier(8)

    def writer(n: int):
        try:
            barrier.wait()
            for i in range(25):
                repo.save_graph(_graph_with_one_edge(f"g{n}-{i}"))
                repo.append_event(
                    HypothesisEvent(ts="t", op="build", status="ok", graph_id=f"g{n}-{i}")
                )
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    def reader():
        try:
            barrier.wait()
            for _ in range(25):
                repo.list_graphs()
                repo.get_graph("seed")
                repo.failed_events()
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(4)]
    threads += [threading.Thread(target=reader) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    repo.close()
    assert not errors, f"concurrent access raised: {errors[:3]}"
    repo.close()
