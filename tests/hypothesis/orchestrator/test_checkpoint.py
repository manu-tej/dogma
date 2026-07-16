"""Tests for orchestrator checkpoint data types."""

from quration.hypothesis.orchestrator.checkpoint import (
    MethodChoice,
    PipelineResult,
    ProposedTest,
    QueryKind,
    StartResult,
)


def test_query_kind_values():
    assert QueryKind.SIMPLE.value == "simple"
    assert QueryKind.INVESTIGATIVE.value == "investigative"


def test_proposed_test_optional_estimates_default_none():
    t = ProposedTest(edge_id="e1", gap="low-n", pipeline="nf-core/rnaseq", data_accession="GSE1")
    assert t.est_cost is None
    assert t.est_time is None


def test_pipeline_result_raw_defaults_empty():
    r = PipelineResult(run_id="run1", data_accession="GSE1", summary="done")
    assert r.raw == {}


def test_start_result_graph_id_optional():
    s = StartResult(kind=QueryKind.SIMPLE)
    assert s.graph_id is None


def test_public_exports_importable():
    import quration.hypothesis.orchestrator as o

    for name in (
        "QueryKind", "ProposedTest", "PipelineResult", "StartResult",
        "Supervisor", "PipelineRunner", "HypothesisLoop",
    ):
        assert hasattr(o, name), f"missing export: {name}"


def test_method_choice_round_trips():
    choice = MethodChoice(
        method_id="deseq2-differential-expression",
        name="DESeq2 Differential Expression",
        score=0.71,
        source="structural",
        rationale="DESeq2 fits an rna_seq test of EGFR↔KRAS",
    )
    assert choice.source == "structural"
    assert choice.score == 0.71


def test_proposed_test_method_defaults_to_none():
    proposed = ProposedTest(edge_id="e1", gap="g", pipeline="p", data_accession="GSE1")
    assert proposed.method is None


def test_proposed_test_carries_method_choice():
    choice = MethodChoice(method_id="m", name="M", score=0.5,
                          source="fallback", rationale="r")
    proposed = ProposedTest(edge_id="e1", gap="g", pipeline="p",
                            data_accession="GSE1", method=choice)
    assert proposed.method is not None
    assert proposed.method.method_id == "m"
    assert proposed.method.source == "fallback"
