"""Integration tests: phospho protein-state grounding through the real HTTP routes.

These exercise what the unit tests bypass: JSON -> the bare ``GraphEdit`` union
coercion in ``/apply-edit``, FastAPI serialization of a ``protein_state`` grounding,
the ``ResolveIsoform`` validation error path, and round-trip persistence through GET.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from quration.api.hypothesis_routes import get_grounding_service, get_loop, router
from quration.hypothesis.orchestrator.demo import build_demo_loop
from quration.hypothesis.orchestrator.edge_chat import SetProteinStateGrounding
from quration.hypothesis.orchestrator.grounding import GroundingProposal
from quration.hypothesis.provenance import OntologyTermProvenance


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    loop = build_demo_loop()  # one loop instance, shared across requests
    app.dependency_overrides[get_loop] = lambda: loop
    return TestClient(app)


class _StubProteinStateGrounding:
    """A grounding backend that always proposes an AKT phospho-family state."""

    def ground(self, node):
        return GroundingProposal(
            found=True,
            summary="stub: AKT phospho-family state",
            proposed_edit=SetProteinStateGrounding(
                node_id=node.id,
                family_label="AKT (phospho-S473/T308)",
                members=[
                    OntologyTermProvenance(ontology="UniProt", term_id="P31749", label="AKT1"),
                    OntologyTermProvenance(ontology="UniProt", term_id="P31751", label="AKT2"),
                ],
                residues=["S473", "T308"],
            ),
        )


def _start(client) -> str:
    return client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]


_AKT_STATE = {
    "op": "set_protein_state_grounding",
    "node_id": "P00533",  # a node id present in the demo graph
    "family_label": "AKT (phospho-S473/T308)",
    "members": [
        {"kind": "ontology_term", "ontology": "UniProt", "term_id": "P31749", "label": "AKT1"},
        {"kind": "ontology_term", "ontology": "UniProt", "term_id": "P31751", "label": "AKT2"},
        {"kind": "ontology_term", "ontology": "UniProt", "term_id": "Q9Y243", "label": "AKT3"},
    ],
    "residues": ["S473", "T308"],
    "resolved_to": None,
}


def test_apply_edit_accepts_protein_state_via_json_union(client):
    gid = _start(client)
    resp = client.post(f"/hypothesis/{gid}/apply-edit", json={"edit": _AKT_STATE})
    assert resp.status_code == 200, resp.text  # bare-union coerced the JSON, didn't 422
    node = next(n for n in resp.json()["nodes"] if n["id"] == "P00533")
    g = node["grounding"]
    assert g["kind"] == "protein_state"
    assert {m["term_id"] for m in g["members"]} == {"P31749", "P31751", "Q9Y243"}
    assert g["modification"]["residues"] == ["S473", "T308"]
    assert g["resolved_to"] is None


def test_resolve_isoform_via_json_then_persists(client):
    gid = _start(client)
    client.post(f"/hypothesis/{gid}/apply-edit", json={"edit": _AKT_STATE})
    resp = client.post(
        f"/hypothesis/{gid}/apply-edit",
        json={"edit": {"op": "resolve_isoform", "node_id": "P00533", "resolved_to": "P31751"}},
    )
    assert resp.status_code == 200, resp.text
    # round-trip through GET (re-load + re-serialize the discriminated union)
    g = next(n for n in client.get(f"/hypothesis/{gid}").json()["nodes"] if n["id"] == "P00533")["grounding"]
    assert g["kind"] == "protein_state" and g["resolved_to"] == "P31751"


def test_resolve_isoform_clear_sets_back_to_none(client):
    gid = _start(client)
    client.post(f"/hypothesis/{gid}/apply-edit", json={"edit": _AKT_STATE})
    client.post(f"/hypothesis/{gid}/apply-edit",
                json={"edit": {"op": "resolve_isoform", "node_id": "P00533", "resolved_to": "P31751"}})
    resp = client.post(f"/hypothesis/{gid}/apply-edit",
                       json={"edit": {"op": "resolve_isoform", "node_id": "P00533", "resolved_to": None}})
    assert resp.status_code == 200, resp.text
    g = next(n for n in resp.json()["nodes"] if n["id"] == "P00533")["grounding"]
    assert g["kind"] == "protein_state" and g["resolved_to"] is None


def test_resolve_isoform_rejects_non_member_with_422(client):
    gid = _start(client)
    client.post(f"/hypothesis/{gid}/apply-edit", json={"edit": _AKT_STATE})
    resp = client.post(f"/hypothesis/{gid}/apply-edit",
                       json={"edit": {"op": "resolve_isoform", "node_id": "P00533", "resolved_to": "P99999"}})
    assert resp.status_code == 422
    assert "candidate isoform" in resp.json()["detail"]


def test_ground_route_serializes_a_protein_state_proposal():
    # The on-demand /ground entry point must serialize a protein_state proposed_edit
    # through its GroundingProposal response_model (not just the apply path).
    app = FastAPI()
    app.include_router(router)
    loop = build_demo_loop()
    app.dependency_overrides[get_loop] = lambda: loop
    app.dependency_overrides[get_grounding_service] = _StubProteinStateGrounding
    client = TestClient(app)

    gid = client.post("/hypothesis/start", json={"query": "q"}).json()["graph_id"]
    resp = client.post(f"/hypothesis/{gid}/nodes/P00533/ground")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["found"] is True
    edit = body["proposed_edit"]
    assert edit["op"] == "set_protein_state_grounding"
    assert {m["term_id"] for m in edit["members"]} == {"P31749", "P31751"}
    assert edit["residues"] == ["S473", "T308"]

    # and the proposal round-trips back through /apply-edit (accept), grounding the node
    applied = client.post(f"/hypothesis/{gid}/apply-edit", json={"edit": edit})
    assert applied.status_code == 200, applied.text
    g = next(n for n in applied.json()["nodes"] if n["id"] == "P00533")["grounding"]
    assert g["kind"] == "protein_state"
