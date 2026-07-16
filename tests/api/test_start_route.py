# tests/api/test_start_route.py
"""TestClient coverage for the live /start path (KG hit vs LLM fallback) + event detail."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from quration.api.hypothesis_routes import get_loop, get_repo, router
from quration.hypothesis.connectors.base import SuggestionResult
from quration.hypothesis.graph import Edge, Node, NodeType
from quration.hypothesis.observability import set_event_sink
from quration.hypothesis.orchestrator.checkpoint import QueryKind
from quration.hypothesis.orchestrator.loop import HypothesisLoop
from quration.hypothesis.provenance import KGEdgeProvenance
from quration.hypothesis.store import SqliteHypothesisRepository


class _Sup:
    def triage(self, q):
        return QueryKind.INVESTIGATIVE

    def seeds_for(self, q):
        return ["P00533"]

    def propose_test(self, g):
        return None

    def interpret(self, p, r):
        return None


class _Signorish:
    """Stub suggester returning one signor-provenanced edge."""

    def expand(self, seeds, query=None):
        return SuggestionResult(
            nodes=[Node(id="P00533", type=NodeType.TARGET, label="EGFR"),
                   Node(id="P01116", type=NodeType.TARGET, label="KRAS")],
            edges=[Edge(id="SIGNOR-1", source_id="P00533", target_id="P01116",
                        relation="activates", pending=True,
                        suggested_by=[KGEdgeProvenance(source="signor", reference="SIGNOR-1")])],
        )

    def check_pair(self, s, t):
        return None


class _Empty:
    def expand(self, seeds, query=None):
        return SuggestionResult(nodes=[], edges=[])

    def check_pair(self, s, t):
        return None


def _fallback(query):
    return SuggestionResult(
        nodes=[Node(id="L1", type=NodeType.TARGET, label="A"),
               Node(id="L2", type=NodeType.TARGET, label="B")],
        edges=[Edge(id="llm-1", source_id="L1", target_id="L2", relation="drives", pending=True)],
    )


def _client(suggester):
    app = FastAPI()
    app.include_router(router)
    repo = SqliteHypothesisRepository(":memory:")
    set_event_sink(repo)
    loop = HypothesisLoop(repository=repo, suggester=suggester, supervisor=_Sup(),
                          runner=None, empty_seed_fallback=_fallback,
                          id_factory=lambda: "g1")
    app.dependency_overrides[get_loop] = lambda: loop
    app.dependency_overrides[get_repo] = lambda: repo
    return TestClient(app), repo


def test_start_kg_hit_persists_signor_edge_and_records_event():
    client, _ = _client(_Signorish())
    resp = client.post("/hypothesis/start", json={"query": "EGFR vs KRAS?"})
    assert resp.status_code == 200
    gid = resp.json()["graph_id"]
    graph = client.get(f"/hypothesis/{gid}").json()
    assert {e["id"] for e in graph["edges"]} == {"SIGNOR-1"}
    events = client.get(f"/hypothesis/{gid}/events").json()
    start_event = next(ev for ev in events if ev.get("op") == "start")
    detail = start_event["detail"]
    assert detail["suggester_path"] == "kg"
    assert detail["sources_used"] == ["signor"]
    assert detail["n_edges"] == 1


def test_start_empty_kg_falls_back_to_llm_skeleton():
    client, _ = _client(_Empty())
    gid = client.post("/hypothesis/start", json={"query": "weather?"}).json()["graph_id"]
    graph = client.get(f"/hypothesis/{gid}").json()
    assert {e["id"] for e in graph["edges"]} == {"llm-1"}
    events = client.get(f"/hypothesis/{gid}/events").json()
    detail = next(ev for ev in events if ev.get("op") == "start")["detail"]
    assert detail["suggester_path"] == "llm_fallback"
    assert detail["sources_used"] == []
