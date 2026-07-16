# tests/hypothesis/orchestrator/test_real_pipeline_wiring.py
"""build_real_loop wires the live LlmAuthoringSuggester + degradation + fallback.

NOTE (Task 10): the hardcoded Spearman correlation executor and the dispatch lane
were removed. The loop's only runner is now MethodsGraphEvaluationRunner, and the
supervisor is a _GroundingSupervisor (live triage/seeds/propose, methods-graph
interpret). The primary-suggester assertions live in test_real_pipeline_path_wiring.py;
this file retains the supervisor/fallback, degradation, and runner-type coverage.
"""

import quration.hypothesis.orchestrator.real_pipeline as rp
from quration.hypothesis.orchestrator.authoring_suggester import LlmAuthoringSuggester
from quration.hypothesis.orchestrator.demo import DemoSuggester
from quration.hypothesis.orchestrator.methods_eval import MethodsGraphEvaluationRunner
from quration.hypothesis.orchestrator.real_pipeline import _GroundingSupervisor


def _stub_llm(monkeypatch):
    monkeypatch.setattr("quration.llm.providers.get_provider_from_config", lambda *a, **k: object())
    monkeypatch.setattr("quration.llm.providers.get_model_for_config", lambda *a, **k: "m")
    # Keep broker construction hermetic (no methods-graph dependency in the test).
    monkeypatch.setattr("quration.broker.method_broker.MethodBroker", lambda cfg: object())


def test_wires_llm_authoring_suggester_grounding_supervisor_and_fallback(monkeypatch):
    _stub_llm(monkeypatch)
    loop = rp.build_real_loop()
    assert isinstance(loop._suggester, LlmAuthoringSuggester)
    assert isinstance(loop._supervisor, _GroundingSupervisor)
    assert isinstance(loop._runner, MethodsGraphEvaluationRunner)
    assert loop._empty_seed_fallback is not None


def test_provider_failure_degrades_to_demo(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no creds")

    monkeypatch.setattr("quration.llm.providers.get_provider_from_config", boom)
    monkeypatch.setattr("quration.broker.method_broker.MethodBroker", lambda cfg: object())
    loop = rp.build_real_loop()
    # Demo-degraded path still grounds against the methods graph (no correlation).
    assert isinstance(loop._suggester, DemoSuggester)
    assert isinstance(loop._supervisor, _GroundingSupervisor)
    assert isinstance(loop._runner, MethodsGraphEvaluationRunner)
    assert loop._empty_seed_fallback is None


def test_fallback_authors_skeleton_via_seeding_service(monkeypatch):
    from quration.hypothesis.connectors.base import SuggestionResult
    from quration.hypothesis.graph import Edge, Node, NodeType
    from quration.hypothesis.orchestrator.seeding import SeedSkeleton

    monkeypatch.setenv("QURATION_ALLOW_NONCOMMERCIAL_KG", "1")
    _stub_llm(monkeypatch)
    skeleton = SeedSkeleton(
        nodes=[Node(id="a", type=NodeType.TARGET, label="A"),
               Node(id="b", type=NodeType.TARGET, label="B")],
        edges=[Edge(id="e", source_id="a", target_id="b", relation="drives")],
        rationale="r",
    )
    monkeypatch.setattr(
        "quration.hypothesis.orchestrator.seeding.LlmSeedingService.author_skeleton",
        lambda self, q: skeleton,
    )
    loop = rp.build_real_loop()
    result = loop._empty_seed_fallback("some query")
    assert isinstance(result, SuggestionResult)
    assert {e.id for e in result.edges} == {"e"}
    assert {n.id for n in result.nodes} == {"a", "b"}


def test_methods_graph_runner_used_regardless_of_neighborhood(monkeypatch):
    """The methods-graph grounding lane is the only runner — no dispatch, no
    correlation — whether or not the provider exposes neighborhood()."""

    class _FakeProvider:
        def retrieve_context_for_keywords(self, keywords, *, k_hops=1):
            return ""

        def neighborhood(self, method_id):
            return []

    class _FakeBroker:
        method_provider = _FakeProvider()

    monkeypatch.setattr("quration.llm.providers.get_provider_from_config", lambda *a, **k: object())
    monkeypatch.setattr("quration.llm.providers.get_model_for_config", lambda *a, **k: "m")
    monkeypatch.setattr("quration.broker.method_broker.MethodBroker", lambda cfg: _FakeBroker())

    loop = rp.build_real_loop()

    assert isinstance(loop._runner, MethodsGraphEvaluationRunner)
    assert isinstance(loop._supervisor, _GroundingSupervisor)
