# tests/hypothesis/orchestrator/test_real_pipeline_path_wiring.py
"""build_real_loop wires the LlmAuthoringSuggester (B-lean) in live mode, and still
degrades to the demo seams when no provider is available."""

import quration.hypothesis.orchestrator.real_pipeline as rp
from quration.hypothesis.orchestrator.authoring_suggester import LlmAuthoringSuggester
from quration.hypothesis.orchestrator.real_pipeline import _GroundingSupervisor


def _stub_llm(monkeypatch):
    monkeypatch.setattr("quration.llm.providers.get_provider_from_config", lambda *a, **k: object())
    monkeypatch.setattr("quration.llm.providers.get_model_for_config", lambda *a, **k: "m")
    monkeypatch.setattr("quration.broker.method_broker.MethodBroker", lambda cfg: object())


def test_wires_llm_authoring_suggester_in_live_mode(monkeypatch):
    _stub_llm(monkeypatch)
    loop = rp.build_real_loop()
    assert isinstance(loop._suggester, LlmAuthoringSuggester)
    assert isinstance(loop._supervisor, _GroundingSupervisor)


def test_provider_failure_still_degrades_to_demo(monkeypatch):
    from quration.hypothesis.orchestrator.demo import DemoSuggester

    def boom(*a, **k):
        raise RuntimeError("no creds")

    monkeypatch.setattr("quration.llm.providers.get_provider_from_config", boom)
    monkeypatch.setattr("quration.broker.method_broker.MethodBroker", lambda cfg: object())
    loop = rp.build_real_loop()
    assert isinstance(loop._suggester, DemoSuggester)
