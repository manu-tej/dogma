"""The scorer must not reward being wrong, or being verbose.

`src/quration/benchmarks/` had no tests at all. These lock down three defects that
made every number it produced unpublishable. Each assertion below failed before
the accompanying fix:

  1. `AccuracyCalculator` matched claims by bag-of-words overlap, so a claim
     asserting the *reverse* mechanism scored a perfect 1.0.
  2. It counted one increment per prediction but divided by the ground-truth
     count, so restating a single true claim five ways scored 2.5 — and
     `MetricResult.normalized` clamped that to 1.0, hiding it in the aggregate
     while `value` published the nonsense.
  3. `HallucinationDetector`, constructed with no reference vocabulary as the
     harness does, reported a rate of 0.0 for wholly invented genes, because the
     only check left was a regex over symbol *shape*.
"""

import pytest

from quration.benchmarks.metrics import (
    AccuracyCalculator,
    BenchmarkMetrics,
    HallucinationDetector,
    MetricResult,
)

TRUTH = ["EGFR upregulates KRAS", "KRAS drives drug resistance"]


@pytest.fixture
def acc() -> AccuracyCalculator:
    return AccuracyCalculator()


class TestAccuracyIsDirectionAware:
    def test_identical_claims_score_perfectly(self, acc):
        assert acc.calculate(TRUTH, TRUTH).value == pytest.approx(1.0)

    def test_reversed_claims_do_not_score_perfectly(self, acc):
        """The defect this file exists for. Both claims share every term with the
        truth, and a reversed mechanism is wrong, not approximately right."""
        reversed_claims = ["KRAS upregulates EGFR", "drug resistance drives KRAS"]
        assert acc.calculate(reversed_claims, TRUTH).value < 1.0

    def test_reversed_scores_strictly_worse_than_correct(self, acc):
        reversed_claims = ["KRAS upregulates EGFR", "drug resistance drives KRAS"]
        assert (
            acc.calculate(reversed_claims, TRUTH).value
            < acc.calculate(TRUTH, TRUTH).value
        )

    def test_elaboration_in_the_same_direction_still_matches(self, acc):
        """Direction-awareness must not become brittleness: extra words are fine
        as long as the orientation holds."""
        elaborated = [
            "EGFR strongly upregulates KRAS in tumours",
            "KRAS drives drug resistance to erlotinib",
        ]
        assert acc.calculate(elaborated, TRUTH).value == pytest.approx(1.0)


class TestAccuracyIsBounded:
    def test_never_exceeds_one(self, acc):
        padded = [f"EGFR upregulates KRAS variant {i}" for i in range(5)]
        assert acc.calculate(padded, TRUTH).value <= 1.0

    def test_padding_does_not_raise_the_score(self, acc):
        """Restating one truth many ways must not beat stating it once. A scorer
        that pays for verbosity trains exactly the wrong behaviour."""
        once = acc.calculate(["EGFR upregulates KRAS"], TRUTH).value
        many = acc.calculate(
            [f"EGFR upregulates KRAS restatement {i}" for i in range(5)], TRUTH
        ).value
        assert many == pytest.approx(once)

    def test_each_ground_truth_counts_at_most_once(self, acc):
        result = acc.calculate(
            ["EGFR upregulates KRAS", "EGFR upregulates KRAS again"], TRUTH
        )
        assert result.details["correct"] == 1

    def test_more_predictions_than_truths_stays_in_range(self, acc):
        noisy = TRUTH + ["TP53 upregulates MDM2", "MDM2 drives apoptosis"]
        assert 0.0 <= acc.calculate(noisy, TRUTH).value <= 1.0


class TestHallucinationHonesty:
    def test_no_reference_vocabulary_reports_not_measured(self):
        """Constructed the way the harness constructs it."""
        result = HallucinationDetector().calculate(
            claims=[],
            mentioned_genes=["ZORPX1", "FLUBBIN3"],
            mentioned_pathways=["Imaginary signalling"],
        )
        assert result.value is None
        assert result.measured is False
        assert "not measured" in result.details["note"]

    def test_invented_genes_are_caught_when_a_vocabulary_is_supplied(self):
        result = HallucinationDetector(known_genes={"EGFR", "KRAS"}).calculate(
            claims=[],
            mentioned_genes=["EGFR", "ZORPX1", "FLUBBIN3"],
            mentioned_pathways=[],
        )
        assert result.measured is True
        assert result.value > 0.0, "invented symbols went unreported"

    def test_a_real_gene_list_reports_no_hallucinations(self):
        result = HallucinationDetector(known_genes={"EGFR", "KRAS"}).calculate(
            claims=[], mentioned_genes=["EGFR", "KRAS"], mentioned_pathways=[]
        )
        assert result.value == pytest.approx(0.0)


class TestUnmeasuredMetricsAreVisible:
    def test_normalized_and_percentage_are_none_when_unmeasured(self):
        unmeasured = MetricResult(name="x", value=None)
        assert unmeasured.normalized is None
        assert unmeasured.percentage is None

    def test_overall_score_ignores_unmeasured_metrics(self):
        """An unmeasured metric must not be scored as a zero, which for an
        inverted metric like hallucination_rate would read as perfect."""
        metrics = BenchmarkMetrics(
            accuracy=MetricResult(name="accuracy", value=0.5),
            hallucination_rate=MetricResult(name="hallucination_rate", value=None),
        )
        assert metrics.overall_score == pytest.approx(0.5)

    def test_weight_coverage_reports_partial_measurement(self):
        metrics = BenchmarkMetrics(accuracy=MetricResult(name="accuracy", value=1.0))
        assert metrics.weight_coverage == pytest.approx(
            BenchmarkMetrics._WEIGHTS["accuracy"]
        )

    def test_weight_coverage_is_one_when_everything_is_measured(self):
        metrics = BenchmarkMetrics(
            **{
                name: MetricResult(name=name, value=0.5)
                for name in BenchmarkMetrics._WEIGHTS
            }
        )
        assert metrics.weight_coverage == pytest.approx(1.0)

    def test_the_weighting_itself_sums_to_one(self):
        """weight_coverage divides by this sum, so drift here silently rescales
        every published coverage figure."""
        assert sum(BenchmarkMetrics._WEIGHTS.values()) == pytest.approx(1.0)


class TestASynthenticScoreCannotBeQuoted:
    """The bundled suite is 25 synthetic tasks and 6 grounded in real papers, and the
    CLI's default registers all of them — so an unqualified default score is ~80%
    self-consistency against invented ground truth. That is the shape of number most
    likely to end up in a README, which is exactly what the repo's rule against
    presenting synthetic output as a real result forbids."""

    def _report(self, task_ids):
        from datetime import datetime

        from quration.benchmarks.harness import HarnessReport

        class _Result:
            def __init__(self, task_id):
                self.task_id = task_id

            def to_dict(self):
                return {"task_id": self.task_id}

        return HarnessReport(
            run_id="r",
            started_at=datetime(2026, 1, 1),
            results=[_Result(t) for t in task_ids],
            aggregate_metrics=BenchmarkMetrics(
                accuracy=MetricResult(name="accuracy", value=0.8)
            ),
        )

    def test_a_mixed_run_is_not_publishable(self):
        report = self._report(["deg-synthetic-001", "pub-deg-001"])
        assert report.synthetic_task_count == 1
        assert report.is_publishable_number is False

    def test_a_published_only_run_is_publishable(self):
        report = self._report(["pub-deg-001", "pub-pathway-001"])
        assert report.synthetic_task_count == 0
        assert report.is_publishable_number is True

    def test_an_empty_run_is_not_publishable(self):
        assert self._report([]).is_publishable_number is False

    def test_the_flag_is_serialised_alongside_the_score(self):
        """So a consumer reading the JSON cannot take the score without the caveat."""
        payload = self._report(["deg-synthetic-001"]).to_dict()
        assert payload["is_publishable_number"] is False
        assert payload["synthetic_task_count"] == 1


class TestFailedTasksDoNotDiluteQualityMetrics:
    """Run 20260809_075144: pub-pathway-002 died in the provider (exit 1,
    zero tokens, no interpretation ever produced). Its zeroed metrics were
    averaged into the aggregates anyway, so the reported claim recall of
    0.586 measured a blend of model quality and infrastructure uptime — the
    five tasks that actually completed scored 0.703. A failure is already
    counted in `failed_tasks`; it must not also masquerade as a maximally
    bad interpretation inside the quality numbers.
    """

    def test_aggregate_averages_only_completed_tasks(self):
        from quration.benchmarks.harness import EvaluationHarness
        from quration.benchmarks.tasks.base import BenchmarkResult

        completed = BenchmarkResult(
            task_id="t-good",
            task_name="t",
            task_type="deg_analysis",
            success=True,
            metrics=BenchmarkMetrics(
                accuracy=MetricResult(name="accuracy", value=0.8),
                claim_recall=MetricResult(name="claim_recall", value=1.0),
            ),
        )
        crashed = BenchmarkResult(
            task_id="t-dead",
            task_name="t",
            task_type="deg_analysis",
            success=False,
            error="claude -p exited 1",
            metrics=BenchmarkMetrics(
                accuracy=MetricResult(name="accuracy", value=0.0),
                claim_recall=MetricResult(name="claim_recall", value=0.0),
            ),
        )
        # __new__: _aggregate_metrics is pure, and constructing the full
        # harness registers tools globally — a second construction in the
        # same process raises "already registered".
        harness = EvaluationHarness.__new__(EvaluationHarness)
        aggregate = harness._aggregate_metrics([completed, crashed])
        assert aggregate.accuracy.value == pytest.approx(0.8)
        assert aggregate.claim_recall.value == pytest.approx(1.0)
        assert aggregate.accuracy.details["sample_count"] == 1

    def test_all_tasks_failed_aggregates_nothing(self):
        from quration.benchmarks.harness import EvaluationHarness
        from quration.benchmarks.tasks.base import BenchmarkResult

        crashed = BenchmarkResult(
            task_id="t-dead",
            task_name="t",
            task_type="deg_analysis",
            success=False,
            error="provider down",
            metrics=BenchmarkMetrics(
                accuracy=MetricResult(name="accuracy", value=0.0),
            ),
        )
        harness = EvaluationHarness.__new__(EvaluationHarness)
        aggregate = harness._aggregate_metrics([crashed])
        assert aggregate.accuracy is None
