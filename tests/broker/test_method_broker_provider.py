"""MethodBroker retains the resolved methods provider (for graph grounding)."""
from quration.broker.method_broker import MethodBroker
from quration.config import get_config


class _FakeProvider:
    def get_methods(self):
        return [{"id": "x", "name": "x"}]


def test_broker_retains_explicit_provider():
    fake = _FakeProvider()
    broker = MethodBroker(get_config(), method_provider=fake)
    assert broker.method_provider is fake


def test_broker_provider_is_none_without_env(monkeypatch):
    monkeypatch.delenv("QURATION_METHODS_GRAPH_DB", raising=False)
    broker = MethodBroker(get_config())
    assert broker.method_provider is None
