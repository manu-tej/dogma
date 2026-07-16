# tests/hypothesis/orchestrator/test_loop_fallback.py
"""The /start empty-KG fallback hook on HypothesisLoop, and the uses_seeds perf gate."""

from quration.hypothesis.connectors.base import SuggestionResult
from quration.hypothesis.graph import Edge, Node, NodeType
from quration.hypothesis.orchestrator.checkpoint import QueryKind
from quration.hypothesis.orchestrator.loop import HypothesisLoop
from quration.hypothesis.repository import InMemoryHypothesisRepository


class _Sup:
    def triage(self, q):
        return QueryKind.INVESTIGATIVE

    def seeds_for(self, q):
        return ["P00533"]

    def propose_test(self, g):
        return None

    def interpret(self, p, r):
        return None


def _nodes_edges(prefix):
    return (
        [Node(id=f"{prefix}1", type=NodeType.TARGET, label="A"),
         Node(id=f"{prefix}2", type=NodeType.TARGET, label="B")],
        [Edge(
            id=f"{prefix}-e",
            source_id=f"{prefix}1",
            target_id=f"{prefix}2",
            relation="activates",
        )],
    )


class _EmptySuggester:
    def expand(self, seeds, query=None):
        return SuggestionResult(nodes=[], edges=[])

    def check_pair(self, s, t):
        return None


class _KgSuggester:
    def expand(self, seeds, query=None):
        n, e = _nodes_edges("KG")
        return SuggestionResult(nodes=n, edges=e)

    def check_pair(self, s, t):
        return None


def _fallback(query):
    n, e = _nodes_edges("LLM")
    return SuggestionResult(nodes=n, edges=e)


def _loop(suggester):
    return HypothesisLoop(
        repository=InMemoryHypothesisRepository(),
        suggester=suggester,
        supervisor=_Sup(),
        runner=None,
        empty_seed_fallback=_fallback,
        id_factory=lambda: "g1",
    )


def test_fallback_used_when_suggester_returns_no_edges():
    loop = _loop(_EmptySuggester())
    graph = loop.get_graph(loop.start("q").graph_id)
    assert {e.id for e in graph.edges} == {"LLM-e"}


def test_fallback_not_used_when_suggester_has_edges():
    loop = _loop(_KgSuggester())
    graph = loop.get_graph(loop.start("q").graph_id)
    assert {e.id for e in graph.edges} == {"KG-e"}


def test_no_fallback_configured_keeps_empty_graph():
    loop = HypothesisLoop(
        repository=InMemoryHypothesisRepository(),
        suggester=_EmptySuggester(),
        supervisor=_Sup(),
        runner=None,
        id_factory=lambda: "g2",
    )
    graph = loop.get_graph(loop.start("q").graph_id)
    assert graph.edges == []


# ---------------------------------------------------------------------------
# uses_seeds perf gate — loop-level tests
# ---------------------------------------------------------------------------

class _RecordingSuper:
    """Supervisor that records seeds_for calls (or can be made to raise)."""

    def __init__(self, raise_on_seeds=False):
        self.seeds_for_calls: list[str] = []
        self._raise = raise_on_seeds

    def triage(self, q):
        return QueryKind.INVESTIGATIVE

    def seeds_for(self, q):
        if self._raise:
            raise AssertionError("seeds_for must NOT be called")
        self.seeds_for_calls.append(q)
        return ["P00533"]

    def propose_test(self, g):
        return None

    def interpret(self, p, r):
        return None


class _NoSeedsSuggester:
    """Suggester that opts out of seed derivation (uses_seeds = False)."""

    uses_seeds = False

    def __init__(self):
        self.expand_calls: list[list] = []

    def expand(self, seeds, query=None):
        self.expand_calls.append(seeds)
        n, e = _nodes_edges("AUTH")
        return SuggestionResult(nodes=n, edges=e)

    def check_pair(self, s, t):
        return None


class _DefaultSuggester:
    """Suggester WITHOUT uses_seeds attribute (should behave as uses_seeds=True)."""

    def expand(self, seeds, query=None):
        n, e = _nodes_edges("DEF")
        return SuggestionResult(nodes=n, edges=e)

    def check_pair(self, s, t):
        return None


def test_loop_skips_seeds_for_when_suggester_opts_out():
    """When suggester.uses_seeds is False, loop.start() must NOT call seeds_for."""
    sup = _RecordingSuper(raise_on_seeds=True)  # raises if seeds_for is called
    sugg = _NoSeedsSuggester()
    loop = HypothesisLoop(
        repository=InMemoryHypothesisRepository(),
        suggester=sugg,
        supervisor=sup,
        runner=None,
        id_factory=lambda: "g3",
    )
    result = loop.start("test-query")
    assert result.graph_id == "g3"
    # expand was called with empty seeds
    assert sugg.expand_calls == [[]]


def test_loop_calls_seeds_for_when_suggester_uses_seeds_default():
    """When suggester has no uses_seeds attribute (default True), seeds_for is called."""
    sup = _RecordingSuper()
    sugg = _DefaultSuggester()
    loop = HypothesisLoop(
        repository=InMemoryHypothesisRepository(),
        suggester=sugg,
        supervisor=sup,
        runner=None,
        id_factory=lambda: "g4",
    )
    loop.start("regression-query")
    assert sup.seeds_for_calls == ["regression-query"]
