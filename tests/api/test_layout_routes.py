"""PUT /layout persists positions and is cosmetic — it must not emit a claim event
or change any edge's validation_status."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import quration.api.hypothesis_routes as hr
from quration.hypothesis.observability import set_event_sink
from quration.hypothesis.orchestrator.demo import build_demo_loop
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
    try:
        yield TestClient(app, raise_server_exceptions=False), repo
    finally:
        set_event_sink(None)
        repo.close()


def _build(tc):
    skeleton = {"rationale": "r",
                "nodes": [{"id": "a", "type": "target", "label": "A"},
                          {"id": "b", "type": "pathway", "label": "B"}],
                "edges": [{"id": "e1", "source_id": "a", "target_id": "b",
                           "relation": "activates"}]}
    res = tc.post("/hypothesis/build", json={"query": "q", "skeleton": skeleton})
    assert res.status_code == 200, res.text
    return res.json()["graph_id"]


def test_layout_persists_positions(client):
    tc, _repo = client
    gid = _build(tc)
    res = tc.put(f"/hypothesis/{gid}/layout",
                 json={"positions": {"a": {"x": 12.0, "y": 34.0}}})
    assert res.status_code == 200, res.text
    got = tc.get(f"/hypothesis/{gid}").json()
    a = next(n for n in got["nodes"] if n["id"] == "a")
    assert a["position"] == {"x": 12.0, "y": 34.0}


def test_layout_does_not_touch_validation_or_emit_claim_event(client):
    tc, repo = client
    gid = _build(tc)
    before = repo.get_graph(gid).get_edge("e1").validation_status
    n_events_before = len(repo.events_for_graph(gid))
    tc.put(f"/hypothesis/{gid}/layout", json={"positions": {"a": {"x": 1.0, "y": 2.0}}})
    after = repo.get_graph(gid).get_edge("e1").validation_status
    assert after == before  # cosmetic move never changes the claim
    assert len(repo.events_for_graph(gid)) == n_events_before  # no claim event


def test_layout_unknown_graph_404(client):
    tc, _repo = client
    res = tc.put("/hypothesis/nope/layout", json={"positions": {}})
    assert res.status_code == 404
