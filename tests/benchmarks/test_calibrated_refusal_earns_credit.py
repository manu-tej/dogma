"""Flagging a real gap in the inputs must earn credit, not score zero.

The first honest `--published` run scored 0.046 — and reading the transcripts
showed the model doing exactly what this repo argues for: refusing to call
genes significant without adjusted p-values, flagging pseudoreplication,
declining to name a KEGG pathway it could not confirm. The scorer counted all
of that as failure, because ground truth held only flat assertions. A
benchmark that punishes calibrated refusal is optimizing for the confident
fabrication the epistemics layer exists to prevent.

`ExpectedOutput.limitations` declares what a task's inputs genuinely do not
establish, and `LimitationRecognitionCalculator` credits a report for carrying
each declared limit through to its conclusions. It is recall-shaped: the score
is the fraction of declared limitations the report flagged, and a task that
declares none is not measured rather than free-perfect.
"""

import pytest

from quration.benchmarks.metrics import (
    BenchmarkMetrics,
    LimitationRecognitionCalculator,
    MetricResult,
)

LIMITS = [
    "per-gene adjusted p-values were not provided",
    "fold-change magnitudes are representative values, not measured table entries",
]


@pytest.fixture
def calc() -> LimitationRecognitionCalculator:
    return LimitationRecognitionCalculator()


class TestRecognisedLimitationsScore:
    def test_a_report_that_flags_every_declared_limit_scores_one(self, calc):
        report = (
            "The signature is coherent. However, per-gene adjusted p-values "
            "were not provided, so no individual gene is called significant. "
            "The fold-change magnitudes are representative values rather than "
            "measured table entries and are not treated as measurements."
        )
        assert calc.calculate(report, LIMITS).normalized == pytest.approx(1.0)

    def test_a_report_that_ignores_the_limits_scores_zero(self, calc):
        report = (
            "ESR1 and GATA3 are significantly upregulated. The luminal "
            "signature is unambiguous and the effect sizes are definitive."
        )
        assert calc.calculate(report, LIMITS).normalized == pytest.approx(0.0)

    def test_paraphrase_still_counts(self, calc):
        """The model will not quote the task definition back verbatim."""
        report = (
            "No adjusted p-values were supplied for any gene, so despite the "
            "large fold changes I treat this as an unfiltered candidate list."
        )
        result = calc.calculate(report, LIMITS)
        assert result.normalized >= 0.5

    def test_partial_recognition_scores_partially(self, calc):
        report = "Note that per-gene adjusted p-values were not provided."
        assert 0.0 < calc.calculate(report, LIMITS).normalized < 1.0

    def test_details_name_what_was_missed(self, calc):
        result = calc.calculate("All genes look significant to me.", LIMITS)
        assert result.details["missed"] == LIMITS


class TestNoDeclaredLimitsMeansNotMeasured:
    def test_empty_limitations_is_not_measured(self, calc):
        """No declared limits must read as "not measured", never as a free
        1.0 — the same rule `HallucinationDetector` follows with no
        vocabulary."""
        result = calc.calculate("Any report text.", [])
        assert result.measured is False
        assert result.normalized is None


class TestTheMetricCarriesWeight:
    def test_limitation_recognition_participates_in_the_overall_score(self):
        metrics = BenchmarkMetrics(
            limitation_recognition=MetricResult(
                name="limitation_recognition", value=1.0
            )
        )
        assert metrics.overall_score > 0.0

    def test_weight_coverage_counts_it(self):
        with_it = BenchmarkMetrics(
            limitation_recognition=MetricResult(
                name="limitation_recognition", value=1.0
            )
        )
        assert with_it.weight_coverage > 0.0

    def test_weights_still_sum_to_one(self):
        """Adding a metric must rebalance, not inflate — a full-coverage run
        should still normalise over exactly 1.0 of weight."""
        full = BenchmarkMetrics(
            accuracy=MetricResult(name="accuracy", value=1.0),
            completeness=MetricResult(name="completeness", value=1.0),
            citation_validity=MetricResult(name="citation_validity", value=1.0),
            hallucination_rate=MetricResult(name="hallucination_rate", value=0.0),
            claim_precision=MetricResult(name="claim_precision", value=1.0),
            claim_recall=MetricResult(name="claim_recall", value=1.0),
            confidence_calibration=MetricResult(
                name="confidence_calibration", value=1.0
            ),
            limitation_recognition=MetricResult(
                name="limitation_recognition", value=1.0
            ),
        )
        assert full.weight_coverage == pytest.approx(1.0)
        assert full.overall_score == pytest.approx(1.0)

    def test_it_serialises(self):
        metrics = BenchmarkMetrics(
            limitation_recognition=MetricResult(
                name="limitation_recognition", value=0.5
            )
        )
        assert "limitation_recognition" in metrics.to_dict()
