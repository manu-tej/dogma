"""Benchmark framework for interpretation evaluation.

This module provides tools for evaluating interpretation quality
using synthetic and published test cases.
"""

from quration.benchmarks.harness import (
    EvaluationHarness,
    HarnessConfig,
    HarnessReport,
    create_evaluation_harness,
)
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
from quration.benchmarks.tasks import (
    get_all_batch_tasks,
    get_all_deg_tasks,
    get_all_published_tasks,
    get_published_deg_tasks,
    get_published_pathway_tasks,
)
from quration.benchmarks.tasks.base import (
    BenchmarkInput,
    BenchmarkResult,
    BenchmarkTask,
    ExpectedOutput,
    PublishedBenchmarkTask,
    SyntheticBenchmarkTask,
)

__all__ = [
    # Harness
    "EvaluationHarness",
    "HarnessConfig",
    "HarnessReport",
    "create_evaluation_harness",
    # Metrics
    "MetricResult",
    "BenchmarkMetrics",
    "AccuracyCalculator",
    "CompletenessCalculator",
    "CitationValidityCalculator",
    "HallucinationDetector",
    "ClaimPrecisionRecallCalculator",
    "ConfidenceCalibrationCalculator",
    "ToolUtilizationCalculator",
    # Tasks
    "BenchmarkTask",
    "SyntheticBenchmarkTask",
    "PublishedBenchmarkTask",
    "BenchmarkInput",
    "BenchmarkResult",
    "ExpectedOutput",
    # Task factories
    "get_all_deg_tasks",
    "get_all_batch_tasks",
    "get_all_published_tasks",
    "get_published_deg_tasks",
    "get_published_pathway_tasks",
]
