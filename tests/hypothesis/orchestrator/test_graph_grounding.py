"""Defensive access to the methods-graph provider's RAG/grounding surface."""
from types import SimpleNamespace

from quration.hypothesis.orchestrator.graph_grounding import (
    grounding_text,
    provider_of,
)


class _RagProvider:
    def __init__(self, text="", raises=False):
        self._text, self._raises = text, raises
        self.calls = []
        self.hops = []

    def retrieve_context_for_keywords(self, keywords, *, k_hops=1):
        self.calls.append(list(keywords))
        self.hops.append(k_hops)
        if self._raises:
            raise RuntimeError("boom")
        return self._text


def test_provider_of_returns_capable_provider():
    p = _RagProvider("x")
    broker = SimpleNamespace(method_provider=p)
    assert provider_of(broker) is p


def test_provider_of_none_when_no_provider():
    broker = SimpleNamespace(method_provider=None)
    assert provider_of(broker) is None


def test_provider_of_none_when_provider_lacks_capability():
    # The hardcoded-registry case: a provider with get_methods() but no RAG.
    broker = SimpleNamespace(method_provider=SimpleNamespace(get_methods=lambda: []))
    assert provider_of(broker) is None


def test_provider_of_none_when_broker_has_no_attr():
    assert provider_of(SimpleNamespace()) is None


def test_grounding_text_passthrough():
    p = _RagProvider("# salmon neighborhood")
    assert grounding_text(p, ["salmon"]) == "# salmon neighborhood"
    assert p.calls == [["salmon"]]


def test_grounding_text_uses_two_hops_to_reach_assumptions():
    p = _RagProvider("x")
    grounding_text(p, ["salmon"])
    assert p.hops == [2]  # Method -> StatisticalMethod -> Assumption


def test_grounding_text_empty_is_none():
    assert grounding_text(_RagProvider(""), ["x"]) is None


def test_grounding_text_swallows_errors():
    assert grounding_text(_RagProvider(raises=True), ["x"]) is None
