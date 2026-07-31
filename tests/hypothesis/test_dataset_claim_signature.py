"""Dataset evidence is tied to a claim signature: a claim-changing edit must not
let stale evidence re-promote the edited edge. Run against BOTH repositories so the
in-memory and SQLite implementations are proven identical."""

import pytest

from quration.hypothesis.epistemics import EdgeValidationStatus as S
from quration.hypothesis.evidence import EvidenceDirection, EvidenceEntry, EvidenceKind
from quration.hypothesis.graph import CausalGraph, Edge, EdgeState, Node, NodeType
from quration.hypothesis.orchestrator.demo import build_demo_loop
from quration.hypothesis.orchestrator.edge_chat import (
    FlipEdge,
    MergeNodes,
    SetRelation,
    SplitNode,
)
from quration.hypothesis.provenance import PipelineRunProvenance
from quration.hypothesis.repository import InMemoryHypothesisRepository
from quration.hypothesis.store import SqliteHypothesisRepository


@pytest.fixture(params=["inmemory", "sqlite"])
def repo(request, tmp_path):
    r = (InMemoryHypothesisRepository() if request.param == "inmemory"
         else SqliteHypothesisRepository(str(tmp_path / "h.db")))
    yield r
    if hasattr(r, "close"):
        r.close()


def _ev(edge_id="e1", direction=EvidenceDirection.SUPPORTS):
    return EvidenceEntry(
        kind=EvidenceKind.MEASUREMENT,
        edge_id=edge_id, direction=direction,
        provenance=PipelineRunProvenance(run_id="r", data_accession="GSE1"))


def _setup(repo, *, nodes=("a", "b"), edges=(("e1", "a", "b", "activates"),)):
    loop = build_demo_loop(repository=repo)
    g = CausalGraph(id="g", query="q")
    for n in nodes:
        g.add_node(Node(id=n, type=NodeType.TARGET, label=n.upper()))
    for eid, s, t, rel in edges:
        g.add_edge(Edge(id=eid, source_id=s, target_id=t, relation=rel))
    repo.save_graph(g)
    return loop


def test_set_relation_orphans_evidence_and_keeps_ledger(repo):
    loop = _setup(repo)
    repo.add_evidence("g", _ev())
    assert repo.get_graph("g").get_edge("e1").state == EdgeState.EXAMINED

    loop.apply_edge_edit("g", SetRelation(edge_id="e1", relation="inhibits"))

    e = repo.get_graph("g").get_edge("e1")
    assert e.relation == "inhibits"
    assert e.state == EdgeState.UNTESTED               # not re-promoted
    assert len(repo.evidence_for_edge("g", "e1")) == 1         # old evidence still in the ledger


def test_flip_edge_invalidates_dataset_support(repo):
    loop = _setup(repo)
    repo.add_evidence("g", _ev())
    loop.apply_edge_edit("g", FlipEdge(edge_id="e1"))
    assert repo.get_graph("g").get_edge("e1").state == EdgeState.UNTESTED


def test_split_node_invalidates_only_moved_edges(repo):
    loop = _setup(repo, nodes=("a", "b", "c"), edges=(
        ("e1", "a", "b", "activates"),   # incident to a (source) — will be moved
        ("e2", "c", "a", "activates"),   # incident to a (target) — NOT moved
    ))
    repo.add_evidence("g", _ev("e1"))
    repo.add_evidence("g", _ev("e2"))
    loop.apply_edge_edit("g", SplitNode(
        node_id="a", new_label="A2", new_type=NodeType.TARGET, move_edge_ids=["e1"]))
    g = repo.get_graph("g")
    assert g.get_edge("e1").state == EdgeState.UNTESTED       # moved → invalidated
    assert g.get_edge("e2").state == EdgeState.EXAMINED  # untouched


def test_merge_nodes_invalidates_affected_edge(repo):
    loop = _setup(repo, nodes=("a", "b", "c"))
    repo.add_evidence("g", _ev("e1"))
    loop.apply_edge_edit("g", MergeNodes(node_id="b", into_node_id="c"))  # e1: a->b => a->c
    e = repo.get_graph("g").get_edge("e1")
    assert e.target_id == "c"
    assert e.state == EdgeState.UNTESTED


def test_new_evidence_after_edit_applies_to_the_new_claim(repo):
    loop = _setup(repo)
    repo.add_evidence("g", _ev())
    loop.apply_edge_edit("g", SetRelation(edge_id="e1", relation="inhibits"))
    assert repo.get_graph("g").get_edge("e1").state == EdgeState.UNTESTED
    repo.add_evidence("g", _ev())  # gathered against the edited claim
    assert repo.get_graph("g").get_edge("e1").state == EdgeState.EXAMINED


def test_new_evidence_after_edit_records_against_the_new_claim(repo):
    loop = _setup(repo)
    repo.add_evidence("g", _ev())
    loop.apply_edge_edit("g", SetRelation(edge_id="e1", relation="inhibits"))
    repo.add_evidence("g", _ev(direction=EvidenceDirection.REFUTES))
    # The refuting record applies to the edited claim — the edge is EXAMINED and the
    # inconsistent observation is a fact in the ledger (there is no CONTRADICTED verdict).
    e = repo.get_graph("g").get_edge("e1")
    assert e.state == EdgeState.EXAMINED
    refuting = [ev for ev in repo.evidence_for_edge("g", "e1")
                if ev.direction == EvidenceDirection.REFUTES]
    assert len(refuting) == 1


# --- Legacy (pre-upgrade) unsigned evidence: claim_signature is None ----------
# Real legacy rows predate claim signatures. They must still count for an UNEDITED
# graph (so old graphs keep working), but once a claim-changing edit drops a
# superseding barrier on the edge, an unsigned row can't be assumed to apply to the
# edited claim — so it must stop counting until new signed evidence arrives.

def _insert_legacy(repo, graph_id, entry):
    """Insert a pre-upgrade evidence row (claim_signature null), bypassing the
    signature-stamping that `add_evidence` does, then recompute via save_graph."""
    if isinstance(repo, InMemoryHypothesisRepository):
        repo._evidence.setdefault((graph_id, entry.edge_id), []).append(entry)
    else:  # sqlite — write the row directly with a null signature
        repo._conn.execute(
            "INSERT INTO evidence (graph_id, edge_id, created_at, entry_json) "
            "VALUES (?, ?, ?, ?)",
            (graph_id, entry.edge_id, "2026-01-01T00:00:00+00:00",
             entry.model_dump_json()),
        )
        repo._conn.commit()
    repo.save_graph(repo.get_graph(graph_id))  # trigger the rollup


def test_legacy_unsigned_evidence_applies_to_unedited_graph(repo):
    _setup(repo)
    _insert_legacy(repo, "g", _ev())  # claim_signature defaults to None
    assert repo.get_graph("g").get_edge("e1").state == EdgeState.EXAMINED


def test_legacy_unsigned_evidence_not_repromoted_after_set_relation(repo):
    loop = _setup(repo)
    _insert_legacy(repo, "g", _ev())
    assert repo.get_graph("g").get_edge("e1").state == EdgeState.EXAMINED

    loop.apply_edge_edit("g", SetRelation(edge_id="e1", relation="inhibits"))

    e = repo.get_graph("g").get_edge("e1")
    assert e.state == EdgeState.UNTESTED            # not re-promoted
    assert len(repo.evidence_for_edge("g", "e1")) == 1      # ledger preserved


def test_legacy_unsigned_evidence_not_repromoted_after_flip(repo):
    loop = _setup(repo)
    _insert_legacy(repo, "g", _ev())
    loop.apply_edge_edit("g", FlipEdge(edge_id="e1"))
    assert repo.get_graph("g").get_edge("e1").state == EdgeState.UNTESTED


def test_new_signed_evidence_after_edit_applies_despite_stale_legacy(repo):
    loop = _setup(repo)
    _insert_legacy(repo, "g", _ev())
    loop.apply_edge_edit("g", SetRelation(edge_id="e1", relation="inhibits"))
    assert repo.get_graph("g").get_edge("e1").state == EdgeState.UNTESTED
    repo.add_evidence("g", _ev())  # gathered against the edited claim → signed
    assert repo.get_graph("g").get_edge("e1").state == EdgeState.EXAMINED


def test_relevant_evidence_excludes_legacy_only_after_barrier():
    """Unit-level regression for the filter itself (no repo)."""
    from quration.hypothesis.epistemics import EdgeValidation, ProposalSource
    from quration.hypothesis.evidence import relevant_evidence

    edge = Edge(id="e1", source_id="a", target_id="b", relation="inhibits")
    legacy = _ev()  # claim_signature None
    assert relevant_evidence(edge, [legacy]) == [legacy]  # no barrier → counts

    edge.validations.append(EdgeValidation(
        status=S.UNVALIDATED, source=ProposalSource.SYSTEM,
        rationale="relation changed", created_at="t", supersedes_prior=True))
    assert relevant_evidence(edge, [legacy]) == []  # barrier → excluded
