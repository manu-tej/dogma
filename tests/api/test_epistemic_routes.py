"""Edge epistemic state over the API: /known validates, grounding doesn't, and
GET exposes a derived display_status."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import quration.api.hypothesis_routes as hr
from quration.hypothesis.observability import set_event_sink
from quration.hypothesis.orchestrator.demo import build_demo_loop
from quration.hypothesis.orchestrator.kg_knowledge import EdgeKnowledge
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
        yield TestClient(app, raise_server_exceptions=False), repo, app
    finally:
        set_event_sink(None)
        repo.close()


def _build(tc, nodes, edges, query="q"):
    skeleton = {"rationale": "r", "nodes": nodes, "edges": edges}
    res = tc.post("/hypothesis/build", json={"query": query, "skeleton": skeleton})
    assert res.status_code == 200, res.text
    return res.json()["graph_id"]


_TWO_GENES = (
    [{"id": "egfr", "type": "target", "label": "EGFR"},
     {"id": "kras", "type": "target", "label": "KRAS"}],
    [{"id": "e1", "source_id": "egfr", "target_id": "kras", "relation": "activates"}],
)


def _edge(tc, gid, eid="e1"):
    graph = tc.get(f"/hypothesis/{gid}").json()
    return next(e for e in graph["edges"] if e["id"] == eid)


def test_built_edge_is_llm_unvalidated_draft(client):
    tc, _repo, _app = client
    gid = _build(tc, *_TWO_GENES)
    e = _edge(tc, gid)
    assert e["proposal_source"] == "llm"
    assert e["validation_status"] == "unvalidated"


def _ground(tc, gid, node_id):
    r = tc.post(f"/hypothesis/{gid}/apply-edit", json={"edit": {
        "op": "set_grounding", "node_id": node_id,
        "ontology": "UniProt", "term_id": "P00533"}})
    assert r.status_code == 200, r.text


def test_grounding_endpoints_gives_display_entity_grounded_not_validated(client):
    # Grounding BOTH endpoints (the real grounding flow) must leave the edge
    # UNVALIDATED, but its derived display_status surfaces the entities-grounded nuance.
    tc, _repo, _app = client
    gid = _build(tc, *_TWO_GENES)
    _ground(tc, gid, "egfr")
    assert _edge(tc, gid)["validation_status"] == "unvalidated"  # one endpoint grounded: still unvalidated
    assert _edge(tc, gid)["display_status"] == "unvalidated"     # not yet both grounded
    _ground(tc, gid, "kras")
    e = _edge(tc, gid)
    assert e["validation_status"] == "unvalidated"              # grounding NEVER validates the edge
    assert e["display_status"] == "entity_grounded_relation_unchecked"


def test_known_records_kg_supported_direct_on_that_edge_only(client):
    tc, _repo, _app = client
    # two edges; only the first gets a known-check
    nodes = [{"id": "a", "type": "target", "label": "A"},
             {"id": "b", "type": "target", "label": "B"},
             {"id": "c", "type": "target", "label": "C"}]
    edges = [{"id": "e1", "source_id": "a", "target_id": "b", "relation": "activates"},
             {"id": "e2", "source_id": "b", "target_id": "c", "relation": "inhibits"}]
    gid = _build(tc, nodes, edges)
    r = tc.post(f"/hypothesis/{gid}/edges/e1/known")
    assert r.status_code == 200 and r.json()["found"] is True
    assert _edge(tc, gid, "e1")["validation_status"] == "kg_supported_direct"
    assert len(_edge(tc, gid, "e1")["validations"]) == 1
    assert _edge(tc, gid, "e2")["validation_status"] == "unvalidated"  # untouched


def test_known_not_found_marks_unsupported_but_keeps_edge(client):
    tc, _repo, app = client

    class _EmptyKG:
        def known(self, src, tgt):
            return EdgeKnowledge(found=False, summary="no direct edge")
        def expand(self, node, limit=8):
            return []

    app.dependency_overrides[hr.get_kg_service] = lambda: _EmptyKG()
    gid = _build(tc, *_TWO_GENES)
    r = tc.post(f"/hypothesis/{gid}/edges/e1/known")
    assert r.status_code == 200 and r.json()["found"] is False
    e = _edge(tc, gid)
    assert e["validation_status"] == "unsupported"   # explicitly marked
    graph = tc.get(f"/hypothesis/{gid}").json()
    assert any(x["id"] == "e1" for x in graph["edges"])  # NOT hidden
