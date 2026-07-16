# tests/hypothesis/orchestrator/test_loop_query_forwarding.py
"""loop.start forwards the query into suggester.expand(seeds, query=...)."""

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


class _QueryCapturingSuggester:
    def __init__(self):
        self.seen_query = "UNSET"

    def expand(self, seeds, query=None):
        self.seen_query = query
        return SuggestionResult(
            nodes=[Node(id="P1", type=NodeType.TARGET, label="A"),
                   Node(id="P2", type=NodeType.TARGET, label="B")],
            edges=[Edge(id="e1", source_id="P1", target_id="P2", relation="activates")],
        )

    def check_pair(self, s, t):
        return None


def test_start_forwards_query_to_expand():
    suggester = _QueryCapturingSuggester()
    loop = HypothesisLoop(InMemoryHypothesisRepository(), suggester, _Sup(),
                          runner=None, id_factory=lambda: "g1")
    loop.start("does EGFR drive resistance?")
    assert suggester.seen_query == "does EGFR drive resistance?"
