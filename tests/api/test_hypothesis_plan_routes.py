"""Tests for /plan and /resolve hypothesis API routes.

Uses the local fixture pattern from tests/api/test_hypothesis_routes.py:
mount the router on a bare FastAPI app, override get_loop with build_demo_loop(),
and override get_plan_service / get_dataset_search_service with demo twins so
tests are fully offline with no API key required.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from quration.api.hypothesis_routes import (
    get_dataset_search_service,
    get_loop,
    get_plan_service,
    router,
)
from quration.hypothesis.orchestrator.dataset_search import DemoDatasetSearchService
from quration.hypothesis.orchestrator.demo import build_demo_loop
from quration.hypothesis.orchestrator.evaluation_plan_service import EvaluationPlanService
from quration.hypothesis.orchestrator.readout_resolver import DemoReadoutResolver


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    loop = build_demo_loop()
    app.dependency_overrides[get_loop] = lambda: loop
    # Force demo service singletons so module-global singletons don't leak across tests.
    app.dependency_overrides[get_plan_service] = lambda: EvaluationPlanService(
        resolver=DemoReadoutResolver(),
        grounding_provider=None,
    )
    app.dependency_overrides[get_dataset_search_service] = lambda: DemoDatasetSearchService()
    return TestClient(app)


def _seed_graph(client: TestClient) -> str:
    """POST /start and return the graph_id."""
    resp = client.post("/hypothesis/start", json={"query": "does EGFR drive resistance?"})
    assert resp.status_code == 200
    return resp.json()["graph_id"]


# ---------------------------------------------------------------------------
# /plan route
# ---------------------------------------------------------------------------

def test_plan_route_returns_200_with_edge_id(client):
    graph_id = _seed_graph(client)
    resp = client.get(f"/hypothesis/{graph_id}/edges/e-egfr-kras/plan")
    assert resp.status_code == 200
    body = resp.json()
    assert body["edge_id"] == "e-egfr-kras"


def test_plan_route_ideal_readout_has_modality(client):
    graph_id = _seed_graph(client)
    resp = client.get(f"/hypothesis/{graph_id}/edges/e-egfr-kras/plan")
    assert resp.status_code == 200
    body = resp.json()
    assert "ideal_readout" in body
    assert "modality" in body["ideal_readout"]
    assert body["ideal_readout"]["modality"] is not None


def test_plan_route_unknown_graph_is_404(client):
    resp = client.get("/hypothesis/no-such-graph/edges/e-egfr-kras/plan")
    assert resp.status_code == 404


def test_plan_route_unknown_edge_is_404(client):
    graph_id = _seed_graph(client)
    resp = client.get(f"/hypothesis/{graph_id}/edges/no-such-edge/plan")
    assert resp.status_code == 404


def test_plan_route_second_edge_also_works(client):
    graph_id = _seed_graph(client)
    resp = client.get(f"/hypothesis/{graph_id}/edges/e-kras-resist/plan")
    assert resp.status_code == 200
    assert resp.json()["edge_id"] == "e-kras-resist"


# ---------------------------------------------------------------------------
# /resolve route
# ---------------------------------------------------------------------------

_VALID_DIRECTNESS = {"direct", "proxy_modality", "proxy_correlation", "wrong_assay", "not_evaluable", None}


def test_resolve_route_returns_200(client):
    graph_id = _seed_graph(client)
    resp = client.post(f"/hypothesis/{graph_id}/edges/e-egfr-kras/resolve")
    assert resp.status_code == 200


def test_resolve_route_directness_is_valid(client):
    graph_id = _seed_graph(client)
    resp = client.post(f"/hypothesis/{graph_id}/edges/e-egfr-kras/resolve")
    assert resp.status_code == 200
    body = resp.json()
    assert body["directness"] in _VALID_DIRECTNESS


def test_resolve_route_edge_id_matches(client):
    graph_id = _seed_graph(client)
    resp = client.post(f"/hypothesis/{graph_id}/edges/e-egfr-kras/resolve")
    assert resp.status_code == 200
    assert resp.json()["edge_id"] == "e-egfr-kras"


def test_resolve_route_does_not_flip_edge_state(client):
    graph_id = _seed_graph(client)
    client.post(f"/hypothesis/{graph_id}/edges/e-egfr-kras/resolve")
    graph_resp = client.get(f"/hypothesis/{graph_id}")
    assert graph_resp.status_code == 200
    edge = next(e for e in graph_resp.json()["edges"] if e["id"] == "e-egfr-kras")
    # resolve persists an EvidenceRecord fact but must NOT flip state to "examined"
    # edge state MUST stay untested (ledger invariant in slice 1)
    assert edge["state"] == "untested"


def test_resolve_route_unknown_graph_is_404(client):
    resp = client.post("/hypothesis/no-such-graph/edges/e-egfr-kras/resolve")
    assert resp.status_code == 404


def test_resolve_route_unknown_edge_is_404(client):
    graph_id = _seed_graph(client)
    resp = client.post(f"/hypothesis/{graph_id}/edges/no-such-edge/resolve")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Router introspection
# ---------------------------------------------------------------------------

def test_router_exposes_plan_and_resolve_paths():
    paths = {r.path for r in router.routes}
    assert "/hypothesis/{graph_id}/edges/{edge_id}/plan" in paths
    assert "/hypothesis/{graph_id}/edges/{edge_id}/resolve" in paths
