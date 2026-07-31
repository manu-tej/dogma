"""DEG analysis benchmark tasks.

Synthetic test cases for differential expression interpretation.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from quration.benchmarks.metrics import BenchmarkMetrics
from quration.benchmarks.tasks.base import (
    BenchmarkInput,
    BenchmarkResult,
    BenchmarkTask,
    ExpectedOutput,
)


class DEGBenchmarkTask(BenchmarkTask):
    """Base class for DEG benchmark tasks."""

    def __init__(
        self,
        task_id: str,
        task_name: str,
        upregulated: list[tuple[str, float]],
        downregulated: list[tuple[str, float]],
        condition_a: str,
        condition_b: str,
        expected_claims: list[str],
        expected_genes: list[str] | None = None,
        expected_pathways: list[str] | None = None,
        organism: str = "human",
        experiment_type: str = "RNA-seq",
        description: str = "",
        tags: list[str] | None = None,
    ):
        """Initialize DEG benchmark task.

        Args:
            task_id: Task identifier
            task_name: Task name
            upregulated: List of (gene, log2fc) tuples
            downregulated: List of (gene, log2fc) tuples
            condition_a: First condition
            condition_b: Second condition
            expected_claims: Expected claims
            expected_genes: Expected genes to mention
            expected_pathways: Expected pathways to identify
            organism: Organism
            experiment_type: Experiment type
            description: Task description
            tags: Task tags
        """
        super().__init__(
            task_id=task_id,
            task_name=task_name,
            task_type="deg_analysis",
            description=description,
            tags=tags or ["deg", "synthetic"],
        )
        self._upregulated = upregulated
        self._downregulated = downregulated
        self._condition_a = condition_a
        self._condition_b = condition_b
        self._expected_claims = expected_claims
        self._expected_genes = expected_genes or []
        self._expected_pathways = expected_pathways or []
        self._organism = organism
        self._experiment_type = experiment_type

    def get_input(self) -> BenchmarkInput:
        return BenchmarkInput(
            task_type="deg_analysis",
            data={
                "upregulated": self._upregulated,
                "downregulated": self._downregulated,
                "condition_a": self._condition_a,
                "condition_b": self._condition_b,
                "organism": self._organism,
                "experiment_type": self._experiment_type,
            },
        )

    def get_expected_output(self) -> ExpectedOutput:
        return ExpectedOutput(
            claims=self._expected_claims,
            genes=self._expected_genes,
            pathways=self._expected_pathways,
            expected_tools=["get_gene_info", "search_pubmed", "get_reactome_pathway"],
        )

    async def run(self, service: Any) -> BenchmarkResult:
        """Run the DEG interpretation benchmark."""
        start_time = datetime.utcnow()

        try:
            result = await service.interpret_deg_results(
                upregulated=self._upregulated,
                downregulated=self._downregulated,
                condition_a=self._condition_a,
                condition_b=self._condition_b,
                organism=self._organism,
                experiment_type=self._experiment_type,
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


def deg_strong_signal_coherent() -> DEGBenchmarkTask:
    """Case 4: DEG with strong signal and coherent biology.

    Clear differential expression with well-known cancer genes.
    Tests basic interpretation capability.
    """
    return DEGBenchmarkTask(
        task_id="deg-synthetic-001",
        task_name="Strong Signal - p53/Cell Cycle",
        upregulated=[
            ("TP53", 3.2),
            ("CDKN1A", 2.8),  # p21
            ("BAX", 2.5),
            ("PUMA", 2.3),  # BBC3
            ("MDM2", 1.9),
            ("GADD45A", 1.8),
        ],
        downregulated=[
            ("CCND1", -2.1),  # Cyclin D1
            ("CDK4", -1.8),
            ("E2F1", -1.5),
            ("MYC", -1.9),
            ("PCNA", -1.4),
        ],
        condition_a="treated",
        condition_b="control",
        expected_claims=[
            "TP53 is significantly upregulated",
            "p53 signaling pathway is activated",
            "Cell cycle arrest genes are induced",
            "Pro-apoptotic genes are upregulated",
            "Cell cycle progression genes are downregulated",
        ],
        expected_genes=["TP53", "CDKN1A", "BAX", "MDM2", "CCND1", "MYC"],
        expected_pathways=["p53 signaling", "Cell cycle", "Apoptosis"],
        description="Strong p53 activation with coherent cell cycle arrest signature",
        tags=["deg", "synthetic", "strong_signal", "p53"],
    )


def deg_weak_signal_noisy() -> DEGBenchmarkTask:
    """Case 5: DEG with weak signal and noise.

    Borderline significant genes with less coherent biology.
    Tests robustness to noise.
    """
    return DEGBenchmarkTask(
        task_id="deg-synthetic-002",
        task_name="Weak Signal - Noisy Data",
        upregulated=[
            ("IL6", 1.2),
            ("CXCL8", 1.1),
            ("FOS", 0.9),
            ("ACTB", 0.8),  # Housekeeping - noise
            ("GAPDH", 0.7),  # Housekeeping - noise
        ],
        downregulated=[
            ("TUBB", -0.8),  # Housekeeping - noise
            ("TNF", -1.0),
            ("NFKB1", -0.9),
        ],
        condition_a="treated",
        condition_b="control",
        expected_claims=[
            "IL6 shows moderate upregulation",
            "Inflammatory response may be activated",
            "Signal is weak and should be interpreted with caution",
        ],
        expected_genes=["IL6", "CXCL8", "TNF"],
        expected_pathways=["Inflammatory response", "Cytokine signaling"],
        description="Weak inflammatory signal with housekeeping gene noise",
        tags=["deg", "synthetic", "weak_signal", "noisy"],
    )


def deg_no_signal() -> DEGBenchmarkTask:
    """Case 6: DEG with no significant signal.

    No biologically meaningful differential expression.
    Tests ability to report negative results.
    """
    return DEGBenchmarkTask(
        task_id="deg-synthetic-003",
        task_name="No Signal - Random Fluctuation",
        upregulated=[
            ("ACTB", 0.3),
            ("GAPDH", 0.2),
            ("TUBB", 0.25),
        ],
        downregulated=[
            ("18S", -0.2),
            ("RPS18", -0.15),
        ],
        condition_a="group_a",
        condition_b="group_b",
        expected_claims=[
            "No significant differential expression detected",
            "Changes are within normal variation",
            "Housekeeping genes show minimal changes",
        ],
        expected_genes=[],
        expected_pathways=[],
        description="No meaningful signal - should report negative result",
        tags=["deg", "synthetic", "no_signal", "negative"],
    )


def deg_immune_response() -> DEGBenchmarkTask:
    """Additional case: Strong immune response signature.

    Clear immune activation pattern.
    """
    return DEGBenchmarkTask(
        task_id="deg-synthetic-004",
        task_name="Immune Response Activation",
        upregulated=[
            ("IFNG", 4.5),
            ("TNF", 3.8),
            ("IL1B", 3.2),
            ("CXCL10", 3.0),
            ("CD8A", 2.8),
            ("GZMB", 2.5),
            ("PRF1", 2.3),
            ("STAT1", 2.0),
        ],
        downregulated=[
            ("IL10", -1.8),
            ("TGFB1", -1.5),
            ("FOXP3", -1.3),
        ],
        condition_a="infected",
        condition_b="healthy",
        expected_claims=[
            "Strong interferon-gamma response detected",
            "Cytotoxic T cell activation markers elevated",
            "Pro-inflammatory cytokines upregulated",
            "Immunosuppressive genes downregulated",
            "Type 1 immune response activated",
        ],
        expected_genes=["IFNG", "TNF", "CD8A", "GZMB", "STAT1"],
        expected_pathways=["Interferon signaling", "T cell activation", "Cytokine signaling"],
        description="Strong T cell-mediated immune response",
        tags=["deg", "synthetic", "strong_signal", "immune"],
    )


def deg_emt_transition() -> DEGBenchmarkTask:
    """Additional case: Epithelial-mesenchymal transition.

    Classic EMT gene expression pattern.
    """
    return DEGBenchmarkTask(
        task_id="deg-synthetic-005",
        task_name="EMT Transition",
        upregulated=[
            ("VIM", 3.5),  # Vimentin
            ("FN1", 3.2),  # Fibronectin
            ("CDH2", 2.8),  # N-cadherin
            ("SNAI1", 2.5),  # Snail
            ("SNAI2", 2.3),  # Slug
            ("ZEB1", 2.0),
            ("TWIST1", 1.9),
        ],
        downregulated=[
            ("CDH1", -3.0),  # E-cadherin
            ("EPCAM", -2.5),
            ("KRT19", -2.2),
            ("CLDN1", -2.0),
            ("OCLN", -1.8),
        ],
        condition_a="mesenchymal",
        condition_b="epithelial",
        expected_claims=[
            "E-cadherin downregulation indicates loss of epithelial phenotype",
            "Vimentin and fibronectin upregulation indicates mesenchymal transition",
            "EMT transcription factors SNAI1/ZEB1/TWIST1 are activated",
            "Classic epithelial-mesenchymal transition pattern detected",
        ],
        expected_genes=["CDH1", "VIM", "SNAI1", "ZEB1", "CDH2"],
        expected_pathways=["EMT", "Cell adhesion", "TGF-beta signaling"],
        description="Classic EMT signature with cadherin switch",
        tags=["deg", "synthetic", "strong_signal", "emt", "cancer"],
    )


def deg_drug_response() -> DEGBenchmarkTask:
    """Case 7: AhR-mediated xenobiotic detoxification response.

    TCDD-induced AhR pathway activation with phase I/II enzyme induction.
    Tests identification of xenobiotic metabolism pathways.
    """
    return DEGBenchmarkTask(
        task_id="deg-synthetic-006",
        task_name="Drug Response - Xenobiotic",
        upregulated=[
            ("CYP1A1", 4.0),
            ("CYP1B1", 3.5),
            ("AHR", 2.8),
            ("NQO1", 2.2),
            ("ALDH3A1", 2.0),
            ("TIPARP", 1.8),
        ],
        downregulated=[
            ("CYP3A4", -1.5),
            ("UGT1A1", -1.2),
            ("ABCB1", -1.0),
        ],
        condition_a="TCDD_treated",
        condition_b="DMSO_control",
        expected_claims=[
            "AhR pathway activation by xenobiotic exposure",
            "CYP1A1/CYP1B1 induction indicates phase I detoxification",
            "NQO1 upregulation consistent with NRF2-mediated antioxidant response",
            "Xenobiotic metabolism activated",
            "Potential toxicological implications",
        ],
        expected_genes=["CYP1A1", "CYP1B1", "AHR", "NQO1"],
        expected_pathways=["Xenobiotic metabolism", "AhR signaling", "Drug metabolism - cytochrome P450"],
        description="AhR-mediated xenobiotic detoxification response",
        tags=["deg", "synthetic", "strong_signal", "toxicology", "xenobiotic"],
    )


def deg_hypoxia_response() -> DEGBenchmarkTask:
    """Case 8: HIF-1 driven hypoxia response.

    Hypoxic conditions leading to HIF-1alpha stabilization with metabolic
    and angiogenic signatures. Tests identification of oxygen sensing pathways.
    """
    return DEGBenchmarkTask(
        task_id="deg-synthetic-007",
        task_name="Hypoxia Response",
        upregulated=[
            ("HIF1A", 2.5),
            ("VEGFA", 3.2),
            ("LDHA", 2.8),
            ("PDK1", 2.5),
            ("SLC2A1", 2.2),
            ("BNIP3", 2.0),
            ("CA9", 3.0),
        ],
        downregulated=[
            ("EGLN1", -1.8),
            ("VHL", -1.2),
            ("SDHB", -1.0),
        ],
        condition_a="hypoxic",
        condition_b="normoxic",
        expected_claims=[
            "HIF-1alpha stabilization and activation",
            "VEGFA upregulation for angiogenesis",
            "Metabolic shift to glycolysis (LDHA/PDK1)",
            "Hypoxia-responsive genes activated",
            "VHL/EGLN1 oxygen sensing pathway disrupted",
        ],
        expected_genes=["HIF1A", "VEGFA", "LDHA", "CA9", "PDK1"],
        expected_pathways=["HIF-1 signaling", "Glycolysis", "Angiogenesis", "VEGF signaling"],
        description="HIF-1 driven hypoxia response with metabolic and angiogenic signatures",
        tags=["deg", "synthetic", "strong_signal", "hypoxia"],
    )


def deg_mixed_contradictory() -> DEGBenchmarkTask:
    """Case 9: Contradictory oncogene and tumor suppressor co-activation.

    Mixed signals with both pro-growth and anti-growth pathways active.
    Tests ability to recognize and flag contradictory patterns.
    """
    return DEGBenchmarkTask(
        task_id="deg-synthetic-008",
        task_name="Mixed Contradictory Signal",
        upregulated=[
            ("MYC", 2.5),
            ("TP53", 2.0),
            ("CCND1", 1.8),
            ("BCL2", 1.5),
            ("E2F1", 1.3),
        ],
        downregulated=[
            ("RB1", -1.5),
            ("CDKN1A", -1.2),
            ("BAX", -1.0),
            ("PTEN", -1.8),
        ],
        condition_a="tumor_sample",
        condition_b="adjacent_normal",
        expected_claims=[
            "Competing oncogenic and tumor-suppressor signals",
            "MYC and TP53 co-upregulation is contradictory and unusual",
            "Loss of RB1/CDKN1A suggests cell cycle deregulation",
            "BCL2 upregulation with BAX downregulation favors survival",
            "Signal is complex and may reflect tumor heterogeneity",
        ],
        expected_genes=["MYC", "TP53", "CCND1", "RB1", "PTEN", "BCL2"],
        expected_pathways=["Cell cycle", "p53 signaling", "Apoptosis", "PI3K-AKT signaling"],
        description="Contradictory oncogene + tumor suppressor co-activation",
        tags=["deg", "synthetic", "mixed_signal", "contradictory", "cancer"],
    )


def deg_senescence_signature() -> DEGBenchmarkTask:
    """Case 10: Cellular senescence with SASP.

    Senescent cells with p16 upregulation, SASP factors, and loss of
    proliferation markers. Tests distinguishing senescence from simple
    cell cycle arrest.
    """
    return DEGBenchmarkTask(
        task_id="deg-synthetic-009",
        task_name="Senescence Signature",
        upregulated=[
            ("CDKN2A", 3.5),
            ("CDKN1A", 2.8),
            ("IL6", 2.0),
            ("CXCL8", 1.8),
            ("MMP3", 1.5),
            ("SERPINE1", 1.8),
        ],
        downregulated=[
            ("LMNB1", -2.5),
            ("PCNA", -1.8),
            ("MCM2", -1.5),
            ("CDK2", -1.3),
            ("TERT", -2.0),
        ],
        condition_a="senescent",
        condition_b="proliferating",
        expected_claims=[
            "CDKN2A (p16) upregulation indicates cellular senescence",
            "SASP factors (IL6/CXCL8/MMP3) secreted",
            "LMNB1 loss is a senescence marker",
            "Proliferation markers suppressed (PCNA/MCM2)",
            "Telomerase (TERT) downregulation",
            "This is senescence not just cell cycle arrest",
        ],
        expected_genes=["CDKN2A", "CDKN1A", "LMNB1", "IL6", "TERT"],
        expected_pathways=["Cellular senescence", "SASP", "Cell cycle arrest", "p53/p21 pathway"],
        description="Cellular senescence with SASP — must identify senescence, not just cell cycle arrest",
        tags=["deg", "synthetic", "strong_signal", "senescence", "aging"],
    )


def get_all_deg_tasks() -> list[DEGBenchmarkTask]:
    """Get all DEG benchmark tasks.

    Returns:
        List of DEG benchmark tasks
    """
    return [
        deg_strong_signal_coherent(),
        deg_weak_signal_noisy(),
        deg_no_signal(),
        deg_immune_response(),
        deg_emt_transition(),
        deg_drug_response(),
        deg_hypoxia_response(),
        deg_mixed_contradictory(),
        deg_senescence_signature(),
    ]
