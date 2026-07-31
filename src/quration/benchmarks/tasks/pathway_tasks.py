"""Pathway enrichment benchmark tasks.

Synthetic test cases for pathway enrichment interpretation.
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


class PathwayEnrichmentBenchmarkTask(BenchmarkTask):
    """Base class for pathway enrichment benchmark tasks."""

    def __init__(
        self,
        task_id: str,
        task_name: str,
        pathways: list[dict],
        experiment_context: str,
        gene_set_size: int,
        expected_claims: list[str],
        expected_pathways: list[str] | None = None,
        expected_tools: list[str] | None = None,
        description: str = "",
        tags: list[str] | None = None,
    ):
        """Initialize pathway enrichment benchmark task.

        Args:
            task_id: Task identifier
            task_name: Task name
            pathways: List of pathway dicts with name, p_value, gene_count
            experiment_context: Description of experimental context
            gene_set_size: Total number of genes in the gene set
            expected_claims: Expected claims from interpretation
            expected_pathways: Expected pathways to identify
            expected_tools: Expected tools to be called
            description: Task description
            tags: Task tags
        """
        super().__init__(
            task_id=task_id,
            task_name=task_name,
            task_type="pathway_enrichment",
            description=description,
            tags=tags or ["pathway", "synthetic"],
        )
        self._pathways = pathways
        self._experiment_context = experiment_context
        self._gene_set_size = gene_set_size
        self._expected_claims = expected_claims
        self._expected_pathways = expected_pathways or []
        self._expected_tools = expected_tools or [
            "get_reactome_pathway",
            "search_pubmed",
            "get_kegg_pathway",
        ]

    def get_input(self) -> BenchmarkInput:
        return BenchmarkInput(
            task_type="pathway_enrichment",
            data={
                "pathways": self._pathways,
                "experiment_context": self._experiment_context,
                "gene_set_size": self._gene_set_size,
            },
        )

    def get_expected_output(self) -> ExpectedOutput:
        return ExpectedOutput(
            claims=self._expected_claims,
            pathways=self._expected_pathways,
            expected_tools=self._expected_tools,
        )

    async def run(self, service: Any) -> BenchmarkResult:
        """Run the pathway enrichment interpretation benchmark."""
        start_time = datetime.utcnow()

        try:
            result = await service.interpret_pathway_enrichment(
                pathways=self._pathways,
                experiment_context=self._experiment_context,
                gene_set_size=self._gene_set_size,
                max_iterations=10,
            )

            # Extract claims from result
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


def pathway_apoptosis() -> PathwayEnrichmentBenchmarkTask:
    """Case 1: Apoptosis pathways in drug-treated cancer cells.

    Strong apoptotic signal with p53-mediated cell death and caspase cascade.
    Tests interpretation of coherent cell death pathway activation.
    """
    return PathwayEnrichmentBenchmarkTask(
        task_id="pathway-synthetic-001",
        task_name="Apoptosis Pathways",
        pathways=[
            {"name": "Apoptosis", "p_value": 1e-8, "gene_count": 15},
            {"name": "p53 signaling pathway", "p_value": 5e-7, "gene_count": 12},
            {"name": "Caspase cascade", "p_value": 1e-5, "gene_count": 8},
        ],
        experiment_context="Drug-treated cancer cells showing apoptosis activation",
        gene_set_size=35,
        expected_claims=[
            "Apoptosis pathway activation",
            "p53-mediated cell death",
            "Caspase cascade engagement",
            "Drug-induced programmed cell death",
        ],
        expected_pathways=["Apoptosis", "p53 signaling pathway", "Caspase cascade"],
        description="Drug-treated cancer cells with strong apoptotic pathway enrichment",
        tags=["pathway", "synthetic", "strong_signal", "apoptosis", "cancer"],
    )


def pathway_immune_activation() -> PathwayEnrichmentBenchmarkTask:
    """Case 2: Immune activation pathways in viral infection.

    Multi-arm innate immune response with interferon, TNF, NF-kB, and TLR signaling.
    Tests interpretation of coordinated immune pathway activation.
    """
    return PathwayEnrichmentBenchmarkTask(
        task_id="pathway-synthetic-002",
        task_name="Immune Activation Pathways",
        pathways=[
            {"name": "Interferon signaling", "p_value": 1e-10, "gene_count": 20},
            {"name": "TNF signaling", "p_value": 1e-7, "gene_count": 14},
            {"name": "NF-kappa B signaling", "p_value": 5e-6, "gene_count": 11},
            {"name": "Toll-like receptor signaling", "p_value": 1e-5, "gene_count": 9},
        ],
        experiment_context="Viral infection immune response in PBMCs",
        gene_set_size=54,
        expected_claims=[
            "Interferon response activation",
            "TNF-mediated inflammation",
            "NF-kB pathway engagement",
            "Innate immune activation via TLR",
        ],
        expected_pathways=[
            "Interferon signaling",
            "TNF signaling",
            "NF-kappa B signaling",
            "Toll-like receptor signaling",
        ],
        description="Viral infection with multi-arm innate immune pathway activation",
        tags=["pathway", "synthetic", "strong_signal", "immune", "infection"],
    )


def pathway_metabolic_reprogramming() -> PathwayEnrichmentBenchmarkTask:
    """Case 3: Metabolic reprogramming in tumor vs normal tissue.

    Warburg effect and HIF-1 driven metabolic shift typical of cancer.
    Tests interpretation of metabolic pathway alterations.
    """
    return PathwayEnrichmentBenchmarkTask(
        task_id="pathway-synthetic-003",
        task_name="Metabolic Reprogramming",
        pathways=[
            {"name": "Glycolysis / Gluconeogenesis", "p_value": 1e-6, "gene_count": 10},
            {"name": "HIF-1 signaling pathway", "p_value": 5e-6, "gene_count": 9},
            {"name": "AMPK signaling pathway", "p_value": 1e-4, "gene_count": 7},
        ],
        experiment_context="Tumor vs normal tissue metabolic comparison",
        gene_set_size=26,
        expected_claims=[
            "Warburg effect / aerobic glycolysis",
            "HIF-1 driven metabolic adaptation",
            "AMPK energy sensing disruption",
            "Metabolic reprogramming in cancer",
        ],
        expected_pathways=["Glycolysis", "HIF-1 signaling", "AMPK signaling"],
        description="Tumor metabolic reprogramming with glycolysis and HIF-1 activation",
        tags=["pathway", "synthetic", "strong_signal", "metabolism", "cancer"],
    )


def pathway_marginal_enrichment() -> PathwayEnrichmentBenchmarkTask:
    """Case 4: Marginal enrichment with borderline significance.

    Low-dose drug treatment with minimal biological effect.
    Tests ability to recognize weak/non-significant pathway enrichment.
    """
    return PathwayEnrichmentBenchmarkTask(
        task_id="pathway-synthetic-004",
        task_name="Marginal Enrichment",
        pathways=[
            {"name": "Generic metabolism", "p_value": 0.04, "gene_count": 4},
            {"name": "Housekeeping pathways", "p_value": 0.03, "gene_count": 5},
        ],
        experiment_context="Low-dose drug treatment, minimal biological effect expected",
        gene_set_size=9,
        expected_claims=[
            "Borderline statistical significance",
            "No strong pathway activation",
            "Results should be interpreted with caution",
            "May represent noise",
        ],
        expected_pathways=[],
        description="Low-dose drug with marginal enrichment, likely noise",
        tags=["pathway", "synthetic", "weak_signal", "marginal"],
    )


def pathway_crosstalk_signaling() -> PathwayEnrichmentBenchmarkTask:
    """Case 5: Signaling pathway crosstalk in RAS-mutant cancer.

    Multiple interconnected oncogenic signaling pathways with extensive crosstalk.
    Tests interpretation of convergent signaling and pathway interactions.
    """
    return PathwayEnrichmentBenchmarkTask(
        task_id="pathway-synthetic-005",
        task_name="Crosstalk Signaling",
        pathways=[
            {"name": "PI3K-AKT signaling pathway", "p_value": 1e-9, "gene_count": 18},
            {"name": "MAPK/ERK signaling pathway", "p_value": 1e-8, "gene_count": 16},
            {"name": "mTOR signaling pathway", "p_value": 1e-6, "gene_count": 12},
            {"name": "RAS signaling pathway", "p_value": 1e-7, "gene_count": 14},
        ],
        experiment_context="RAS-mutant cancer cells showing signaling pathway crosstalk",
        gene_set_size=60,
        expected_claims=[
            "PI3K-AKT pathway activation",
            "MAPK/ERK cascade engagement",
            "mTOR pathway involvement",
            "RAS-driven signaling crosstalk",
            "Convergent oncogenic signaling",
        ],
        expected_pathways=[
            "PI3K-AKT signaling",
            "MAPK signaling",
            "mTOR signaling",
            "RAS signaling",
        ],
        description="RAS-mutant cancer with convergent oncogenic signaling crosstalk",
        tags=["pathway", "synthetic", "strong_signal", "signaling", "cancer"],
    )


def get_all_pathway_tasks() -> list[PathwayEnrichmentBenchmarkTask]:
    """Get all pathway enrichment benchmark tasks.

    Returns:
        List of pathway enrichment benchmark tasks
    """
    return [
        pathway_apoptosis(),
        pathway_immune_activation(),
        pathway_metabolic_reprogramming(),
        pathway_marginal_enrichment(),
        pathway_crosstalk_signaling(),
    ]
