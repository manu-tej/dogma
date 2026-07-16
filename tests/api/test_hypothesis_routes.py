"""TestClient tests for the hypothesis-engine API (mounted on a bare app)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from quration.api.hypothesis_routes import get_loop, router
from quration.hypothesis.orchestrator.demo import build_demo_loop


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    loop = build_demo_loop()
    app.dependency_overrides[get_loop] = lambda: loop
    return TestClient(app)


def test_start_returns_investigative_with_graph_id(client):
    resp = client.post("/hypothesis/start", json={"query": "does EGFR drive resistance?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "investigative"
    assert body["graph_id"]


def test_get_graph_returns_nodes_and_edges(client):
    graph_id = client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    resp = client.get(f"/hypothesis/{graph_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert {n["id"] for n in body["nodes"]} == {"P00533", "P01116", "RESIST"}
    assert {e["id"] for e in body["edges"]} == {"e-egfr-kras", "e-kras-resist"}


def test_get_graph_unknown_is_404(client):
    resp = client.get("/hypothesis/nope")
    assert resp.status_code == 404
    assert "unknown graph" in resp.json()["detail"]


def test_next_returns_a_proposal_without_running(client):
    graph_id = client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    resp = client.get(f"/hypothesis/{graph_id}/next")
    assert resp.status_code == 200
    proposed = resp.json()["proposed"]
    assert proposed["edge_id"] in {"e-egfr-kras", "e-kras-resist"}
    assert proposed["pipeline"] == "nf-core/rnaseq"
    # nothing ran: edge still untested
    graph = client.get(f"/hypothesis/{graph_id}").json()
    assert all(e["state"] == "untested" for e in graph["edges"])


def test_next_unknown_graph_is_404(client):
    resp = client.get("/hypothesis/nope/next")
    assert resp.status_code == 404


def test_approve_records_evidence_on_edge(client):
    graph_id = client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    proposed = client.get(f"/hypothesis/{graph_id}/next").json()["proposed"]

    resp = client.post(f"/hypothesis/{graph_id}/approve", json={"proposed": proposed})
    assert resp.status_code == 200
    entry = resp.json()
    assert entry["edge_id"] == proposed["edge_id"]
    assert entry["direction"] == "supports"

    graph = client.get(f"/hypothesis/{graph_id}").json()
    examined = next(e for e in graph["edges"] if e["id"] == proposed["edge_id"])
    assert examined["state"] == "examined"  # has a ledger record, not a verdict
    assert examined["confidence"] == 0.0


def test_approve_unknown_graph_is_404(client):
    proposed = {"edge_id": "e-egfr-kras", "gap": "x", "pipeline": "p", "data_accession": "d"}
    resp = client.post("/hypothesis/nope/approve", json={"proposed": proposed})
    assert resp.status_code == 404


def test_router_exposes_expected_paths():
    paths = {r.path for r in router.routes}
    assert "/hypothesis/start" in paths
    assert "/hypothesis/{graph_id}" in paths
    assert "/hypothesis/{graph_id}/next" in paths
    assert "/hypothesis/{graph_id}/approve" in paths
    assert "/hypothesis/seed" in paths
    assert "/hypothesis/build" in paths
    assert "/hypothesis/{graph_id}/edges/{edge_id}/chat" in paths
    assert "/hypothesis/{graph_id}/apply-edit" in paths


from quration.hypothesis.orchestrator.seeding import DemoSeedingService


@pytest.fixture
def seeding_client():
    from quration.api.hypothesis_routes import get_loop, get_seeding_service, router
    app = FastAPI()
    app.include_router(router)
    loop = build_demo_loop()
    app.dependency_overrides[get_loop] = lambda: loop
    app.dependency_overrides[get_seeding_service] = lambda: DemoSeedingService()
    return TestClient(app)


def test_seed_returns_questions_then_skeleton(seeding_client):
    q = seeding_client.post("/hypothesis/seed",
                            json={"query": "does EGFR drive resistance?", "answers": []})
    assert q.status_code == 200
    assert q.json()["kind"] == "questions"

    s = seeding_client.post("/hypothesis/seed", json={
        "query": "does EGFR drive resistance?",
        "answers": [{"question_id": "context", "value": "lung"}],
    })
    assert s.json()["kind"] == "seeds"
    assert s.json()["skeleton"]["nodes"]


def test_build_persists_skeleton_and_get_returns_it(seeding_client):
    skeleton = seeding_client.post("/hypothesis/seed", json={
        "query": "q", "answers": [{"question_id": "context", "value": "lung"}],
    }).json()["skeleton"]

    built = seeding_client.post("/hypothesis/build",
                                json={"query": "q", "skeleton": skeleton})
    assert built.status_code == 200
    gid = built.json()["graph_id"]
    graph = seeding_client.get(f"/hypothesis/{gid}").json()
    assert {n["label"] for n in graph["nodes"]} >= {"EGFR", "KRAS", "drug resistance"}


from quration.hypothesis.orchestrator.edge_chat import DemoEdgeChatService


@pytest.fixture
def chat_client():
    from quration.api.hypothesis_routes import get_edge_chat_service, get_loop, router
    app = FastAPI()
    app.include_router(router)
    loop = build_demo_loop()
    app.dependency_overrides[get_loop] = lambda: loop
    app.dependency_overrides[get_edge_chat_service] = lambda: DemoEdgeChatService()
    return TestClient(app), loop


def test_edge_chat_returns_turn(chat_client):
    client, loop = chat_client
    gid = client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    edge_id = client.get(f"/hypothesis/{gid}").json()["edges"][0]["id"]
    resp = client.post(f"/hypothesis/{gid}/edges/{edge_id}/chat",
                       json={"history": [], "message": "can you flip this?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["reply"]
    assert body["proposed_edit"]["op"] == "flip_edge"


def test_apply_edit_mutates_graph(chat_client):
    client, loop = chat_client
    gid = client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    edge_id = client.get(f"/hypothesis/{gid}").json()["edges"][0]["id"]
    resp = client.post(f"/hypothesis/{gid}/apply-edit",
                       json={"edit": {"op": "set_relation", "edge_id": edge_id, "relation": "modulates"}})
    assert resp.status_code == 200
    assert any(e["relation"] == "modulates" for e in resp.json()["edges"])


def test_apply_edit_unknown_graph_404(chat_client):
    client, _ = chat_client
    resp = client.post("/hypothesis/nope/apply-edit",
                       json={"edit": {"op": "flip_edge", "edge_id": "x"}})
    assert resp.status_code == 404


def test_apply_edit_unknown_edge_422(chat_client):
    client, _ = chat_client
    gid = client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    resp = client.post(f"/hypothesis/{gid}/apply-edit",
                       json={"edit": {"op": "flip_edge", "edge_id": "ghost-edge"}})
    assert resp.status_code == 422


def test_edge_chat_unknown_edge_404(chat_client):
    client, _ = chat_client
    gid = client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    resp = client.post(f"/hypothesis/{gid}/edges/ghost/chat",
                       json={"history": [], "message": "hi"})
    assert resp.status_code == 404


from quration.hypothesis.orchestrator.edge_chat import DemoNodeChatService


@pytest.fixture
def node_chat_client():
    from quration.api.hypothesis_routes import get_loop, get_node_chat_service, router
    app = FastAPI()
    app.include_router(router)
    loop = build_demo_loop()
    app.dependency_overrides[get_loop] = lambda: loop
    app.dependency_overrides[get_node_chat_service] = lambda: DemoNodeChatService()
    return TestClient(app)


def test_node_chat_returns_turn(node_chat_client):
    gid = node_chat_client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    node_id = node_chat_client.get(f"/hypothesis/{gid}").json()["nodes"][0]["id"]
    resp = node_chat_client.post(f"/hypothesis/{gid}/nodes/{node_id}/chat",
                                 json={"history": [], "message": "please rename this node"})
    assert resp.status_code == 200
    assert resp.json()["reply"]
    assert resp.json()["proposed_edit"]["op"] == "set_label"


def test_node_chat_unknown_node_404(node_chat_client):
    gid = node_chat_client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    resp = node_chat_client.post(f"/hypothesis/{gid}/nodes/ghost/chat",
                                 json={"history": [], "message": "hi"})
    assert resp.status_code == 404


def test_router_exposes_node_chat_path():
    from quration.api.hypothesis_routes import router
    paths = {r.path for r in router.routes}
    assert "/hypothesis/{graph_id}/nodes/{node_id}/chat" in paths


# --- Real-LLM-brain DI wiring -------------------------------------------------

from types import SimpleNamespace

import quration.api.hypothesis_routes as hr
from quration.hypothesis.orchestrator.edge_chat import (
    DemoEdgeChatService,
    DemoNodeChatService as _DemoNodeChat,
    LlmEdgeChatService,
    LlmNodeChatService,
)
from quration.hypothesis.orchestrator.seeding import DemoSeedingService, LlmSeedingService


@pytest.fixture
def reset_chat_singletons():
    hr._seeding = hr._edge_chat = hr._node_chat = hr._grounding = hr._dataset_search = hr._kg = None
    hr._repo = hr._loop = None
    yield
    hr._seeding = hr._edge_chat = hr._node_chat = hr._grounding = hr._dataset_search = hr._kg = None
    hr._repo = hr._loop = None


def test_di_falls_back_to_demo_when_no_real_provider(monkeypatch, reset_chat_singletons):
    monkeypatch.setattr(hr, "_resolve_chat_llm", lambda: None)
    assert isinstance(hr.get_seeding_service(), DemoSeedingService)
    assert isinstance(hr.get_edge_chat_service(), DemoEdgeChatService)
    assert isinstance(hr.get_node_chat_service(), _DemoNodeChat)


def test_di_uses_llm_services_when_provider_resolves(monkeypatch, reset_chat_singletons):
    sentinel = object()
    monkeypatch.setattr(hr, "_resolve_chat_llm", lambda: (sentinel, "sonnet"))
    seeding = hr.get_seeding_service()
    edge = hr.get_edge_chat_service()
    node = hr.get_node_chat_service()
    assert isinstance(seeding, LlmSeedingService)
    assert isinstance(edge, LlmEdgeChatService)
    assert isinstance(node, LlmNodeChatService)
    # the resolved provider + model are threaded into the service
    assert edge._provider is sentinel and edge._model == "sonnet"


def test_resolve_chat_llm_none_for_demo_sentinel(monkeypatch):
    monkeypatch.setattr(hr, "get_config", lambda: SimpleNamespace(llm=SimpleNamespace(provider="demo")))
    assert hr._resolve_chat_llm() is None


def test_resolve_chat_llm_none_when_provider_unconstructible(monkeypatch):
    monkeypatch.setattr(
        hr, "get_config", lambda: SimpleNamespace(llm=SimpleNamespace(provider="anthropic")))

    def _boom(*a, **k):
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    monkeypatch.setattr(hr, "get_provider_from_config", _boom)
    assert hr._resolve_chat_llm() is None


def test_resolve_chat_llm_returns_provider_and_smart_model(monkeypatch):
    provider = object()
    monkeypatch.setattr(
        hr, "get_config", lambda: SimpleNamespace(llm=SimpleNamespace(provider="claude_subscription")))
    monkeypatch.setattr(hr, "get_provider_from_config", lambda: provider)
    monkeypatch.setattr(hr, "get_model_for_config", lambda tier="smart": "sonnet")
    resolved = hr._resolve_chat_llm()
    assert resolved == (provider, "sonnet")


# --- On-demand node grounding -------------------------------------------------

from quration.hypothesis.orchestrator.grounding import DemoGroundingService


@pytest.fixture
def grounding_client():
    from quration.api.hypothesis_routes import get_grounding_service, get_loop, router
    app = FastAPI()
    app.include_router(router)
    loop = build_demo_loop()
    app.dependency_overrides[get_loop] = lambda: loop
    app.dependency_overrides[get_grounding_service] = lambda: DemoGroundingService()
    return TestClient(app)


def test_ground_node_returns_proposal(grounding_client):
    gid = grounding_client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    # demo graph's first node is EGFR (P00533), which DemoGroundingService knows.
    resp = grounding_client.post(f"/hypothesis/{gid}/nodes/P00533/ground")
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["proposed_edit"]["op"] == "set_grounding"
    assert body["proposed_edit"]["term_id"] == "P00533"


def test_ground_unknown_node_404(grounding_client):
    gid = grounding_client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    resp = grounding_client.post(f"/hypothesis/{gid}/nodes/ghost/ground")
    assert resp.status_code == 404


def test_ground_unknown_graph_404(grounding_client):
    resp = grounding_client.post("/hypothesis/nope/nodes/P00533/ground")
    assert resp.status_code == 404


def test_router_exposes_ground_path():
    paths = {r.path for r in hr.router.routes}
    assert "/hypothesis/{graph_id}/nodes/{node_id}/ground" in paths


def test_grounding_di_real_vs_demo(monkeypatch, reset_chat_singletons):
    from quration.hypothesis.orchestrator.grounding import OntologyGroundingService
    monkeypatch.setattr(hr, "_real_mode", lambda: False)
    assert isinstance(hr.get_grounding_service(), DemoGroundingService)
    hr._grounding = None  # force a rebuild under the flipped mode
    monkeypatch.setattr(hr, "_real_mode", lambda: True)
    monkeypatch.delenv("QURATION_GROUNDING", raising=False)
    assert isinstance(hr.get_grounding_service(), OntologyGroundingService)


def test_grounding_di_optimuskg_branch(monkeypatch, reset_chat_singletons):
    from quration.hypothesis.orchestrator.grounding import (
        FallbackGroundingService,
        OntologyGroundingService,
    )
    from quration.hypothesis.orchestrator.optimuskg_grounding import OptimusKGGroundingService
    monkeypatch.setattr(hr, "_real_mode", lambda: True)
    monkeypatch.setenv("QURATION_GROUNDING", "optimuskg")
    # optimuskg mode chains the local KG with a public-ontology fallback:
    # OptimusKG first, OLS/UniProt second. Construction is cheap (no network,
    # optimuskg import is lazy in the loader).
    svc = hr.get_grounding_service()
    assert isinstance(svc, FallbackGroundingService)
    assert isinstance(svc._services[0], OptimusKGGroundingService)
    assert isinstance(svc._services[1], OntologyGroundingService)


# --- Per-edge dataset discovery ----------------------------------------------

from quration.hypothesis.orchestrator.dataset_search import DemoDatasetSearchService


@pytest.fixture
def find_data_client():
    from quration.api.hypothesis_routes import get_dataset_search_service, get_loop, router
    app = FastAPI()
    app.include_router(router)
    loop = build_demo_loop()
    app.dependency_overrides[get_loop] = lambda: loop
    app.dependency_overrides[get_dataset_search_service] = lambda: DemoDatasetSearchService()
    return TestClient(app)


def test_find_data_returns_candidates(find_data_client):
    gid = find_data_client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    edge_id = find_data_client.get(f"/hypothesis/{gid}").json()["edges"][0]["id"]
    resp = find_data_client.post(f"/hypothesis/{gid}/edges/{edge_id}/find-data")
    assert resp.status_code == 200
    cands = resp.json()["candidates"]
    assert len(cands) == 1
    assert {c["source"] for c in cands} == {"geo"}
    assert cands[0]["accession"] == "GSE-DEMO"
    assert any("synthetic demo" in reason for reason in cands[0]["match_reasons"])
    assert all(c["suggested_pipeline"] for c in cands)


def test_find_data_unknown_edge_404(find_data_client):
    gid = find_data_client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    resp = find_data_client.post(f"/hypothesis/{gid}/edges/ghost/find-data")
    assert resp.status_code == 404


def test_find_data_unknown_graph_404(find_data_client):
    resp = find_data_client.post("/hypothesis/nope/edges/e/find-data")
    assert resp.status_code == 404


def test_router_exposes_find_data_path():
    paths = {r.path for r in hr.router.routes}
    assert "/hypothesis/{graph_id}/edges/{edge_id}/find-data" in paths


def test_dataset_search_di_real_vs_demo(monkeypatch, reset_chat_singletons):
    from quration.hypothesis.orchestrator.dataset_search import RealDatasetSearchService
    monkeypatch.setattr(hr, "_real_mode", lambda: False)
    assert isinstance(hr.get_dataset_search_service(), DemoDatasetSearchService)
    hr._dataset_search = None  # force a rebuild under the flipped mode
    monkeypatch.setattr(hr, "_real_mode", lambda: True)
    assert isinstance(hr.get_dataset_search_service(), RealDatasetSearchService)


def test_unimplemented_provider_does_not_silently_enter_demo_mode(monkeypatch):
    monkeypatch.setattr(
        hr,
        "get_config",
        lambda: SimpleNamespace(llm=SimpleNamespace(provider="aws_bedrock")),
    )
    with pytest.raises(RuntimeError, match="not implemented"):
        hr._real_mode()


# --- OptimusKG edge knowledge + expansion (demo-backed in tests) ---------------

from quration.hypothesis.orchestrator.kg_knowledge import DemoKGService


@pytest.fixture
def kg_client():
    from quration.api.hypothesis_routes import get_kg_service, get_loop, router
    app = FastAPI()
    app.include_router(router)
    loop = build_demo_loop()
    app.dependency_overrides[get_loop] = lambda: loop
    app.dependency_overrides[get_kg_service] = lambda: DemoKGService()
    return TestClient(app)


def test_edge_known_returns_knowledge(kg_client):
    gid = kg_client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    eid = kg_client.get(f"/hypothesis/{gid}").json()["edges"][0]["id"]
    resp = kg_client.post(f"/hypothesis/{gid}/edges/{eid}/known", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True and body["sources"]


def test_edge_known_unknown_edge_404(kg_client):
    gid = kg_client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    assert kg_client.post(f"/hypothesis/{gid}/edges/ghost/known", json={}).status_code == 404


def test_expand_node_returns_neighbors(kg_client):
    gid = kg_client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    nid = kg_client.get(f"/hypothesis/{gid}").json()["nodes"][0]["id"]
    resp = kg_client.post(f"/hypothesis/{gid}/nodes/{nid}/expand", json={})
    assert resp.status_code == 200
    assert resp.json()["neighbors"][0]["symbol"] == "GRB2"


def test_expand_unknown_node_404(kg_client):
    gid = kg_client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    assert kg_client.post(f"/hypothesis/{gid}/nodes/ghost/expand", json={}).status_code == 404


def test_kg_routes_registered():
    from quration.api.hypothesis_routes import router
    paths = {r.path for r in router.routes}
    assert "/hypothesis/{graph_id}/edges/{edge_id}/known" in paths
    assert "/hypothesis/{graph_id}/nodes/{node_id}/expand" in paths


def test_kg_di_optimuskg_branch(monkeypatch, reset_chat_singletons):
    from quration.hypothesis.orchestrator.optimuskg_kg import OptimusKGKnowledgeService
    monkeypatch.setattr(hr, "_real_mode", lambda: True)
    monkeypatch.setenv("QURATION_GROUNDING", "optimuskg")
    assert isinstance(hr.get_kg_service(), OptimusKGKnowledgeService)


def test_kg_di_demo_default(monkeypatch, reset_chat_singletons):
    monkeypatch.setattr(hr, "_real_mode", lambda: True)
    monkeypatch.delenv("QURATION_GROUNDING", raising=False)
    assert isinstance(hr.get_kg_service(), DemoKGService)


def test_expand_annotates_existing_node_for_provenance_edge(kg_client):
    # DemoKGService.expand returns GRB2. If the graph already has GRB2, it is NOT
    # hidden — it's annotated with existing_node_id so the UI offers a provenance
    # edge to it (not a duplicate node).
    built = kg_client.post("/hypothesis/build", json={"query": "q", "skeleton": {
        "nodes": [
            {"id": "egfr", "type": "target", "label": "EGFR", "grounding": None},
            {"id": "grb2", "type": "target", "label": "GRB2 (adapter)", "grounding": None},
        ],
        "edges": [], "rationale": "x"}}).json()
    gid = built["graph_id"]
    neighbors = kg_client.post(f"/hypothesis/{gid}/nodes/egfr/expand", json={}).json()["neighbors"]
    grb2 = next(n for n in neighbors if n["symbol"].lower() == "grb2")
    assert grb2["existing_node_id"] == "grb2"  # mapped to the existing node


def test_expand_excludes_the_anchor_itself(kg_client):
    # If the demo neighbor symbol equals the anchor label, it must not be suggested.
    built = kg_client.post("/hypothesis/build", json={"query": "q", "skeleton": {
        "nodes": [{"id": "grb2", "type": "target", "label": "GRB2", "grounding": None}],
        "edges": [], "rationale": "x"}}).json()
    gid = built["graph_id"]
    neighbors = kg_client.post(f"/hypothesis/{gid}/nodes/grb2/expand", json={}).json()["neighbors"]
    assert all(n["symbol"].lower() != "grb2" for n in neighbors)
