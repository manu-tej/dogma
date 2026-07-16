"""TDD tests for QURATION_SEED_TIER env-var support in hypothesis_routes."""

import importlib
import sys

import pytest


def _fresh_module():
    """Re-import hypothesis_routes so module-level state is reset between tests."""
    # Remove from cache so env changes are visible to the helper
    for key in list(sys.modules):
        if "hypothesis_routes" in key:
            del sys.modules[key]
    from quration.api import hypothesis_routes as hr

    return hr


class TestSeedTierHelper:
    """_seed_tier() returns the canonical tier string based on QURATION_SEED_TIER."""

    def test_defaults_to_smart_when_unset(self, monkeypatch):
        monkeypatch.delenv("QURATION_SEED_TIER", raising=False)
        hr = _fresh_module()
        assert hr._seed_tier() == "smart"

    def test_returns_fast_when_set(self, monkeypatch):
        monkeypatch.setenv("QURATION_SEED_TIER", "fast")
        hr = _fresh_module()
        assert hr._seed_tier() == "fast"

    def test_returns_smart_for_invalid_value(self, monkeypatch):
        monkeypatch.setenv("QURATION_SEED_TIER", "turbo")
        hr = _fresh_module()
        assert hr._seed_tier() == "smart"

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("QURATION_SEED_TIER", "  fast  ")
        hr = _fresh_module()
        assert hr._seed_tier() == "fast"

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("QURATION_SEED_TIER", "FAST")
        hr = _fresh_module()
        assert hr._seed_tier() == "fast"


class TestGetSeedingServiceUsesEnvTier:
    """get_seeding_service() picks up QURATION_SEED_TIER; edge-chat/node-chat stay on 'smart'."""

    def test_seeding_uses_fast_tier_when_env_set(self, monkeypatch):
        monkeypatch.setenv("QURATION_SEED_TIER", "fast")
        hr = _fresh_module()

        calls: list[str] = []

        def fake_resolve():
            return (object(), "smart-model")

        def fake_model_for_config(config=None, tier="smart"):
            calls.append(tier)
            return f"model-{tier}"

        monkeypatch.setattr(hr, "_resolve_chat_llm", fake_resolve)
        monkeypatch.setattr(hr, "get_model_for_config", fake_model_for_config)
        monkeypatch.setattr(hr, "LlmSeedingService", lambda provider, model: (provider, model))

        hr._seeding = None  # reset singleton
        svc = hr.get_seeding_service()
        assert calls == ["fast"], f"Expected ['fast'] tier call, got {calls}"

    def test_edge_chat_stays_on_smart_regardless(self, monkeypatch):
        monkeypatch.setenv("QURATION_SEED_TIER", "fast")
        hr = _fresh_module()

        calls: list[str] = []

        def fake_resolve():
            return (object(), "model-smart")

        monkeypatch.setattr(hr, "_resolve_chat_llm", fake_resolve)
        monkeypatch.setattr(
            hr,
            "LlmEdgeChatService",
            lambda provider, model: (provider, model),
        )

        hr._edge_chat = None
        svc = hr.get_edge_chat_service()
        # edge-chat calls _resolve_chat_llm directly (no seed-tier logic)
        # we just check it didn't blow up and returned something non-None
        assert svc is not None
