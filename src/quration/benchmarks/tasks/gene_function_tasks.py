"""Gene function analysis benchmark tasks.

Synthetic test cases for gene function interpretation.
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


class GeneFunctionBenchmarkTask(BenchmarkTask):
    """Base class for gene function benchmark tasks."""

    def __init__(
        self,
        task_id: str,
        task_name: str,
        genes: list[str],
        analysis_context: str,
        expected_claims: list[str],
        expected_genes: list[str] | None = None,
        expected_pathways: list[str] | None = None,
        description: str = "",
        tags: list[str] | None = None,
    ):
        """Initialize gene function benchmark task.

        Args:
            task_id: Task identifier
            task_name: Task name
            genes: List of gene symbols to analyze
            analysis_context: Biological context for the analysis
            expected_claims: Expected claims
            expected_genes: Expected genes to mention
            expected_pathways: Expected pathways to identify
            description: Task description
            tags: Task tags
        """
        super().__init__(
            task_id=task_id,
            task_name=task_name,
            task_type="gene_function",
            description=description,
            tags=tags or ["gene_function", "synthetic"],
        )
        self._genes = genes
        self._analysis_context = analysis_context
        self._expected_claims = expected_claims
        self._expected_genes = expected_genes or []
        self._expected_pathways = expected_pathways or []

    def get_input(self) -> BenchmarkInput:
        return BenchmarkInput(
            task_type="gene_function",
            data={
                "genes": self._genes,
                "analysis_context": self._analysis_context,
            },
        )

    def get_expected_output(self) -> ExpectedOutput:
        return ExpectedOutput(
            claims=self._expected_claims,
            genes=self._expected_genes,
            pathways=self._expected_pathways,
            expected_tools=[
                "get_gene_info",
                "get_protein_function",
                "get_interaction_partners",
                "search_gene_literature",
            ],
        )

    async def run(self, service: Any) -> BenchmarkResult:
        """Run the gene function interpretation benchmark."""
        start_time = datetime.utcnow()

        try:
            result = await service.analyze_gene_function(
                genes=self._genes,
                analysis_context=self._analysis_context,
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


def gf_tumor_suppressors() -> GeneFunctionBenchmarkTask:
    """Tumor suppressor genes in cancer genomics.

    Well-characterized tumor suppressors with established roles in oncogenesis.
    Tests basic gene function interpretation capability.
    """
    return GeneFunctionBenchmarkTask(
        task_id="gf-synthetic-001",
        task_name="Tumor Suppressors",
        genes=["TP53", "RB1", "PTEN"],
        analysis_context="Cancer genomics — role of tumor suppressors in oncogenesis",
        expected_claims=[
            "TP53 is the guardian of the genome, controlling cell cycle and apoptosis",
            "RB1 encodes the retinoblastoma protein involved in cell cycle regulation",
            "PTEN negatively regulates the PI3K/AKT signaling pathway",
            "These genes cooperate in tumor suppression",
            "Loss-of-function mutations in these genes are common in cancer",
        ],
        expected_genes=["TP53", "RB1", "PTEN"],
        expected_pathways=["p53 signaling", "Cell cycle", "PI3K-AKT signaling"],
        description="Core tumor suppressor gene functions in oncogenesis",
        tags=["gene_function", "synthetic", "cancer", "tumor_suppressor"],
    )


def gf_epigenetic_regulators() -> GeneFunctionBenchmarkTask:
    """Epigenetic regulators in acute myeloid leukemia.

    Key chromatin-modifying enzymes frequently mutated in AML.
    Tests understanding of epigenetic machinery and its role in leukemia.
    """
    return GeneFunctionBenchmarkTask(
        task_id="gf-synthetic-002",
        task_name="Epigenetic Regulators",
        genes=["DNMT1", "TET2", "EZH2", "KDM5A"],
        analysis_context="Epigenetic dysregulation in acute myeloid leukemia (AML)",
        expected_claims=[
            "DNMT1 is a DNA methyltransferase responsible for maintenance methylation",
            "TET2 catalyzes DNA demethylation through conversion to 5-hydroxymethylcytosine",
            "EZH2 mediates polycomb repression via H3K27 trimethylation",
            "KDM5A is a histone demethylase targeting H3K4 methylation marks",
            "Epigenetic crosstalk among these regulators is disrupted in leukemia",
        ],
        expected_genes=["DNMT1", "TET2", "EZH2", "KDM5A"],
        expected_pathways=["DNA methylation", "Chromatin modification", "Polycomb repressive complex"],
        description="Epigenetic regulators and their dysregulation in AML",
        tags=["gene_function", "synthetic", "epigenetics", "leukemia"],
    )


def gf_ion_channels() -> GeneFunctionBenchmarkTask:
    """Ion channel genes in pediatric epilepsy.

    Voltage-gated ion channels implicated in channelopathies.
    Tests understanding of neuronal excitability and pharmacogenomics.
    """
    return GeneFunctionBenchmarkTask(
        task_id="gf-synthetic-003",
        task_name="Ion Channels",
        genes=["SCN1A", "KCNQ2", "CACNA1A"],
        analysis_context="Channelopathies in pediatric epilepsy",
        expected_claims=[
            "SCN1A sodium channel mutations cause Dravet syndrome",
            "KCNQ2 potassium channel dysfunction leads to neonatal seizures",
            "CACNA1A calcium channel variants are linked to episodic ataxia and epilepsy",
            "Ion channel dysfunction disrupts neuronal excitability",
            "These genes have pharmacogenomic implications for antiepileptic drug selection",
        ],
        expected_genes=["SCN1A", "KCNQ2", "CACNA1A"],
        expected_pathways=["Ion channel transport", "Neuronal excitability", "Synaptic transmission"],
        description="Ion channel channelopathies in pediatric epilepsy",
        tags=["gene_function", "synthetic", "neurology", "epilepsy", "channels"],
    )


def gf_drug_metabolism() -> GeneFunctionBenchmarkTask:
    """Drug metabolism enzymes and transporters.

    Core pharmacogenomic genes affecting drug metabolism and transport.
    Tests understanding of pharmacokinetics and genetic variability.
    """
    return GeneFunctionBenchmarkTask(
        task_id="gf-synthetic-004",
        task_name="Drug Metabolism Enzymes",
        genes=["CYP2D6", "CYP3A4", "UGT1A1", "ABCB1"],
        analysis_context="Pharmacogenomics of drug metabolism and transport",
        expected_claims=[
            "CYP2D6 polymorphisms significantly affect drug metabolism rates",
            "CYP3A4 is the major drug-metabolizing cytochrome P450 enzyme",
            "UGT1A1 catalyzes glucuronidation and variants cause Gilbert syndrome",
            "ABCB1 encodes P-glycoprotein, a major efflux transporter",
            "Pharmacogenomic variability in these genes drives inter-individual drug response differences",
        ],
        expected_genes=["CYP2D6", "CYP3A4", "UGT1A1", "ABCB1"],
        expected_pathways=["Drug metabolism - cytochrome P450", "Phase II conjugation", "ABC transporters"],
        description="Pharmacogenomic genes governing drug metabolism and transport",
        tags=["gene_function", "synthetic", "pharmacogenomics", "drug_metabolism"],
    )


def gf_single_gene_foxp3() -> GeneFunctionBenchmarkTask:
    """Single gene analysis of FOXP3 in regulatory T cell biology.

    Master transcription factor for Treg development.
    Tests depth of analysis for a single gene across multiple contexts.
    """
    return GeneFunctionBenchmarkTask(
        task_id="gf-synthetic-005",
        task_name="Single Gene - FOXP3",
        genes=["FOXP3"],
        analysis_context="Regulatory T cell biology and autoimmune disease",
        expected_claims=[
            "FOXP3 is the master regulator of regulatory T cell development",
            "FOXP3 is critical for maintaining immune tolerance",
            "Mutations in FOXP3 cause IPEX syndrome",
            "FOXP3 suppresses effector T cell activation",
            "FOXP3 is a therapeutic target in autoimmunity and cancer immunotherapy",
        ],
        expected_genes=["FOXP3"],
        expected_pathways=["T cell differentiation", "Immune regulation", "FOXP3 transcriptional network"],
        description="Deep analysis of FOXP3 in Treg biology and autoimmune disease",
        tags=["gene_function", "synthetic", "immunology", "treg", "single_gene"],
    )


def get_all_gene_function_tasks() -> list[GeneFunctionBenchmarkTask]:
    """Get all gene function benchmark tasks.

    Returns:
        List of gene function benchmark tasks
    """
    return [
        gf_tumor_suppressors(),
        gf_epigenetic_regulators(),
        gf_ion_channels(),
        gf_drug_metabolism(),
        gf_single_gene_foxp3(),
    ]
