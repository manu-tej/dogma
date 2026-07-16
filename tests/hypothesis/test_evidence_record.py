from quration.hypothesis.evidence import EvidenceRecord, ResolverProvenance
from quration.hypothesis.orchestrator.evaluation_plan import AssumptionOutcome


def test_evidence_record_is_a_fact_not_a_verdict():
    rec = EvidenceRecord(
        edge_id="e1",
        claim_signature=("AKT", "pAKT", "phosphorylates"),
        measured_vs_claimed="measured total AKT mRNA; claim is phospho-S473",
        dataset_context={"accession": "GSE123"},
        per_assumption_outcomes=[AssumptionOutcome(name="independence")],
        directness="proxy_modality",
        caveats=["transcriptomic proxy for a phospho claim"],
        provenance=ResolverProvenance(model="sonnet", sources_searched=["geo", "pride"]),
    )
    # no verdict / weight / score fields exist on the record
    assert not hasattr(rec, "weight")
    assert rec.raw_result is None
    assert rec.directness == "proxy_modality"
