"""Published paper benchmark tasks.

Benchmark tasks based on real published bioinformatics papers
with known results that serve as ground truth.
"""

from datetime import datetime
from typing import Any

from quration.benchmarks.metrics import BenchmarkMetrics
from quration.benchmarks.tasks.base import (
    BenchmarkInput,
    BenchmarkResult,
    BenchmarkTask,
    ExpectedOutput,
    PublishedBenchmarkTask,
)


class PublishedDEGBenchmarkTask(PublishedBenchmarkTask):
    """Benchmark task from published DEG analysis paper."""

    def __init__(
        self,
        task_id: str,
        task_name: str,
        paper_doi: str,
        paper_title: str,
        paper_year: int,
        upregulated: list[tuple[str, float]],
        downregulated: list[tuple[str, float]],
        condition_a: str,
        condition_b: str,
        organism: str,
        experiment_type: str,
        expected_claims: list[str],
        expected_genes: list[str],
        expected_pathways: list[str],
        description: str = "",
        tags: list[str] | None = None,
    ):
        """Initialize published DEG benchmark task.

        Args:
            task_id: Task identifier
            task_name: Task name
            paper_doi: DOI of the source paper
            paper_title: Title of the source paper
            paper_year: Publication year
            upregulated: List of (gene, log2fc) tuples
            downregulated: List of (gene, log2fc) tuples
            condition_a: First condition
            condition_b: Second condition
            organism: Organism
            experiment_type: Experiment type
            expected_claims: Expected claims from paper
            expected_genes: Key genes from paper
            expected_pathways: Key pathways from paper
            description: Task description
            tags: Task tags
        """
        super().__init__(
            task_id=task_id,
            task_name=task_name,
            task_type="deg_analysis",
            paper_doi=paper_doi,
            paper_title=paper_title,
            paper_year=paper_year,
            description=description,
            tags=tags or ["deg", "published"],
        )
        self._upregulated = upregulated
        self._downregulated = downregulated
        self._condition_a = condition_a
        self._condition_b = condition_b
        self._organism = organism
        self._experiment_type = experiment_type
        self._expected_claims = expected_claims
        self._expected_genes = expected_genes
        self._expected_pathways = expected_pathways

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
        """Run the published DEG interpretation benchmark."""
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
                    "paper_doi": self.paper_doi,
                    "paper_title": self.paper_title,
                    "paper_year": self.paper_year,
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


class PublishedPathwayBenchmarkTask(PublishedBenchmarkTask):
    """Benchmark task from published pathway enrichment paper."""

    def __init__(
        self,
        task_id: str,
        task_name: str,
        paper_doi: str,
        paper_title: str,
        paper_year: int,
        gene_list: list[str],
        background_genes: list[str] | None,
        organism: str,
        enrichment_source: str,
        expected_claims: list[str],
        expected_pathways: list[str],
        description: str = "",
        tags: list[str] | None = None,
    ):
        """Initialize published pathway benchmark task.

        Args:
            task_id: Task identifier
            task_name: Task name
            paper_doi: DOI of the source paper
            paper_title: Title of the source paper
            paper_year: Publication year
            gene_list: List of genes for enrichment
            background_genes: Optional background gene set
            organism: Organism
            enrichment_source: Database for enrichment (Reactome, KEGG, GO)
            expected_claims: Expected claims from paper
            expected_pathways: Key pathways from paper
            description: Task description
            tags: Task tags
        """
        super().__init__(
            task_id=task_id,
            task_name=task_name,
            task_type="pathway_enrichment",
            paper_doi=paper_doi,
            paper_title=paper_title,
            paper_year=paper_year,
            description=description,
            tags=tags or ["pathway", "published"],
        )
        self._gene_list = gene_list
        self._background_genes = background_genes
        self._organism = organism
        self._enrichment_source = enrichment_source
        self._expected_claims = expected_claims
        self._expected_pathways = expected_pathways

    def get_input(self) -> BenchmarkInput:
        return BenchmarkInput(
            task_type="pathway_enrichment",
            data={
                "gene_list": self._gene_list,
                "background_genes": self._background_genes,
                "organism": self._organism,
                "enrichment_source": self._enrichment_source,
            },
        )

    def get_expected_output(self) -> ExpectedOutput:
        return ExpectedOutput(
            claims=self._expected_claims,
            pathways=self._expected_pathways,
            expected_tools=["get_reactome_pathway", "get_go_enrichment", "get_kegg_pathway"],
        )

    async def run(self, service: Any) -> BenchmarkResult:
        """Run the published pathway interpretation benchmark."""
        start_time = datetime.utcnow()

        try:
            # Convert stored gene list to the pathway dict format the service expects
            pathways = [
                {
                    "name": f"{self._enrichment_source} analysis",
                    "p_value": 0.001,
                    "gene_count": len(self._gene_list),
                    "genes": self._gene_list,
                }
            ]
            experiment_context = (
                f"Pathway enrichment of {len(self._gene_list)} genes "
                f"from: {self.paper_title}"
            )
            result = await service.interpret_pathway_enrichment(
                pathways=pathways,
                experiment_context=experiment_context,
                gene_set_size=len(self._gene_list),
                max_iterations=10,
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
                    "paper_doi": self.paper_doi,
                    "paper_title": self.paper_title,
                    "paper_year": self.paper_year,
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
# Published Test Cases
# ============================================================================


def published_brca_tcga() -> PublishedDEGBenchmarkTask:
    """TCGA BRCA paper - Breast cancer DEG analysis.

    Based on The Cancer Genome Atlas Network breast cancer analysis.
    Reference: Nature 2012.
    """
    return PublishedDEGBenchmarkTask(
        task_id="pub-deg-001",
        task_name="TCGA Breast Cancer",
        paper_doi="10.1038/nature11412",
        paper_title="Comprehensive molecular portraits of human breast tumours",
        paper_year=2012,
        upregulated=[
            ("ESR1", 4.2),
            ("GATA3", 3.8),
            ("FOXA1", 3.5),
            ("XBP1", 2.9),
            ("TFF1", 2.8),
            ("AGR2", 2.5),
            ("ERBB2", 3.2),
            ("GRB7", 2.7),
        ],
        downregulated=[
            ("KRT5", -3.5),
            ("KRT17", -3.2),
            ("KRT14", -2.8),
            ("TP63", -2.5),
            ("EGFR", -2.2),
            ("SOX10", -2.0),
        ],
        condition_a="luminal",
        condition_b="basal",
        organism="human",
        experiment_type="RNA-seq",
        expected_claims=[
            "ESR1 and estrogen receptor signaling upregulated in luminal tumors",
            "GATA3 and FOXA1 are key luminal transcription factors",
            "ERBB2 (HER2) shows elevated expression",
            "Basal-like markers KRT5/KRT14/KRT17 downregulated in luminal subtype",
            "Molecular subtypes show distinct expression patterns",
        ],
        expected_genes=["ESR1", "GATA3", "FOXA1", "ERBB2", "KRT5", "KRT14"],
        expected_pathways=[
            "Estrogen receptor signaling",
            "Receptor tyrosine kinase signaling",
            "Cell differentiation",
        ],
        description="TCGA breast cancer molecular subtypes - luminal vs basal",
        tags=["deg", "published", "cancer", "tcga", "breast"],
    )


def published_covid_pbmc() -> PublishedDEGBenchmarkTask:
    """COVID-19 PBMC transcriptomics.

    Based on early COVID-19 immune profiling studies.
    Reference: Cell 2020 / Nature Medicine 2020.
    """
    return PublishedDEGBenchmarkTask(
        task_id="pub-deg-002",
        task_name="COVID-19 PBMC Response",
        paper_doi="10.1016/j.cell.2020.04.026",
        paper_title="A single-cell atlas of the peripheral immune response in patients with severe COVID-19",
        paper_year=2020,
        upregulated=[
            ("ISG15", 5.2),
            ("IFIT1", 4.8),
            ("IFIT3", 4.5),
            ("MX1", 4.2),
            ("OAS1", 3.9),
            ("IFI44L", 3.7),
            ("SIGLEC1", 3.5),
            ("IL1B", 2.8),
            ("CCL2", 2.5),
            ("S100A8", 3.2),
        ],
        downregulated=[
            ("CD3D", -2.5),
            ("CD8A", -2.2),
            ("CD4", -1.8),
            ("IL7R", -2.0),
            ("TCF7", -1.9),
            ("LEF1", -1.7),
        ],
        condition_a="severe_covid",
        condition_b="healthy",
        organism="human",
        experiment_type="scRNA-seq",
        expected_claims=[
            "Strong interferon-stimulated gene (ISG) signature",
            "Type I interferon response is activated",
            "T cell markers are downregulated",
            "Lymphopenia indicated by reduced T cell gene expression",
            "Inflammatory monocyte signature present",
            "ISG15 and IFIT genes highly upregulated",
        ],
        expected_genes=["ISG15", "IFIT1", "MX1", "OAS1", "CD3D", "CD8A"],
        expected_pathways=[
            "Type I interferon signaling",
            "Antiviral response",
            "Innate immune response",
            "T cell signaling",
        ],
        description="COVID-19 PBMC immune response - severe vs healthy",
        tags=["deg", "published", "covid", "immune", "scRNA-seq"],
    )


def published_ipf_lung() -> PublishedDEGBenchmarkTask:
    """Idiopathic Pulmonary Fibrosis lung transcriptomics.

    Based on IPF gene expression studies.
    Reference: AJRCCM 2017 / Nature Medicine 2018.
    """
    return PublishedDEGBenchmarkTask(
        task_id="pub-deg-003",
        task_name="IPF Lung Fibrosis",
        paper_doi="10.1164/rccm.201712-2410OC",
        paper_title="Single-Cell RNA Sequencing Identifies Diverse Roles of Epithelial Cells in Idiopathic Pulmonary Fibrosis",
        paper_year=2018,
        upregulated=[
            ("COL1A1", 4.5),
            ("COL3A1", 4.2),
            ("FN1", 3.8),
            ("MMP7", 3.5),
            ("SPP1", 3.3),
            ("TGFB1", 2.8),
            ("POSTN", 3.0),
            ("FAP", 2.5),
            ("ACTA2", 2.8),
        ],
        downregulated=[
            ("SFTPC", -4.0),
            ("SFTPB", -3.5),
            ("SCGB1A1", -3.0),
            ("AGER", -2.8),
            ("NKX2-1", -2.5),
            ("HOPX", -2.2),
        ],
        condition_a="ipf",
        condition_b="healthy_lung",
        organism="human",
        experiment_type="RNA-seq",
        expected_claims=[
            "Collagen genes strongly upregulated indicating fibrosis",
            "Extracellular matrix remodeling signature",
            "MMP7 is a key IPF biomarker",
            "Surfactant proteins downregulated indicating AT2 cell dysfunction",
            "TGF-beta signaling activated",
            "Myofibroblast markers elevated",
        ],
        expected_genes=["COL1A1", "MMP7", "FN1", "SFTPC", "TGFB1", "ACTA2"],
        expected_pathways=[
            "ECM organization",
            "TGF-beta signaling",
            "Collagen formation",
            "Wound healing",
        ],
        description="IPF vs healthy lung - fibrotic signature",
        tags=["deg", "published", "lung", "fibrosis", "disease"],
    )


def published_aging_brain() -> PublishedDEGBenchmarkTask:
    """Brain aging transcriptomics.

    Based on GTEx and aging brain studies.
    Reference: Nature 2019 / Genome Research.
    """
    return PublishedDEGBenchmarkTask(
        task_id="pub-deg-004",
        task_name="Brain Aging Signature",
        paper_doi="10.1038/s41586-019-1545-0",
        paper_title="Human brain aging atlas",
        paper_year=2019,
        upregulated=[
            ("GFAP", 2.5),
            ("CD44", 2.2),
            ("SERPINA3", 2.0),
            ("CLU", 1.8),
            ("C3", 1.7),
            ("VIM", 1.5),
            ("SOD2", 1.4),
        ],
        downregulated=[
            ("SYP", -2.0),
            ("BDNF", -1.8),
            ("CREB1", -1.5),
            ("SYN1", -1.4),
            ("GAD1", -1.3),
            ("SLC17A7", -1.2),
        ],
        condition_a="aged",
        condition_b="young",
        organism="human",
        experiment_type="RNA-seq",
        expected_claims=[
            "Astrocyte activation markers elevated with age",
            "Neuroinflammation indicated by GFAP and complement",
            "Synaptic genes downregulated",
            "BDNF reduction associated with cognitive decline",
            "Oxidative stress response genes upregulated",
        ],
        expected_genes=["GFAP", "C3", "SYP", "BDNF", "CLU"],
        expected_pathways=[
            "Neuroinflammation",
            "Synaptic signaling",
            "Complement cascade",
            "Astrocyte activation",
        ],
        description="Brain aging - old vs young",
        tags=["deg", "published", "brain", "aging", "gtex"],
    )


def published_stemcell_pathway() -> PublishedPathwayBenchmarkTask:
    """Stem cell pluripotency pathway enrichment.

    Based on iPSC and ESC studies.
    Reference: Cell Stem Cell / Nature.
    """
    return PublishedPathwayBenchmarkTask(
        task_id="pub-pathway-001",
        task_name="Pluripotency Pathways",
        paper_doi="10.1016/j.cell.2007.11.019",
        paper_title="Induction of Pluripotent Stem Cells from Adult Human Fibroblasts by Defined Factors",
        paper_year=2007,
        gene_list=[
            "OCT4",
            "SOX2",
            "NANOG",
            "KLF4",
            "MYC",
            "LIN28A",
            "DPPA4",
            "ZFP42",
            "SALL4",
            "TDGF1",
            "DNMT3B",
            "UTF1",
            "PODXL",
        ],
        background_genes=None,
        organism="human",
        enrichment_source="Reactome",
        expected_claims=[
            "Pluripotency transcription factors highly enriched",
            "OCT4-SOX2-NANOG core regulatory network",
            "Self-renewal pathways activated",
            "Epigenetic regulators present",
        ],
        expected_pathways=[
            "Signaling pathways regulating pluripotency",
            "Transcriptional regulation by OCT4",
            "POU5F1 (OCT4), SOX2, NANOG activate genes",
        ],
        description="iPSC/ESC pluripotency gene set enrichment",
        tags=["pathway", "published", "stemcell", "pluripotency"],
    )


def published_inflammation_pathway() -> PublishedPathwayBenchmarkTask:
    """Inflammatory response pathway enrichment.

    Based on NF-kB and inflammation studies.
    Reference: Cell / Immunity.
    """
    return PublishedPathwayBenchmarkTask(
        task_id="pub-pathway-002",
        task_name="NF-kB Inflammation",
        paper_doi="10.1016/j.immuni.2012.12.001",
        paper_title="The NF-kB family of transcription factors and its regulation",
        paper_year=2012,
        gene_list=[
            "NFKB1",
            "RELA",
            "IKBKB",
            "TNF",
            "IL1B",
            "IL6",
            "CXCL8",
            "CCL2",
            "ICAM1",
            "VCAM1",
            "PTGS2",
            "MMP9",
            "BCL2",
            "BIRC3",
        ],
        background_genes=None,
        organism="human",
        enrichment_source="KEGG",
        expected_claims=[
            "NF-kB signaling pathway highly enriched",
            "Pro-inflammatory cytokines cluster together",
            "Cell survival genes present (BCL2, BIRC3)",
            "Adhesion molecules indicate inflammation",
        ],
        expected_pathways=[
            "NF-kappa B signaling pathway",
            "TNF signaling pathway",
            "Cytokine-cytokine receptor interaction",
            "IL-17 signaling pathway",
        ],
        description="NF-kB inflammatory response gene set",
        tags=["pathway", "published", "inflammation", "nfkb"],
    )


def get_all_published_tasks() -> list[PublishedBenchmarkTask]:
    """Get all published benchmark tasks.

    Returns:
        List of published benchmark tasks
    """
    return [
        published_brca_tcga(),
        published_covid_pbmc(),
        published_ipf_lung(),
        published_aging_brain(),
        published_stemcell_pathway(),
        published_inflammation_pathway(),
    ]


def get_published_deg_tasks() -> list[PublishedDEGBenchmarkTask]:
    """Get published DEG benchmark tasks.

    Returns:
        List of published DEG benchmark tasks
    """
    return [
        published_brca_tcga(),
        published_covid_pbmc(),
        published_ipf_lung(),
        published_aging_brain(),
    ]


def get_published_pathway_tasks() -> list[PublishedPathwayBenchmarkTask]:
    """Get published pathway benchmark tasks.

    Returns:
        List of published pathway benchmark tasks
    """
    return [
        published_stemcell_pathway(),
        published_inflammation_pathway(),
    ]
