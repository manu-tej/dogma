"""A configured-but-unusable LLM provider must fail, not fabricate.

Before this, a machine with `provider = "anthropic"` (the default, see
`config.py`) and no `ANTHROPIC_API_KEY` answered *every* question with the same
synthetic graph, at HTTP 200:

    POST /hypothesis/start {"query": "Does SOD1 aggregation drive motor neuron
                                     death in ALS?"}
    -> 200
       nodes: P00533 EGFR, P01116 KRAS, RESIST "drug resistance"
       edges: EGFR -> KRAS "up-regulates activity", proposal_source="llm"

Nothing about SOD1, ALS or motor neurons. `proposal_source="llm"` on edges no
model had produced. `UniProt:RESIST` on a phenotype, which cannot have a UniProt
accession. The only signal was a `logger.warning` in the server log.

Demo mode is still supported and still tested here — it just has to be asked for.
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from quration.api import hypothesis_routes as hr
from quration.llm.providers import LLMProviderUnavailableError

#: Fixture content of the demo seams. None of it may appear in a live-mode error.
DEMO_LEAKAGE = ("EGFR", "P00533", "KRAS", "P01116", "RESIST", "drug resistance")

QUESTION = "Does SOD1 aggregation drive motor neuron death in ALS?"


@pytest.fixture
def clean_singletons(monkeypatch):
    """The module memoises the loop and chat services process-wide."""
    monkeypatch.setattr(hr, "_loop", None)
    monkeypatch.setattr(hr, "_repo", None)
    monkeypatch.setattr(hr, "_seeding", None)
    monkeypatch.setattr(hr, "_edge_chat", None)
    monkeypatch.setattr(hr, "_node_chat", None)
    monkeypatch.setenv("QURATION_HYPOTHESIS_DB", ":memory:")
    yield


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(hr.router)
    # No dependency_overrides: the point is to exercise the real wiring.
    return TestClient(app, raise_server_exceptions=False)


def _configure(monkeypatch, provider: str) -> None:
    monkeypatch.setattr(
        hr, "get_config", lambda: SimpleNamespace(llm=SimpleNamespace(provider=provider))
    )


def _break_provider(monkeypatch, on_call=None):
    """Simulate a configured provider that cannot be constructed.

    There are two seams and both matter. `hypothesis_routes` binds
    `get_provider_from_config` at module import, so `_resolve_chat_llm` reads
    `hr.get_provider_from_config`. `real_pipeline.build_real_loop` imports it
    *inside the function*, so it reads the attribute off `quration.llm.providers`
    at call time. Patching only one leaves the other running the real thing, which
    still 503s here for want of a key — so the test passes while measuring
    nothing. Patch both.
    """
    from quration.llm import providers as providers_module

    def failing():
        if on_call is not None:
            on_call()
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    monkeypatch.setattr(hr, "get_provider_from_config", failing)
    monkeypatch.setattr(providers_module, "get_provider_from_config", failing)


def test_missing_api_key_returns_503_not_a_fabricated_graph(
    monkeypatch, clean_singletons
):
    _configure(monkeypatch, "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _break_provider(monkeypatch)

    response = _client().post("/hypothesis/start", json={"query": QUESTION})

    assert response.status_code == 503, response.text


def test_the_error_body_leaks_no_demo_content(monkeypatch, clean_singletons):
    """The failure must not smuggle the fixture graph out in the error payload."""
    _configure(monkeypatch, "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    _break_provider(monkeypatch)

    body = _client().post("/hypothesis/start", json={"query": QUESTION}).text

    for token in DEMO_LEAKAGE:
        assert token not in body, f"demo content {token!r} leaked into a live-mode error"


def test_the_error_states_the_remedy(monkeypatch, clean_singletons):
    """A 503 with no instructions just moves the confusion."""
    _configure(monkeypatch, "anthropic")
    _break_provider(monkeypatch)

    detail = _client().post("/hypothesis/start", json={"query": QUESTION}).json()["detail"]

    assert "ANTHROPIC_API_KEY" in detail
    assert "QURATION_PROVIDER=demo" in detail


def test_explicit_demo_mode_still_works(monkeypatch, clean_singletons):
    """Demo mode is a legitimate configuration; only the silence was the problem."""
    _configure(monkeypatch, "demo")

    response = _client().post("/hypothesis/start", json={"query": QUESTION})

    assert response.status_code == 200, response.text
    assert response.json()["graph_id"]


def test_chat_services_refuse_rather_than_answering_from_demo_seams(
    monkeypatch, clean_singletons
):
    """The chat seams had the same fallback, and it is the more insidious one: an
    answer in prose carries no `suggested_by` field to inspect."""
    _configure(monkeypatch, "anthropic")
    _break_provider(monkeypatch)

    with pytest.raises(LLMProviderUnavailableError):
        hr._resolve_chat_llm()

    # Inside a dependency the same condition becomes 503, not an unhandled 500.
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as caught:
        hr._chat_llm_or_503()
    assert caught.value.status_code == 503


def test_demo_mode_chat_services_resolve_to_none(monkeypatch, clean_singletons):
    _configure(monkeypatch, "demo")
    assert hr._resolve_chat_llm() is None
    assert hr._chat_llm_or_503() is None


def test_a_failed_loop_is_not_cached(monkeypatch, clean_singletons):
    """The key can appear in the environment between requests. A cached failure
    would outlive the fix and need a restart to clear."""
    _configure(monkeypatch, "anthropic")
    calls = {"n": 0}
    _break_provider(monkeypatch, on_call=lambda: calls.__setitem__("n", calls["n"] + 1))

    client = _client()
    for _ in range(2):
        assert client.post("/hypothesis/start", json={"query": QUESTION}).status_code == 503

    assert hr._loop is None, "a broken loop was memoised"
    assert calls["n"] >= 2, "the second request reused a cached failure"


def test_error_message_carries_the_underlying_cause(monkeypatch, clean_singletons):
    """Diagnosing "unavailable" needs the provider's own complaint, not just ours."""
    exc = LLMProviderUnavailableError("ANTHROPIC_API_KEY environment variable not set")
    assert "ANTHROPIC_API_KEY environment variable not set" in str(exc)
    assert LLMProviderUnavailableError.REMEDY in str(exc)
