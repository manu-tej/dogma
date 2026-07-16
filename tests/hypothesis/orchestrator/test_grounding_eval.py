# tests/hypothesis/orchestrator/test_grounding_eval.py
from quration.hypothesis.orchestrator.grounding_eval import GroundingResult, ground_edge


class FakeProvider:
    def resolve_method_ids(self, keywords):
        return ["m:deseq2"] if "differential expression" in keywords else []

    def method_preconditions(self, mid):
        return {
            "method_id": mid,
            "assumptions": [
                {"name": "asymptotic normality", "checkable": "pre_run",
                 "threshold": {"min_replicates_per_group": 3},
                 "via": [{"statistical_method": "MLE", "evidence": "doi:x"}]},
            ],
            "diagnostics": [],
        }


def test_grounded_edge_carries_per_assumption_outcomes():
    res = ground_edge(FakeProvider(), "up-regulates")
    assert isinstance(res, GroundingResult)
    assert res.verdict == "GROUNDED"
    assert res.method_id == "m:deseq2"
    a = res.assumptions[0]
    assert a.name == "asymptotic normality"
    assert a.checkable == "pre_run"
    assert a.threshold == {"min_replicates_per_group": 3}
    assert a.status == "unchecked"


def test_unmatched_relation_is_coverage_gap():
    res = ground_edge(FakeProvider(), "binds")        # FakeProvider returns no ids
    assert res.verdict == "COVERAGE_GAP"
    assert res.assumptions == []


def test_definitional_relation_is_not_evaluable():
    res = ground_edge(FakeProvider(), "manifests as")
    assert res.verdict == "NOT_EVALUABLE"


def test_none_provider_is_coverage_gap_not_crash():
    res = ground_edge(None, "up-regulates")
    assert res.verdict == "COVERAGE_GAP"
