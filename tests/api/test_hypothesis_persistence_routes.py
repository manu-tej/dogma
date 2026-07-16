"""History + observability endpoints over the durable SQLite store.

Drives the deterministic Demo seams end to end against a real (tmp-file) SQLite
repository, asserting that graphs persist and that every op leaves an event trail
— including a failed seed that never produced a graph.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import quration.api.hypothesis_routes as hr
from quration.hypothesis.observability import set_event_sink
from quration.hypothesis.orchestrator.demo import build_demo_loop
from quration.hypothesis.orchestrator.seeding import DemoSeedingService
from quration.hypothesis.store import SqliteHypothesisRepository


@pytest.fixture
def client(tmp_path):
    repo = SqliteHypothesisRepository(str(tmp_path / "h.db"))
    loop = build_demo_loop(repository=repo)
    set_event_sink(repo)
    app = FastAPI()
    app.include_router(hr.router)
    app.dependency_overrides[hr.get_loop] = lambda: loop
    app.dependency_overrides[hr.get_repo] = lambda: repo
    app.dependency_overrides[hr.get_seeding_service] = lambda: DemoSeedingService()
    try:
        yield TestClient(app, raise_server_exceptions=False), repo
    finally:
        set_event_sink(None)
        repo.close()


def _seed_and_build(tc) -> str:
    """Run the Demo seeding flow and build a graph; return its id."""
    step = tc.post(
        "/hypothesis/seed",
        json={"query": "egfr resistance", "answers": [{"question_id": "context", "value": "lung"}]},
    ).json()
    assert step["kind"] == "seeds"
    skeleton = step["skeleton"]
    res = tc.post("/hypothesis/build", json={"query": "egfr resistance", "skeleton": skeleton})
    assert res.status_code == 200
    return res.json()["graph_id"]


def test_list_graphs_newest_first_with_counts(client):
    tc, _repo = client
    gid1 = _seed_and_build(tc)
    gid2 = _seed_and_build(tc)

    rows = tc.get("/hypothesis").json()
    ids = [r["id"] for r in rows]
    assert gid1 in ids and gid2 in ids
    assert ids.index(gid2) < ids.index(gid1)  # newest first
    row = next(r for r in rows if r["id"] == gid1)
    assert row["n_nodes"] == 3 and row["n_edges"] == 2  # the demo skeleton
    assert row["status"] == "active"
    assert row["query"] == "egfr resistance"


def test_built_graph_persists_and_is_reloadable(client, tmp_path):
    tc, _repo = client
    gid = _seed_and_build(tc)
    # Fresh repo on the same file simulates a restart: the graph is still there.
    reopened = SqliteHypothesisRepository(str(tmp_path / "h.db"))
    try:
        assert reopened.get_graph(gid) is not None
    finally:
        reopened.close()


def test_build_and_ground_leave_an_event_trail(client):
    tc, _repo = client
    gid = _seed_and_build(tc)
    # Ground a node (demo grounding) — records a 'ground' event.
    node_id = tc.get(f"/hypothesis/{gid}").json()["nodes"][0]["id"]
    tc.post(f"/hypothesis/{gid}/nodes/{node_id}/ground")

    events = tc.get(f"/hypothesis/{gid}/events").json()
    ops = [e["op"] for e in events]
    assert "build" in ops
    assert "ground" in ops
    ground_ev = next(e for e in events if e["op"] == "ground")
    assert ground_ev["status"] in ("ok", "not_found")
    assert ground_ev["latency_ms"] is not None
    assert ground_ev["detail"] is not None


def test_build_autogrounds_molecular_nodes(client, monkeypatch):
    tc, _repo = client
    # Force the fast local backend to the offline Demo grounder (grounds EGFR/KRAS,
    # not arbitrary pathways) so the test is deterministic and network-free.
    from quration.hypothesis.orchestrator.grounding import DemoGroundingService
    monkeypatch.setattr(hr, "get_grounding_service", lambda: DemoGroundingService())

    skeleton = {
        "rationale": "t",
        "nodes": [
            {"id": "egfr", "type": "target", "label": "EGFR"},          # demo-known -> grounds
            {"id": "p", "type": "pathway", "label": "MAPK cascade xyz"}, # not known -> stays ungrounded
        ],
        "edges": [{"id": "e1", "source_id": "egfr", "target_id": "p", "relation": "activates"}],
    }
    res = tc.post("/hypothesis/build", json={"query": "egfr build", "skeleton": skeleton})
    gid = res.json()["graph_id"]
    graph = tc.get(f"/hypothesis/{gid}").json()
    by_id = {n["id"]: n for n in graph["nodes"]}
    assert by_id["egfr"]["grounding"] is not None  # molecular node pre-grounded at build
    assert by_id["egfr"]["grounding"]["term_id"] == "P00533"
    assert by_id["p"]["grounding"] is None          # conceptual node left for on-demand

    ev = next(e for e in tc.get(f"/hypothesis/{gid}/events").json() if e["op"] == "build")
    assert ev["detail"]["n_grounded"] == 1


def test_failed_seed_surfaces_in_failed_events(client):
    tc, repo = client

    class _Boom:
        def next_step(self, query, answers):
            raise RuntimeError("seed model exploded")

    tc.app.dependency_overrides[hr.get_seeding_service] = lambda: _Boom()
    res = tc.post("/hypothesis/seed", json={"query": "doomed query", "answers": []})
    assert res.status_code == 500  # traced_op re-raised the error

    failed = tc.get("/hypothesis/events/failed").json()
    seed_fail = next(e for e in failed if e["op"] == "seed")
    assert seed_fail["status"] == "error"
    assert seed_fail["graph_id"] is None  # no graph existed yet
    assert "exploded" in (seed_fail["error"] or "")
    assert seed_fail["query"] == "doomed query"
