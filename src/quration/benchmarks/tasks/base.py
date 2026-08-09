"""Base classes for benchmark tasks.

This module provides the abstract base class for all benchmark tasks.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from quration.benchmarks.metrics import BenchmarkMetrics


@dataclass
class BenchmarkInput:
    """Input data for a benchmark task."""

    task_type: str
    data: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExpectedOutput:
    """Expected output for validation."""

    claims: list[str] = field(default_factory=list)
    genes: list[str] = field(default_factory=list)
    pathways: list[str] = field(default_factory=list)
    aspects: list[str] = field(default_factory=list)
    min_confidence: float = 0.5
    expected_tools: list[str] = field(default_factory=list)
    custom_validations: dict[str, Any] = field(default_factory=dict)
    # What the task's inputs genuinely do NOT establish. A report earns
    # limitation-recognition credit for carrying each of these through to its
    # conclusions — calibrated refusal scored as the success it is.
    limitations: list[str] = field(default_factory=list)


@dataclass
class BenchmarkResult:
    """Result of running a benchmark task."""

    task_id: str
    task_name: str
    task_type: str
    success: bool
    metrics: BenchmarkMetrics
    interpretation_id: UUID | None = None
    interpretation_summary: str = ""
    claims_extracted: list[str] = field(default_factory=list)
    tool_calls_made: list[dict[str, Any]] = field(default_factory=list)
    processing_time_ms: float = 0.0
    cost_usd: float = 0.0
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_id": self.task_id,
            "task_name": self.task_name,
            "task_type": self.task_type,
            "success": self.success,
            "metrics": self.metrics.to_dict(),
            "interpretation_id": str(self.interpretation_id) if self.interpretation_id else None,
            "interpretation_summary": self.interpretation_summary,
            "claims_extracted": self.claims_extracted,
            "tool_calls_count": len(self.tool_calls_made),
            "processing_time_ms": self.processing_time_ms,
            "cost_usd": self.cost_usd,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class BenchmarkTask(ABC):
    """Abstract base class for benchmark tasks.

    Each benchmark task defines:
    - Input data and parameters
    - Expected output for validation
    - How to run the interpretation
    - How to evaluate the results

    Example:
        ```python
        class MyBenchmarkTask(BenchmarkTask):
            def __init__(self):
                super().__init__(
                    task_id="my-task-001",
                    task_name="My Benchmark Task",
                    task_type="custom",
                )

            def get_input(self) -> BenchmarkInput:
                return BenchmarkInput(
                    task_type="custom",
                    data={"prompt": "Analyze these genes..."},
                )

            def get_expected_output(self) -> ExpectedOutput:
                return ExpectedOutput(
                    claims=["Claim 1", "Claim 2"],
                    genes=["TP53", "BRCA1"],
                )

            async def run(self, service) -> BenchmarkResult:
                # Run interpretation and evaluate
                ...
        ```
    """

    def __init__(
        self,
        task_id: str,
        task_name: str,
        task_type: str,
        description: str = "",
        tags: list[str] | None = None,
    ):
        """Initialize benchmark task.

        Args:
            task_id: Unique task identifier
            task_name: Human-readable task name
            task_type: Task type (deg_analysis, pathway, etc.)
            description: Task description
            tags: Tags for filtering/grouping
        """
        self.task_id = task_id
        self.task_name = task_name
        self.task_type = task_type
        self.description = description
        self.tags = tags or []

    @abstractmethod
    def get_input(self) -> BenchmarkInput:
        """Get the input data for this benchmark.

        Returns:
            BenchmarkInput with task data
        """
        pass

    @abstractmethod
    def get_expected_output(self) -> ExpectedOutput:
        """Get the expected output for validation.

        Returns:
            ExpectedOutput with expected claims, genes, etc.
        """
        pass

    @abstractmethod
    async def run(self, service: Any) -> BenchmarkResult:
        """Run the benchmark task.

        Args:
            service: InterpretationService or InterpretationAPIService

        Returns:
            BenchmarkResult with metrics
        """
        pass

    def validate(self, result: BenchmarkResult) -> bool:
        """Validate if result meets minimum quality standards.

        Args:
            result: Benchmark result

        Returns:
            True if result is acceptable
        """
        if not result.success:
            return False

        # Check minimum confidence
        expected = self.get_expected_output()
        if result.metrics.accuracy and result.metrics.accuracy.normalized < 0.3:
            return False

        # Check hallucination rate
        if result.metrics.hallucination_rate and result.metrics.hallucination_rate.value > 0.5:
            return False

        return True

    def __str__(self) -> str:
        return f"{self.task_type}:{self.task_id} - {self.task_name}"

    def __repr__(self) -> str:
        return f"BenchmarkTask(id={self.task_id}, type={self.task_type})"


class SyntheticBenchmarkTask(BenchmarkTask):
    """Benchmark task with synthetic (generated) data.

    Synthetic tasks have known ground truth and are used for
    testing specific capabilities.
    """

    def __init__(
        self,
        task_id: str,
        task_name: str,
        task_type: str,
        input_data: dict[str, Any],
        expected_claims: list[str],
        expected_genes: list[str] | None = None,
        expected_pathways: list[str] | None = None,
        description: str = "",
        tags: list[str] | None = None,
    ):
        """Initialize synthetic benchmark task.

        Args:
            task_id: Task identifier
            task_name: Task name
            task_type: Task type
            input_data: Input data dict
            expected_claims: Expected claims
            expected_genes: Expected genes
            expected_pathways: Expected pathways
            description: Task description
            tags: Task tags
        """
        super().__init__(task_id, task_name, task_type, description, tags)
        self._input_data = input_data
        self._expected_claims = expected_claims
        self._expected_genes = expected_genes or []
        self._expected_pathways = expected_pathways or []

    def get_input(self) -> BenchmarkInput:
        return BenchmarkInput(
            task_type=self.task_type,
            data=self._input_data,
            metadata={"synthetic": True},
        )

    def get_expected_output(self) -> ExpectedOutput:
        return ExpectedOutput(
            claims=self._expected_claims,
            genes=self._expected_genes,
            pathways=self._expected_pathways,
        )


class PublishedBenchmarkTask(BenchmarkTask):
    """Benchmark task based on published research.

    These tasks reproduce analysis from published papers to
    validate interpretation quality against peer-reviewed results.
    """

    def __init__(
        self,
        task_id: str,
        task_name: str,
        task_type: str,
        paper_doi: str,
        paper_title: str,
        paper_year: int,
        paper_citation: str | None = None,
        paper_pmid: str | None = None,
        dataset_id: str | None = None,
        description: str = "",
        tags: list[str] | None = None,
    ):
        """Initialize published benchmark task.

        Args:
            task_id: Task identifier
            task_name: Task name
            task_type: Task type
            paper_doi: Paper DOI
            paper_title: Paper title
            paper_year: Publication year
            paper_citation: Paper citation string (auto-generated if not provided)
            paper_pmid: Paper PMID
            dataset_id: Associated dataset (e.g., GSE ID)
            description: Task description
            tags: Task tags
        """
        super().__init__(task_id, task_name, task_type, description, tags)
        self.paper_doi = paper_doi
        self.paper_title = paper_title
        self.paper_year = paper_year
        self.paper_citation = paper_citation or f"{paper_title} ({paper_year}). DOI: {paper_doi}"
        self.paper_pmid = paper_pmid
        self.dataset_id = dataset_id
