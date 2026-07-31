# tests/hypothesis/orchestrator/test_methods_eval.py
"""MethodsGraphEvaluationRunner: methodological grounding, honest coverage gaps."""
from quration.hypothesis.evidence import EvidenceDirection
from quration.hypothesis.orchestrator.checkpoint import MethodChoice, ProposedTest
from quration.hypothesis.orchestrator.methods_eval import (
    MethodsGraphEvaluationRunner,
    MethodsGraphSupervisor,
)


class FakeProvider:
    def __init__(self, preconditions=None, matches=None, resolve_error=None,
                 preconditions_error=None):
        self._pre = preconditions or {}
        self._matches = matches or []
        self._resolve_error = resolve_error
        self._preconditions_error = preconditions_error

    def method_preconditions(self, method_id):
        if self._preconditions_error:
            raise self._preconditions_error
        if method_id not in self._pre:
            raise KeyError(method_id)
        return self._pre[method_id]

    def resolve_method_ids(self, keywords):
        if self._resolve_error:
            raise self._resolve_error
        return list(self._matches)


def _proposed(**kw):
    base = dict(edge_id="e1", gap="g", pipeline="p", data_accession="",
                relation="up-regulates", source_symbol=None, target_symbol=None, method=None)
    base.update(kw)
    return ProposedTest(**base)


_SALMON_PRE = {
    "method_id": "salmon",
    "assumptions": [
        {"name": "independence", "checkable": "pre_run",
         "threshold": None,
         "via": [{"statistical_method": "negative binomial", "evidence": "doi:10.1/x"}]},
    ],
    "diagnostics": [],
}


def test_run_grounded_when_relation_resolves_a_method_with_assumptions():
    # relation -> keywords -> resolve_method_ids -> ["salmon"] -> method_preconditions w/ assumptions
    p = FakeProvider(preconditions={"salmon": _SALMON_PRE}, matches=["salmon"])
    runner = MethodsGraphEvaluationRunner(p)
    res = runner.run(_proposed(relation="up-regulates"))
    assert res.raw["verdict"] == "GROUNDED"
    assert res.raw["evaluable"] is True
    assert res.raw["assumptions"][0]["name"] == "independence"
    assert res.raw["coverage_gap"] is False


def test_resolver_prefers_method_with_assumptions_over_first_hit():
    # resolve returns a bare method first (no assumptions), then one WITH assumptions.
    # ground_edge must use the assumption-bearing method (kallisto), not the first hit.
    _kallisto_pre = {
        "method_id": "kallisto",
        "assumptions": [{"name": "independence", "checkable": "pre_run",
                         "threshold": None, "via": []}],
        "diagnostics": [],
    }
    p = FakeProvider(
        preconditions={
            "bare": {"method_id": "bare", "assumptions": [], "diagnostics": []},
            "kallisto": _kallisto_pre,
        },
        matches=["bare", "kallisto"],
    )
    res = MethodsGraphEvaluationRunner(p).run(_proposed(relation="up-regulates"))
    assert res.raw["verdict"] == "GROUNDED"
    assert res.raw["method_id"] == "kallisto"


def test_no_assumptions_yields_coverage_gap():
    # ground_edge uses method_preconditions; a method with no assumptions cannot be
    # GROUNDED. PARTIALLY_GROUNDED is no longer reachable via run() — the method is
    # resolvable but yields no structured assumptions -> honest COVERAGE_GAP.
    p = FakeProvider(
        preconditions={"m1": {"method_id": "m1", "assumptions": [], "diagnostics": []}},
        matches=["m1"],
    )
    res = MethodsGraphEvaluationRunner(p).run(_proposed(relation="up-regulates"))
    assert res.raw["verdict"] == "COVERAGE_GAP"
    assert res.raw["method_id"] == "m1"


def test_broker_method_is_ignored_grounding_is_relation_driven():
    # A broker MethodChoice is present, but resolve_method_ids finds NOTHING for the
    # relation's readout -> honest COVERAGE_GAP. The broker score must NOT ground it.
    p = FakeProvider(preconditions={"kallisto": _SALMON_PRE}, matches=[])
    runner = MethodsGraphEvaluationRunner(p)
    res = runner.run(_proposed(relation="binds and activates", method=MethodChoice(
        method_id="kallisto", name="kallisto", score=0.55, source="structural", rationale="r")))
    assert res.raw["verdict"] == "COVERAGE_GAP"
    assert res.raw["method_id"] is None


def test_run_coverage_gap_when_method_id_unknown():
    # resolve returns an id with no method_preconditions entry -> KeyError -> skip -> COVERAGE_GAP
    p = FakeProvider(preconditions={}, matches=["ghost"])
    runner = MethodsGraphEvaluationRunner(p)
    res = runner.run(_proposed(relation="up-regulates"))
    assert res.raw["verdict"] == "COVERAGE_GAP"
    assert res.raw["coverage_gap"] is True


def test_run_coverage_gap_when_nothing_resolves():
    p = FakeProvider(preconditions={}, matches=[])
    runner = MethodsGraphEvaluationRunner(p)
    res = runner.run(_proposed(relation="up-regulates"))
    assert res.raw["verdict"] == "COVERAGE_GAP"


def test_run_not_evaluable_for_definitional_relation():
    p = FakeProvider()
    runner = MethodsGraphEvaluationRunner(p)
    res = runner.run(_proposed(relation="manifests as"))
    assert res.raw["verdict"] == "NOT_EVALUABLE"
    assert res.raw["evaluable"] is False


def test_interpret_returns_inconclusive_low_weight_evidence():
    p = FakeProvider(preconditions={"salmon": _SALMON_PRE}, matches=["salmon"])
    runner = MethodsGraphEvaluationRunner(p)
    proposed = _proposed(relation="up-regulates")
    res = runner.run(proposed)
    entry = MethodsGraphSupervisor().interpret(proposed, res)
    assert entry.direction == EvidenceDirection.INCONCLUSIVE
    assert 0.0 < entry.weight <= 0.05
    assert entry.edge_id == "e1"

    # Inverted deliberately. This used to assert
    # `entry.provenance.data_accession == "methods-graph"` — pinning in place a
    # PipelineRunProvenance carrying a fabricated run id and the literal string
    # "methods-graph" where a data accession belongs, for a path that runs no
    # pipeline and touches no data. That made the type's own promise ("a
    # reproducible pipeline run on named data") unfalsifiable.
    from quration.hypothesis.evidence import EvidenceKind
    from quration.hypothesis.provenance import (
        GroundingProvenance,
        PipelineRunProvenance,
    )

    assert entry.kind is EvidenceKind.FEASIBILITY
    assert isinstance(entry.provenance, GroundingProvenance)
    assert not isinstance(entry.provenance, PipelineRunProvenance)
    assert entry.provenance.verdict == entry.magnitude
    assert entry.provenance.source == "methods-graph"
    # No accession and no run id, because there is no run and no data.
    assert not hasattr(entry.provenance, "data_accession")
    assert not hasattr(entry.provenance, "run_id")


def test_run_coverage_gap_when_resolve_method_ids_raises():
    p = FakeProvider(resolve_error=OSError("db down"))
    runner = MethodsGraphEvaluationRunner(p)
    res = runner.run(_proposed(relation="up-regulates"))
    assert res.raw["verdict"] == "COVERAGE_GAP"
    assert res.raw["coverage_gap"] is True


def test_run_coverage_gap_when_method_preconditions_raises_generic():
    # method_preconditions raises a non-KeyError (e.g. DB connection) -> skip -> COVERAGE_GAP
    p = FakeProvider(preconditions={}, matches=["x"],
                     preconditions_error=ConnectionError("boom"))
    runner = MethodsGraphEvaluationRunner(p)
    res = runner.run(_proposed(relation="up-regulates"))
    assert res.raw["verdict"] == "COVERAGE_GAP"
    assert res.raw["coverage_gap"] is True
