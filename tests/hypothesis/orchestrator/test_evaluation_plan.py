from quration.hypothesis.orchestrator.evaluation_plan import (
    AssumptionOutcome, Claim, EvaluationPlan, ReadoutSpec, ResolvedReadout,
)


def test_minimal_plan_defaults_are_unresolved():
    plan = EvaluationPlan(
        edge_id="e1",
        claim=Claim(source_symbol="AKT", target_symbol="pAKT", relation="phosphorylates"),
        ideal_readout=ReadoutSpec(
            claimed_entity="AKT phospho-S473", modality="phospho",
            ideal_assay_class="phosphoproteomics",
        ),
    )
    assert plan.resolved_readout is None
    assert plan.directness is None          # unknown until a dataset is resolved
    assert plan.not_evaluable is False
    assert plan.expected_direction == "unknown"
    assert plan.assumptions == []


def test_assumption_outcome_carries_methodsgraph_shape():
    a = AssumptionOutcome(
        name="asymptotic normality", checkable="pre_run",
        threshold={"min_replicates_per_group": 3},
        via=[{"statistical_method": "MLE", "evidence": "doi:x"}],
    )
    assert a.status == "unchecked"
    assert a.threshold["min_replicates_per_group"] == 3


def test_resolved_readout_records_what_was_measured():
    r = ResolvedReadout(
        measured_entity="total AKT mRNA", measured_modality="transcript",
        assay="RNA-Seq", source="geo", accession="GSE123",
    )
    assert r.feature_present is None
