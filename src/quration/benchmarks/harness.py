"""Evaluation harness for running interpretation benchmarks.

This module provides the main harness for executing benchmark tasks
and collecting metrics across multiple interpretations.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from quration.benchmarks.metrics import (
    AccuracyCalculator,
    BenchmarkMetrics,
    CitationValidityCalculator,
    ClaimPrecisionRecallCalculator,
    CompletenessCalculator,
    ConfidenceCalibrationCalculator,
    HallucinationDetector,
    MetricResult,
    ToolUtilizationCalculator,
)
from quration.benchmarks.tasks.base import BenchmarkResult, BenchmarkTask
from quration.interpretation.service import InterpretationService, create_interpretation_service

logger = logging.getLogger(__name__)


@dataclass
class HarnessConfig:
    """Configuration for the evaluation harness."""

    # Execution settings
    parallel_tasks: int = 1  # Number of parallel task executions
    max_retries: int = 2
    timeout_seconds: int = 300

    # Output settings
    output_dir: str = "benchmarks/results"
    save_detailed_results: bool = True

    # Comparison settings
    compare_models: list[str] = field(default_factory=list)

    # Filtering
    task_types: list[str] | None = None  # None = all types
    tags: list[str] | None = None


@dataclass
class HarnessReport:
    """Report from a benchmark run."""

    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    results: list[BenchmarkResult] = field(default_factory=list)
    aggregate_metrics: BenchmarkMetrics | None = None
    model_used: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_tasks == 0:
            return 0.0
        return self.successful_tasks / self.total_tasks

    @property
    def synthetic_task_count(self) -> int:
        """Tasks whose ground truth was invented rather than taken from a study.

        The bundled suite is 25 synthetic tasks (`*-synthetic-*`) and 6 grounded in
        real papers with DOIs. The CLI's default registers all of them, so a score
        from a default run is roughly 80% self-consistency against made-up data.
        That number must never be quoted as a benchmark result — see
        `is_publishable_number`. `--published` restricts the run to the real ones.
        """
        return sum(1 for r in self.results if "synthetic" in r.task_id.lower())

    @property
    def is_publishable_number(self) -> bool:
        """Whether the aggregate score is fit to be quoted anywhere external.

        False whenever any synthetic task contributed, or when no metric coverage
        exists. This is deliberately conservative: the repo's standing rule is that
        synthetic output is never presented as a real scientific result, and an
        aggregate score silently averaged over invented ground truth is exactly
        that, in the form most likely to end up in a README.
        """
        if self.synthetic_task_count > 0:
            return False
        if not self.results:
            return False
        return bool(self.aggregate_metrics and self.aggregate_metrics.weight_coverage > 0)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_tasks": self.total_tasks,
            "successful_tasks": self.successful_tasks,
            "failed_tasks": self.failed_tasks,
            "success_rate": self.success_rate,
            "synthetic_task_count": self.synthetic_task_count,
            "is_publishable_number": self.is_publishable_number,
            "aggregate_metrics": self.aggregate_metrics.to_dict() if self.aggregate_metrics else None,
            "model_used": self.model_used,
            "config": self.config,
            "errors": self.errors,
            "results": [r.to_dict() for r in self.results],
        }

    def save(self, path: Path | str) -> None:
        """Save report to JSON file.

        Args:
            path: Output path
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

        logger.info(f"Saved report to {path}")


class EvaluationHarness:
    """Main harness for running interpretation benchmarks.

    The harness:
    - Manages benchmark task execution
    - Collects and aggregates metrics
    - Supports model comparison
    - Saves detailed results

    Example:
        ```python
        harness = EvaluationHarness()

        # Register tasks
        harness.register_task(DEGBenchmarkTask(...))
        harness.register_task(PathwayBenchmarkTask(...))

        # Run benchmarks
        report = await harness.run()

        # Save results
        report.save("benchmark_results.json")
        ```
    """

    def __init__(
        self,
        config: HarnessConfig | None = None,
        service: InterpretationService | None = None,
    ):
        """Initialize the evaluation harness.

        Args:
            config: Harness configuration
            service: Interpretation service (creates default if not provided)
        """
        self.config = config or HarnessConfig()
        self._service = service or create_interpretation_service()
        self._tasks: list[BenchmarkTask] = []

        # Metric calculators
        self._accuracy_calc = AccuracyCalculator()
        self._completeness_calc = CompletenessCalculator()
        self._citation_calc = CitationValidityCalculator()
        self._hallucination_calc = HallucinationDetector()
        self._precision_recall_calc = ClaimPrecisionRecallCalculator()
        self._calibration_calc = ConfidenceCalibrationCalculator()
        self._tool_calc = ToolUtilizationCalculator()

    def register_task(self, task: BenchmarkTask) -> None:
        """Register a benchmark task.

        Args:
            task: Benchmark task to register
        """
        self._tasks.append(task)
        logger.debug(f"Registered benchmark task: {task}")

    def register_tasks(self, tasks: list[BenchmarkTask]) -> None:
        """Register multiple benchmark tasks.

        Args:
            tasks: List of tasks to register
        """
        for task in tasks:
            self.register_task(task)

    def clear_tasks(self) -> None:
        """Clear all registered tasks."""
        self._tasks.clear()

    def filter_tasks(
        self,
        task_types: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> list[BenchmarkTask]:
        """Filter registered tasks.

        Args:
            task_types: Filter by task types
            tags: Filter by tags (any match)

        Returns:
            Filtered list of tasks
        """
        tasks = self._tasks

        if task_types:
            tasks = [t for t in tasks if t.task_type in task_types]

        if tags:
            tag_set = set(tags)
            tasks = [t for t in tasks if set(t.tags) & tag_set]

        return tasks

    async def run(
        self,
        run_id: str | None = None,
    ) -> HarnessReport:
        """Run all registered benchmark tasks.

        Args:
            run_id: Optional run identifier

        Returns:
            HarnessReport with results
        """
        run_id = run_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        started_at = datetime.utcnow()

        logger.info(f"Starting benchmark run: {run_id}")

        # Filter tasks based on config
        tasks = self.filter_tasks(
            task_types=self.config.task_types,
            tags=self.config.tags,
        )

        if not tasks:
            logger.warning("No tasks to run")
            return HarnessReport(
                run_id=run_id,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                errors=["No tasks registered or all filtered out"],
            )

        logger.info(f"Running {len(tasks)} benchmark tasks")

        # Run tasks
        results: list[BenchmarkResult] = []
        errors: list[str] = []

        if self.config.parallel_tasks > 1:
            # Parallel execution
            semaphore = asyncio.Semaphore(self.config.parallel_tasks)

            async def run_with_semaphore(task: BenchmarkTask) -> BenchmarkResult | None:
                async with semaphore:
                    return await self._run_single_task(task)

            task_results = await asyncio.gather(
                *[run_with_semaphore(t) for t in tasks],
                return_exceptions=True,
            )

            for task, result in zip(tasks, task_results):
                if isinstance(result, Exception):
                    errors.append(f"{task.task_id}: {result}")
                elif result:
                    results.append(result)
        else:
            # Sequential execution
            for task in tasks:
                try:
                    result = await self._run_single_task(task)
                    if result:
                        results.append(result)
                except Exception as e:
                    errors.append(f"{task.task_id}: {e}")
                    logger.exception(f"Task {task.task_id} failed: {e}")

        # Aggregate metrics
        aggregate = self._aggregate_metrics(results)

        # Build report
        report = HarnessReport(
            run_id=run_id,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            total_tasks=len(tasks),
            successful_tasks=sum(1 for r in results if r.success),
            failed_tasks=sum(1 for r in results if not r.success),
            results=results,
            aggregate_metrics=aggregate,
            model_used=self._service._model,
            config={
                "parallel_tasks": self.config.parallel_tasks,
                "max_retries": self.config.max_retries,
                "task_types": self.config.task_types,
                "tags": self.config.tags,
            },
            errors=errors,
        )

        # Save results if configured
        if self.config.save_detailed_results:
            output_path = Path(self.config.output_dir) / f"benchmark_{run_id}.json"
            report.save(output_path)

        logger.info(
            f"Benchmark run complete: {report.successful_tasks}/{report.total_tasks} "
            f"successful, overall score: {report.aggregate_metrics.overall_score:.2f}"
            if report.aggregate_metrics
            else ""
        )

        return report

    async def _run_single_task(
        self,
        task: BenchmarkTask,
    ) -> BenchmarkResult | None:
        """Run a single benchmark task with retries.

        Args:
            task: Task to run

        Returns:
            BenchmarkResult or None if all retries failed
        """
        for attempt in range(self.config.max_retries + 1):
            try:
                logger.debug(f"Running task {task.task_id} (attempt {attempt + 1})")

                # Run with timeout
                result = await asyncio.wait_for(
                    task.run(self._service),
                    timeout=self.config.timeout_seconds,
                )

                # Calculate additional metrics
                result.metrics = self._calculate_task_metrics(task, result)

                return result

            except asyncio.TimeoutError:
                logger.warning(f"Task {task.task_id} timed out (attempt {attempt + 1})")
                if attempt == self.config.max_retries:
                    return BenchmarkResult(
                        task_id=task.task_id,
                        task_name=task.task_name,
                        task_type=task.task_type,
                        success=False,
                        metrics=BenchmarkMetrics(),
                        error=f"Timeout after {self.config.timeout_seconds}s",
                    )

            except Exception as e:
                logger.warning(f"Task {task.task_id} failed (attempt {attempt + 1}): {e}")
                if attempt == self.config.max_retries:
                    return BenchmarkResult(
                        task_id=task.task_id,
                        task_name=task.task_name,
                        task_type=task.task_type,
                        success=False,
                        metrics=BenchmarkMetrics(),
                        error=str(e),
                    )

        return None

    def _calculate_task_metrics(
        self,
        task: BenchmarkTask,
        result: BenchmarkResult,
    ) -> BenchmarkMetrics:
        """Calculate metrics for a task result.

        Args:
            task: Benchmark task
            result: Task result

        Returns:
            BenchmarkMetrics
        """
        expected = task.get_expected_output()
        metrics = result.metrics or BenchmarkMetrics()

        # Accuracy
        if expected.claims:
            metrics.accuracy = self._accuracy_calc.calculate(
                predicted_claims=result.claims_extracted,
                ground_truth_claims=expected.claims,
            )

        # Completeness
        if expected.aspects:
            metrics.completeness = self._completeness_calc.calculate(
                covered_aspects=result.claims_extracted,
                required_aspects=expected.aspects,
            )

        # Claim precision/recall
        if expected.claims:
            metrics.claim_precision = self._precision_recall_calc.calculate_precision(
                predicted_claims=result.claims_extracted,
                relevant_claims=expected.claims,
            )
            metrics.claim_recall = self._precision_recall_calc.calculate_recall(
                predicted_claims=result.claims_extracted,
                relevant_claims=expected.claims,
            )

        # Tool utilization
        if result.tool_calls_made:
            metrics.tool_utilization = self._tool_calc.calculate(
                tool_calls=result.tool_calls_made,
                expected_tools=expected.expected_tools,
            )

        return metrics

    def _aggregate_metrics(
        self,
        results: list[BenchmarkResult],
    ) -> BenchmarkMetrics:
        """Aggregate metrics across all results.

        Args:
            results: List of benchmark results

        Returns:
            Aggregated BenchmarkMetrics
        """
        if not results:
            return BenchmarkMetrics()

        # Collect individual metric values
        accuracy_values = []
        completeness_values = []
        citation_values = []
        hallucination_values = []
        precision_values = []
        recall_values = []
        tool_values = []
        calibration_values = []

        for r in results:
            if r.metrics.accuracy:
                accuracy_values.append(r.metrics.accuracy.normalized)
            if r.metrics.completeness:
                completeness_values.append(r.metrics.completeness.normalized)
            if r.metrics.citation_validity:
                citation_values.append(r.metrics.citation_validity.normalized)
            if r.metrics.hallucination_rate:
                hallucination_values.append(r.metrics.hallucination_rate.value)
            if r.metrics.claim_precision:
                precision_values.append(r.metrics.claim_precision.normalized)
            if r.metrics.claim_recall:
                recall_values.append(r.metrics.claim_recall.normalized)
            if r.metrics.tool_utilization:
                tool_values.append(r.metrics.tool_utilization.normalized)
            if r.metrics.confidence_calibration:
                calibration_values.append(r.metrics.confidence_calibration.normalized)

        # Calculate averages
        aggregate = BenchmarkMetrics()

        if accuracy_values:
            aggregate.accuracy = MetricResult(
                name="accuracy",
                value=sum(accuracy_values) / len(accuracy_values),
                details={"sample_count": len(accuracy_values)},
            )

        if completeness_values:
            aggregate.completeness = MetricResult(
                name="completeness",
                value=sum(completeness_values) / len(completeness_values),
                details={"sample_count": len(completeness_values)},
            )

        if citation_values:
            aggregate.citation_validity = MetricResult(
                name="citation_validity",
                value=sum(citation_values) / len(citation_values),
                details={"sample_count": len(citation_values)},
            )

        if hallucination_values:
            aggregate.hallucination_rate = MetricResult(
                name="hallucination_rate",
                value=sum(hallucination_values) / len(hallucination_values),
                details={"sample_count": len(hallucination_values)},
            )

        if precision_values:
            aggregate.claim_precision = MetricResult(
                name="claim_precision",
                value=sum(precision_values) / len(precision_values),
                details={"sample_count": len(precision_values)},
            )

        if recall_values:
            aggregate.claim_recall = MetricResult(
                name="claim_recall",
                value=sum(recall_values) / len(recall_values),
                details={"sample_count": len(recall_values)},
            )

        if tool_values:
            aggregate.tool_utilization = MetricResult(
                name="tool_utilization",
                value=sum(tool_values) / len(tool_values),
                details={"sample_count": len(tool_values)},
            )

        if calibration_values:
            aggregate.confidence_calibration = MetricResult(
                name="confidence_calibration",
                value=sum(calibration_values) / len(calibration_values),
                details={"sample_count": len(calibration_values)},
            )

        return aggregate

    async def compare_models(
        self,
        models: list[str],
        run_id: str | None = None,
    ) -> dict[str, HarnessReport]:
        """Run benchmarks with multiple models for comparison.

        Args:
            models: List of model identifiers
            run_id: Optional run identifier prefix

        Returns:
            Dict mapping model to HarnessReport
        """
        run_id = run_id or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        reports = {}

        for model in models:
            logger.info(f"Running benchmarks with model: {model}")

            # Create service with specific model
            service = create_interpretation_service(model=model)

            # Create harness copy with this service
            harness = EvaluationHarness(config=self.config, service=service)
            harness.register_tasks(self._tasks)

            # Run benchmarks
            model_run_id = f"{run_id}_{model.replace('/', '_')}"
            report = await harness.run(run_id=model_run_id)
            reports[model] = report

        return reports


def create_evaluation_harness(
    output_dir: str = "benchmarks/results",
    parallel_tasks: int = 1,
) -> EvaluationHarness:
    """Create a configured evaluation harness.

    Args:
        output_dir: Output directory for results
        parallel_tasks: Number of parallel tasks

    Returns:
        EvaluationHarness instance
    """
    config = HarnessConfig(
        output_dir=output_dir,
        parallel_tasks=parallel_tasks,
    )
    return EvaluationHarness(config=config)
