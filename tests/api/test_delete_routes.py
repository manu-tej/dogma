"""HTTP routes for deleting saved graphs (single + clear-all)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from quration.api.hypothesis_routes import get_repo, router
from quration.hypothesis.graph import CausalGraph, Node, NodeType
from quration.hypothesis.store.sqlite_repository import SqliteHypothesisRepository


def _g(gid: str) -> CausalGraph:
    return CausalGraph(
        id=gid, query=f"q-{gid}",
        nodes=[Node(id="n", type=NodeType.TARGET, label="EGFR")], edges=[],
    )


@pytest.fixture
def client_and_repo():
    app = FastAPI()
    app.include_router(router)
    repo = SqliteHypothesisRepository(":memory:")  # isolated, not the real ./data store
    app.dependency_overrides[get_repo] = lambda: repo
    return TestClient(app), repo


def test_delete_one_graph_leaves_the_rest(client_and_repo):
    client, repo = client_and_repo
    repo.save_graph(_g("a"))
    repo.save_graph(_g("b"))
    resp = client.delete("/hypothesis/a")
    assert resp.status_code == 200, resp.text
    assert resp.json()["deleted"] is True
    assert {s["id"] for s in client.get("/hypothesis").json()} == {"b"}


def test_delete_unknown_graph_is_404(client_and_repo):
    client, _ = client_and_repo
    resp = client.delete("/hypothesis/nope")
    assert resp.status_code == 404
    assert "unknown graph" in resp.json()["detail"]


def test_clear_all_history_empties_the_list(client_and_repo):
    client, repo = client_and_repo
    repo.save_graph(_g("a"))
    repo.save_graph(_g("b"))
    resp = client.delete("/hypothesis")
    assert resp.status_code == 200, resp.text
    assert resp.json()["deleted"] == 2
    assert client.get("/hypothesis").json() == []
