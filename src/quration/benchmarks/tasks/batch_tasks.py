"""Batch effect assessment benchmark tasks.

Synthetic test cases for batch effect interpretation.
"""

from datetime import datetime
from typing import Any

from quration.benchmarks.metrics import BenchmarkMetrics
from quration.benchmarks.tasks.base import (
    BenchmarkInput,
    BenchmarkResult,
    BenchmarkTask,
    ExpectedOutput,
)


class BatchEffectBenchmarkTask(BenchmarkTask):
    """Base class for batch effect benchmark tasks."""

    def __init__(
        self,
        task_id: str,
        task_name: str,
        batch_count: int,
        batch_metrics: str,
        samples_per_batch: str,
        pca_summary: str,
        expected_claims: list[str],
        expected_severity: str,
        correction_recommended: bool,
        recommended_method: str | None = None,
        description: str = "",
        tags: list[str] | None = None,
    ):
        """Initialize batch effect benchmark task.

        Args:
            task_id: Task identifier
            task_name: Task name
            batch_count: Number of batches
            batch_metrics: Description of batch effect metrics
            samples_per_batch: Sample distribution
            pca_summary: PCA analysis summary
            expected_claims: Expected claims
            expected_severity: Expected severity (none, low, medium, high)
            correction_recommended: Whether correction should be recommended
            recommended_method: Expected correction method
            description: Task description
            tags: Task tags
        """
        super().__init__(
            task_id=task_id,
            task_name=task_name,
            task_type="batch_effect",
            description=description,
            tags=tags or ["batch", "synthetic"],
        )
        self._batch_count = batch_count
        self._batch_metrics = batch_metrics
        self._samples_per_batch = samples_per_batch
        self._pca_summary = pca_summary
        self._expected_claims = expected_claims
        self._expected_severity = expected_severity
        self._correction_recommended = correction_recommended
        self._recommended_method = recommended_method

    def get_input(self) -> BenchmarkInput:
        return BenchmarkInput(
            task_type="batch_effect",
            data={
                "batch_count": self._batch_count,
                "batch_metrics": self._batch_metrics,
                "samples_per_batch": self._samples_per_batch,
                "pca_summary": self._pca_summary,
            },
        )

    def get_expected_output(self) -> ExpectedOutput:
        return ExpectedOutput(
            claims=self._expected_claims,
            aspects=[
                "severity_assessment",
                "confounding_check",
                "correction_recommendation",
            ],
            custom_validations={
                "severity": self._expected_severity,
                "correction_recommended": self._correction_recommended,
                "recommended_method": self._recommended_method,
            },
        )

    async def run(self, service: Any) -> BenchmarkResult:
        """Run the batch effect assessment benchmark."""
        start_time = datetime.utcnow()

        try:
            result = await service.assess_batch_effects(
                batch_count=self._batch_count,
                batch_metrics=self._batch_metrics,
                samples_per_batch=self._samples_per_batch,
                pca_summary=self._pca_summary,
                max_iterations=5,
            )

            claims_extracted = [claim.statement for claim in result.claims]
            tool_calls = [
                {
                    "tool_name": tc.tool_name,
                    "status": tc.status.value,
                    "latency_ms": tc.latency_ms,
                    "cached": tc.cached,
                }
                for tc in result.tool_calls
            ]

            return BenchmarkResult(
                task_id=self.task_id,
                task_name=self.task_name,
                task_type=self.task_type,
                success=not result.failed,
                error=result.error,
                metrics=BenchmarkMetrics(),
                interpretation_id=result.id,
                interpretation_summary=result.summary,
                claims_extracted=claims_extracted,
                tool_calls_made=tool_calls,
                processing_time_ms=result.processing_time_ms,
                cost_usd=result.cost_usd,
                metadata={
                    "expected_severity": self._expected_severity,
                    "correction_recommended": self._correction_recommended,
                },
            )

        except Exception as e:
            return BenchmarkResult(
                task_id=self.task_id,
                task_name=self.task_name,
                task_type=self.task_type,
                success=False,
                metrics=BenchmarkMetrics(),
                error=str(e),
                processing_time_ms=(datetime.utcnow() - start_time).total_seconds() * 1000,
            )


# ============================================================================
# Synthetic Test Cases
# ============================================================================


def batch_obvious_confounding() -> BatchEffectBenchmarkTask:
    """Case 1: Obvious confounding batch effect.

    Batch perfectly correlates with treatment.
    Should identify and warn about confounding.
    """
    return BatchEffectBenchmarkTask(
        task_id="batch-synthetic-001",
        task_name="Obvious Confounding",
        batch_count=2,
        batch_metrics=(
            "PC1 explains 45% variance, perfectly separates batches. "
            "Silhouette score by batch: 0.92. "
            "PVCA analysis: Batch explains 45% variance, Treatment explains 44%."
        ),
        samples_per_batch="Batch1: 20 samples (all treated), Batch2: 20 samples (all control)",
        pca_summary=(
            "PC1 separates samples by batch (and treatment). "
            "PC2 shows no meaningful structure. "
            "Treatment and batch are completely confounded."
        ),
        expected_claims=[
            "Batch effect is severely confounding",
            "Cannot separate batch from treatment effect",
            "Results will be uninterpretable",
            "Study design issue - recommend repeating with balanced design",
        ],
        expected_severity="high",
        correction_recommended=False,
        recommended_method=None,
        description="Perfect confounding - batch = treatment. Should recommend new study.",
        tags=["batch", "synthetic", "confounded", "high_severity"],
    )


def batch_subtle_correctable() -> BatchEffectBenchmarkTask:
    """Case 2: Subtle but correctable batch effect.

    Moderate batch effect that can be corrected with ComBat.
    """
    return BatchEffectBenchmarkTask(
        task_id="batch-synthetic-002",
        task_name="Subtle Correctable",
        batch_count=3,
        batch_metrics=(
            "PC1 explains 28% variance (treatment-related). "
            "PC2 explains 15% variance (batch-related). "
            "PVCA: Treatment 30%, Batch 12%, Residual 58%."
        ),
        samples_per_batch=(
            "Batch1: 15 samples (8 treated, 7 control), "
            "Batch2: 18 samples (9 treated, 9 control), "
            "Batch3: 12 samples (6 treated, 6 control)"
        ),
        pca_summary=(
            "PC1 separates treatment groups with some overlap. "
            "PC2 shows batch clustering but treatment groups are balanced within batches. "
            "Batches are balanced for treatment assignment."
        ),
        expected_claims=[
            "Moderate batch effect detected",
            "Batch is not confounded with treatment",
            "Batch correction is recommended",
            "ComBat or similar methods should be effective",
        ],
        expected_severity="medium",
        correction_recommended=True,
        recommended_method="ComBat",
        description="Correctable batch effect with balanced design",
        tags=["batch", "synthetic", "correctable", "medium_severity"],
    )


def batch_none_present() -> BatchEffectBenchmarkTask:
    """Case 3: No batch effect present.

    Well-designed study with minimal batch effects.
    """
    return BatchEffectBenchmarkTask(
        task_id="batch-synthetic-003",
        task_name="No Batch Effect",
        batch_count=3,
        batch_metrics=(
            "PC1 explains 35% variance (treatment-related). "
            "PC2 explains 12% variance (biological variation). "
            "PVCA: Treatment 40%, Batch 2%, Residual 58%."
        ),
        samples_per_batch=(
            "Batch1: 15 samples (7 treated, 8 control), "
            "Batch2: 15 samples (8 treated, 7 control), "
            "Batch3: 15 samples (7 treated, 8 control)"
        ),
        pca_summary=(
            "PC1 clearly separates treatment from control. "
            "No clustering by batch in any component. "
            "Samples from all batches intermixed."
        ),
        expected_claims=[
            "No significant batch effect detected",
            "Treatment effect is dominant",
            "Batch correction not necessary",
            "Data quality is good",
        ],
        expected_severity="none",
        correction_recommended=False,
        recommended_method=None,
        description="Well-designed study with no batch effect",
        tags=["batch", "synthetic", "no_effect", "low_severity"],
    )


def batch_technical_variation() -> BatchEffectBenchmarkTask:
    """Additional case: Technical batch with different sequencing depths.

    Batch effect due to sequencing depth differences.
    """
    return BatchEffectBenchmarkTask(
        task_id="batch-synthetic-004",
        task_name="Sequencing Depth Batch",
        batch_count=2,
        batch_metrics=(
            "PC1 explains 25% variance. "
            "Library size differs significantly between batches. "
            "Batch1 mean depth: 30M reads, Batch2 mean depth: 60M reads."
        ),
        samples_per_batch=(
            "Batch1: 20 samples (10 treated, 10 control), "
            "Batch2: 20 samples (10 treated, 10 control)"
        ),
        pca_summary=(
            "PC1 shows partial batch separation. "
            "Treatment groups cluster together within batches. "
            "Library size correlates with PC1."
        ),
        expected_claims=[
            "Technical batch effect from sequencing depth",
            "Library size normalization required",
            "Treatment design is balanced",
            "TMM or RLE normalization recommended",
        ],
        expected_severity="medium",
        correction_recommended=True,
        recommended_method="Library size normalization",
        description="Sequencing depth batch effect",
        tags=["batch", "synthetic", "technical", "depth"],
    )


def batch_time_effect() -> BatchEffectBenchmarkTask:
    """Additional case: Time-based batch effect.

    Samples processed at different times with drift.
    """
    return BatchEffectBenchmarkTask(
        task_id="batch-synthetic-005",
        task_name="Time-Based Drift",
        batch_count=4,
        batch_metrics=(
            "Processing dates: Week 1, Week 3, Week 5, Week 8. "
            "Progressive drift in expression levels. "
            "PVCA: Time 18%, Treatment 25%, Residual 57%."
        ),
        samples_per_batch=(
            "Week1: 10 samples (5T/5C), "
            "Week3: 10 samples (5T/5C), "
            "Week5: 10 samples (5T/5C), "
            "Week8: 10 samples (5T/5C)"
        ),
        pca_summary=(
            "PC3 shows time progression. "
            "Treatment effect visible in PC1. "
            "Time batches show progressive shift."
        ),
        expected_claims=[
            "Time-dependent batch effect detected",
            "Progressive drift in expression",
            "Treatment design is balanced across time",
            "Consider time as covariate in model",
        ],
        expected_severity="medium",
        correction_recommended=True,
        recommended_method="Include time as covariate",
        description="Time-based progressive batch effect",
        tags=["batch", "synthetic", "temporal", "drift"],
    )


def get_all_batch_tasks() -> list[BatchEffectBenchmarkTask]:
    """Get all batch effect benchmark tasks.

    Returns:
        List of batch effect benchmark tasks
    """
    return [
        batch_obvious_confounding(),
        batch_subtle_correctable(),
        batch_none_present(),
        batch_technical_variation(),
        batch_time_effect(),
    ]
