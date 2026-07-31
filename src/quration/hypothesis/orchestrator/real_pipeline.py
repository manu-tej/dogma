"""Real evidence seam: an approved test is grounded against the methods graph.

The hardcoded Spearman correlation executor was removed. The loop's only runner is
the methods-graph grounding lane (`MethodsGraphEvaluationRunner`): an edge is either
grounded (method + assumptions, INCONCLUSIVE-only) or honestly "execution pending"
(COVERAGE_GAP). `LiveSupervisor` provides the gene-symbol/relation enrichment used
by `propose_test`; `_GroundingSupervisor` wraps it so triage/seeds/propose come from
the live seeding lane and interpret comes from the methods-graph supervisor.
Real pipeline execution lands in slice 2.
"""

from __future__ import annotations

import logging

from quration.hypothesis.connectors.base import SuggestionResult
from quration.hypothesis.graph import NodeType
from quration.hypothesis.orchestrator.checkpoint import ProposedTest
from quration.hypothesis.orchestrator.demo import DemoSupervisor
from quration.hypothesis.orchestrator.loop import HypothesisLoop
from quration.hypothesis.repository import HypothesisRepository, InMemoryHypothesisRepository

logger = logging.getLogger(__name__)


class LiveSupervisor(DemoSupervisor):
    """Reuses the demo triage/seeds, but proposes with gene symbols + the edge's
    relation so the methods-graph grounding lane has the context it needs.

    Interpret is inherited from DemoSupervisor and never called via the
    `_GroundingSupervisor` wrapper (which delegates interpret to the methods-graph
    supervisor)."""

    def propose_test(self, graph) -> ProposedTest | None:
        base = super().propose_test(graph)
        if base is None:
            return None
        edge = graph.get_edge(base.edge_id)
        if edge is None:  # symbols stay None -> grounding handles missing context
            return base
        source = graph.get_node(edge.source_id)
        target = graph.get_node(edge.target_id)
        base.source_symbol = source.label if source and source.type == NodeType.TARGET else None
        base.target_symbol = target.label if target and target.type == NodeType.TARGET else None
        base.relation = edge.relation
        return base


class _GroundingSupervisor:
    """triage/seeds/propose from the live supervisor; interpret from methods-graph."""

    def __init__(self, live, methods):
        self._live = live
        self._methods = methods

    def triage(self, query):
        return self._live.triage(query)

    def seeds_for(self, query):
        return self._live.seeds_for(query)

    def propose_test(self, graph):
        return self._live.propose_test(graph)

    def interpret(self, proposed, result):
        return self._methods.interpret(proposed, result)


def _skeleton_to_suggestion(skeleton) -> SuggestionResult:
    return SuggestionResult(nodes=list(skeleton.nodes), edges=list(skeleton.edges))


def _build_live_seeding(provider):
    """Build (suggester, supervisor, empty_seed_fallback) for B-lean real mode.

    The LLM authors the graph (full mechanism, variable) as the primary suggester;
    KG path-retrieval is no longer used at /start. The deriver/supervisor remain for
    the test/propose_test flow. Wiring errors here are bugs and propagate (only
    provider-credential failures are caught upstream in build_real_loop).
    """
    from quration.data_sources.uniprot import UniProtClient
    from quration.hypothesis.orchestrator.authoring_suggester import LlmAuthoringSuggester
    from quration.hypothesis.orchestrator.seed_derivation import (
        LiveSeedSupervisor,
        LlmSeedDeriver,
    )
    from quration.hypothesis.orchestrator.seeding import LlmSeedingService
    from quration.llm.providers import get_model_for_config

    deriver = LlmSeedDeriver(provider, get_model_for_config(tier="fast"), UniProtClient())
    seeding = LlmSeedingService(provider, get_model_for_config(tier="smart"))

    suggester = LlmAuthoringSuggester(seeding)
    supervisor = LiveSeedSupervisor(deriver)

    def fallback(query: str) -> SuggestionResult:
        return _skeleton_to_suggestion(seeding.author_skeleton(query))

    return suggester, supervisor, fallback


def build_real_loop(repository: HypothesisRepository | None = None, **_ignored) -> HypothesisLoop:
    """A HypothesisLoop with methods-graph grounding as the only runner.

    The hardcoded Spearman correlation executor was removed: an edge is grounded
    (method + assumptions, INCONCLUSIVE) or honestly 'execution pending'
    (COVERAGE_GAP). The method broker attaches an advisory recommendation to each
    proposed test. Real pipeline execution lands in slice 2.
    """
    from quration.broker.method_broker import MethodBroker
    from quration.config import get_config
    from quration.hypothesis.orchestrator.graph_grounding import provider_of
    from quration.hypothesis.orchestrator.method_selection import (
        BrokerMethodSelector,
        enrich_intent,
    )
    from quration.hypothesis.orchestrator.methods_eval import (
        MethodsGraphEvaluationRunner,
        MethodsGraphSupervisor,
    )

    # MethodBroker raises if methods-graph is misconfigured; that is not recoverable
    # here, so it is intentionally OUTSIDE the degradation guard below.
    broker = MethodBroker(get_config())
    selector = BrokerMethodSelector(broker, intent_author=enrich_intent)
    methods_provider = provider_of(broker)

    # The only runner: methods-graph grounding. ground_edge handles a None provider
    # (returns COVERAGE_GAP), so non-grounded edges are honest "execution pending".
    runner = MethodsGraphEvaluationRunner(methods_provider)

    # A configured-but-unusable LLM provider is a configuration error, not something
    # to paper over. This used to degrade to DemoSuggester() on any exception, which
    # meant a machine with no ANTHROPIC_API_KEY answered every question — about ALS,
    # about anything — with the same synthetic EGFR -> KRAS -> drug-resistance graph,
    # at HTTP 200, with `proposal_source="llm"` on edges no model had produced. The
    # warning it logged went to the server log, where no user of the API sees it.
    #
    # Demo mode is still fully supported; it now has to be requested, via
    # QURATION_PROVIDER=demo. Silence is the thing being removed, not the capability.
    from quration.llm.providers import (
        LLMProviderUnavailableError,
        get_provider_from_config,
    )

    try:
        provider = get_provider_from_config()
    except Exception as exc:
        logger.error("live LLM provider unavailable; refusing to seed with demo content")
        raise LLMProviderUnavailableError(str(exc)) from exc

    # Live path: LLM provider is available. Build live seeding components.
    live_suggester, live_supervisor, fallback = _build_live_seeding(provider)
    supervisor = _GroundingSupervisor(live_supervisor, MethodsGraphSupervisor())
    return HypothesisLoop(
        repository=repository or InMemoryHypothesisRepository(),
        suggester=live_suggester,
        supervisor=supervisor,
        runner=runner,
        selector=selector,
        empty_seed_fallback=fallback,
    )
