"""LlmAuthoringSuggester authors the graph from the query, ignoring derived seeds."""

from quration.hypothesis.graph import Edge, Node, NodeType
from quration.hypothesis.orchestrator.authoring_suggester import LlmAuthoringSuggester
from quration.hypothesis.orchestrator.seeding import SeedSkeleton


class FakeSeeding:
    def __init__(self):
        self.calls: list[str] = []

    def author_skeleton(self, query: str) -> SeedSkeleton:
        self.calls.append(query)
        return SeedSkeleton(
            rationale="r",
            nodes=[
                Node(id="ptx", type=NodeType.COMPOUND, label="paclitaxel"),
                Node(id="AXL", type=NodeType.TARGET, label="AXL"),
            ],
            edges=[Edge(id="e1", source_id="ptx", target_id="AXL", relation="inhibits")],
        )


def test_expand_authors_from_query_and_ignores_seeds():
    seeding = FakeSeeding()
    sugg = LlmAuthoringSuggester(seeding)
    result = sugg.expand(["IGNORED_SEED"], query="how does AXL inhibition...")
    assert seeding.calls == ["how does AXL inhibition..."]
    assert {n.id for n in result.nodes} == {"ptx", "AXL"}
    assert [e.id for e in result.edges] == ["e1"]


def test_expand_handles_none_query():
    seeding = FakeSeeding()
    LlmAuthoringSuggester(seeding).expand([])
    assert seeding.calls == [""]


def test_check_pair_returns_none():
    assert LlmAuthoringSuggester(FakeSeeding()).check_pair("A", "B") is None


# ---------------------------------------------------------------------------
# uses_seeds attribute (perf gate)
# ---------------------------------------------------------------------------

def test_uses_seeds_is_false():
    """LlmAuthoringSuggester opts out of seed derivation."""
    assert LlmAuthoringSuggester(FakeSeeding()).uses_seeds is False
