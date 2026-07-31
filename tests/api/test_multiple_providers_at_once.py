"""Several providers live in one process, chosen per request.

There was one module-level `_loop`, built from one global `QURATION_PROVIDER`.
Switching provider meant restarting the backend, and asking two models the same
question meant restarting between them — which makes comparing them impractical
exactly when comparing them is the interesting thing to do.

Three hazards this locks down, all of which bit during the change:

  - Bypassing ``Depends(get_loop)`` to resolve the provider per request broke
    every test that swaps in a fake loop via ``dependency_overrides``, and would
    have broken any caller relying on the same mechanism. The injected loop must
    stay the default path.
  - Overriding the provider by mutating the global config would race: two
    in-flight requests naming different providers is precisely the situation
    this feature creates. The override travels as a copied config object.
  - A failure must not be cached, per provider. The CLI login or API key can
    appear between requests, and a cached failure would outlive the fix.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from quration.api import hypothesis_routes as hr


@pytest.fixture
def clean_loops(monkeypatch):
    monkeypatch.setattr(hr, "_loops", {})
    monkeypatch.setattr(hr, "_repo", None)
    monkeypatch.setenv("QURATION_HYPOTHESIS_DB", ":memory:")
    yield


def client() -> TestClient:
    app = FastAPI()
    app.include_router(hr.router)
    return TestClient(app, raise_server_exceptions=False)


def configure(monkeypatch, provider: str):
    """Patch in a *real* config with the provider set.

    Not a SimpleNamespace: `_config_for` deep-copies via pydantic's
    `model_copy`, which is the mechanism keeping the override off the global.
    A stub without it passes the tests that never reach the copy and blows up in
    the ones that do — testing the stub's shape rather than the behaviour.
    """
    from quration.config import get_config as real_get_config

    config = real_get_config().model_copy(deep=True)
    config.llm.provider = provider
    monkeypatch.setattr(hr, "get_config", lambda: config)
    return config


class TestProviderResolution:
    def test_none_falls_back_to_the_configured_provider(self, monkeypatch):
        configure(monkeypatch, "claude_subscription")
        assert hr.resolve_provider(None) == "claude_subscription"

    def test_an_explicit_provider_wins(self, monkeypatch):
        configure(monkeypatch, "claude_subscription")
        assert hr.resolve_provider("codex_subscription") == "codex_subscription"

    def test_case_and_whitespace_are_forgiven(self, monkeypatch):
        configure(monkeypatch, "anthropic")
        assert hr.resolve_provider("  Codex_Subscription ") == "codex_subscription"

    def test_an_unknown_provider_is_a_400_naming_the_real_ones(self, monkeypatch):
        """Not a 500. `_real_mode()` raises RuntimeError on an unknown name, so
        without this guard a typo reached it and surfaced as a server error."""
        configure(monkeypatch, "anthropic")
        with pytest.raises(Exception) as exc:
            hr.resolve_provider("clod")
        assert getattr(exc.value, "status_code", None) == 400
        assert "codex_subscription" in str(exc.value.detail)


class TestBothSubscriptionsAreReachable:
    def test_codex_is_a_real_provider(self):
        """It was absent from `_REAL_PROVIDERS`, so `_real_mode()` raised
        "Unknown Dogma LLM provider" and every request 500'd — the provider
        worked in isolation while the route it is used through did not."""
        assert "codex_subscription" in hr._REAL_PROVIDERS

    def test_claude_is_a_real_provider(self):
        assert "claude_subscription" in hr._REAL_PROVIDERS

    def test_neither_is_treated_as_demo(self):
        assert not (hr._REAL_PROVIDERS & hr._DEMO_PROVIDERS)


class TestLoopsAreCachedPerProvider:
    def test_two_providers_get_two_loops(self, monkeypatch, clean_loops):
        configure(monkeypatch, "anthropic")
        built = []

        def fake_build(repository=None, config=None, **_):
            built.append((config.llm.provider if config else None))
            return object()

        monkeypatch.setattr(
            "quration.hypothesis.orchestrator.real_pipeline.build_real_loop", fake_build
        )
        a = hr.build_loop_for("claude_subscription")
        b = hr.build_loop_for("codex_subscription")
        assert a is not b
        assert built == ["claude_subscription", "codex_subscription"]

    def test_the_same_provider_is_built_once(self, monkeypatch, clean_loops):
        configure(monkeypatch, "anthropic")
        calls = {"n": 0}

        def fake_build(repository=None, config=None, **_):
            calls["n"] += 1
            return object()

        monkeypatch.setattr(
            "quration.hypothesis.orchestrator.real_pipeline.build_real_loop", fake_build
        )
        first = hr.build_loop_for("claude_subscription")
        second = hr.build_loop_for("claude_subscription")
        assert first is second and calls["n"] == 1

    def test_a_failure_is_not_cached_for_that_provider(self, monkeypatch, clean_loops):
        from quration.llm.providers import LLMProviderUnavailableError

        configure(monkeypatch, "anthropic")

        def fake_build(repository=None, config=None, **_):
            raise LLMProviderUnavailableError("no CLI")

        monkeypatch.setattr(
            "quration.hypothesis.orchestrator.real_pipeline.build_real_loop", fake_build
        )
        for _ in range(2):
            with pytest.raises(Exception) as exc:
                hr.build_loop_for("codex_subscription")
            assert getattr(exc.value, "status_code", None) == 503
        assert hr._loops == {}, "a broken loop was memoised"


class TestTheOverrideDoesNotEscape:
    def test_the_global_config_is_not_mutated(self, monkeypatch, clean_loops):
        """The race this avoids: two concurrent requests naming different
        providers, where a global swap lets one build with the other's client."""
        live = configure(monkeypatch, "anthropic")
        overridden = hr._config_for("codex_subscription")
        assert overridden.llm.provider == "codex_subscription"
        assert live.llm.provider == "anthropic", "the override escaped onto the global"
        assert overridden is not live

    def test_the_llm_section_is_not_shared(self, monkeypatch, clean_loops):
        """A shallow copy would share `llm`, so setting provider on the copy
        would still land on the original — the bug this deep copy prevents."""
        live = configure(monkeypatch, "anthropic")
        overridden = hr._config_for("codex_subscription")
        assert overridden.llm is not live.llm

    def test_the_configured_provider_reuses_the_live_config(self, monkeypatch):
        """No pointless deep copy when nothing needs overriding."""
        cfg = configure(monkeypatch, "anthropic")
        assert hr._config_for("anthropic") is cfg


class TestTheProvidersEndpoint:
    def test_it_lists_both_subscriptions_and_the_default(self, monkeypatch, clean_loops):
        configure(monkeypatch, "claude_subscription")
        body = client().get("/hypothesis/providers").json()
        assert body["default"] == "claude_subscription"
        by_name = {p["name"]: p for p in body["providers"]}
        assert by_name["claude_subscription"]["kind"] == "subscription"
        assert by_name["codex_subscription"]["kind"] == "subscription"
        assert by_name["claude_subscription"]["is_default"] is True

    def test_an_unavailable_provider_says_why(self, monkeypatch, clean_loops):
        configure(monkeypatch, "anthropic")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        body = client().get("/hypothesis/providers").json()
        anthropic = next(p for p in body["providers"] if p["name"] == "anthropic")
        assert anthropic["available"] is False
        assert "ANTHROPIC_API_KEY" in anthropic["detail"]

    def test_demo_is_labelled_as_synthetic(self, monkeypatch, clean_loops):
        """It is always 'available'. Nothing must let that read as a real result."""
        configure(monkeypatch, "anthropic")
        body = client().get("/hypothesis/providers").json()
        demo = next(p for p in body["providers"] if p["name"] == "demo")
        assert demo["available"] is True
        assert "synthetic" in demo["detail"]


class TestDependencyOverridesStillWork:
    """The regression that broke 35 tests: resolving the provider per request
    bypassed Depends(get_loop) entirely, so overrides stopped applying."""

    def test_an_overridden_loop_is_used_when_no_provider_is_named(self, monkeypatch, clean_loops):
        configure(monkeypatch, "anthropic")
        sentinel = SimpleNamespace(
            start=lambda q: SimpleNamespace(graph_id="g1", kind="investigative"),
            get_graph=lambda gid: None,
        )
        app = FastAPI()
        app.include_router(hr.router)
        app.dependency_overrides[hr.get_loop] = lambda: sentinel
        resp = TestClient(app, raise_server_exceptions=False).post(
            "/hypothesis/start", json={"query": "does X drive Y?"}
        )
        assert resp.status_code == 200
        assert resp.json()["graph_id"] == "g1"
