# tests/hypothesis/connectors/test_signor_cache.py
"""Tests for the in-process SIGNOR fetch memo."""

import pytest

import quration.hypothesis.connectors.signor as sig


def test_cached_signor_fetch_memoizes_by_entity(monkeypatch):
    calls = []

    def fake_default(entity):
        calls.append(entity)
        return [{"IDA": "P00533"}]

    monkeypatch.setattr(sig, "default_signor_fetch", fake_default)
    sig._SIGNOR_CACHE.clear()

    assert sig.cached_signor_fetch("P00533") == [{"IDA": "P00533"}]
    assert sig.cached_signor_fetch("P00533") == [{"IDA": "P00533"}]
    assert calls == ["P00533"]  # fetched only once


def test_cached_signor_fetch_does_not_cache_errors(monkeypatch):
    sig._SIGNOR_CACHE.clear()
    state = {"fail": True}

    def fake_default(entity):
        if state["fail"]:
            raise RuntimeError("net")
        return [{"IDA": "X"}]

    monkeypatch.setattr(sig, "default_signor_fetch", fake_default)
    with pytest.raises(RuntimeError):
        sig.cached_signor_fetch("X")
    state["fail"] = False
    assert sig.cached_signor_fetch("X") == [{"IDA": "X"}]


def test_signor_license_is_declared():
    assert "NC" in sig.SIGNOR_LICENSE  # non-commercial flagged
