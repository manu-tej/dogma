# tests/hypothesis/orchestrator/test_path_judge.py
"""Tests for PathJudge (LLM picks the query-relevant candidate path per pair)."""

from quration.hypothesis.graph import Edge
from quration.hypothesis.orchestrator.path_judge import PathJudge


def _edge(s, t):
    return Edge(id=f"{s}-{t}", source_id=s, target_id=t, relation="activates")


class FakeProvider:
    def __init__(self, response):
        self.response = response
        self.last_system = None
        self.last_messages = None

    def create_message(self, messages, model, system=None, **kwargs):
        self.last_messages = messages
        self.last_system = system
        return self.response


_LABELS = {"A": "EGFR", "C1": "MAP2K1", "C2": "UBC", "B": "KRAS"}
# pair (A,B) has two candidates: index 0 via C1, index 1 via C2
_CANDIDATES = {
    ("A", "B"): [[_edge("A", "C1"), _edge("C1", "B")], [_edge("A", "C2"), _edge("C2", "B")]],
}


def test_judge_picks_named_index():
    judge = PathJudge(FakeProvider('{"0": 1}'), "model")   # pair index 0 -> candidate 1
    chosen = judge.select("does EGFR drive KRAS?", _CANDIDATES, _LABELS)
    assert chosen[("A", "B")] == _CANDIDATES[("A", "B")][1]


def test_judge_renders_labels_and_query_in_prompt():
    provider = FakeProvider('{"0": 0}')
    PathJudge(provider, "model").select("why resistance?", _CANDIDATES, _LABELS)
    blob = str(provider.last_messages)
    assert "EGFR" in blob and "MAP2K1" in blob and "why resistance?" in blob


def test_malformed_response_falls_back_to_shortest():
    judge = PathJudge(FakeProvider("not json"), "model")
    chosen = judge.select("q", _CANDIDATES, _LABELS)
    assert chosen[("A", "B")] == _CANDIDATES[("A", "B")][0]   # candidate 0 (first/shortest)


def test_out_of_range_index_falls_back():
    judge = PathJudge(FakeProvider('{"0": 9}'), "model")
    chosen = judge.select("q", _CANDIDATES, _LABELS)
    assert chosen[("A", "B")] == _CANDIDATES[("A", "B")][0]


def test_empty_candidate_list_is_skipped():
    judge = PathJudge(FakeProvider('{"0": 0}'), "model")
    chosen = judge.select("q", {("A", "B"): []}, _LABELS)
    assert ("A", "B") not in chosen
