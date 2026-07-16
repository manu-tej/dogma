"""
Method Registry

Manages the collection of available analysis methods and pipelines.
Provides search, filtering, and management capabilities.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from quration.broker.models import (
    AnalysisMethod,
    DataModality,
    MethodAssumption,
    MethodCategory,
    MethodCaveat,
    MethodInputSpec,
    MethodOutputSpec,
    MethodQualityMetrics,
)


def analysis_method_from_dict(data: Dict) -> AnalysisMethod:
    """Build an AnalysisMethod from a (possibly partial) provider dict.

    quration owns its types: rather than trust an external provider (e.g.
    methods_graph's KuzuMethodsGraphProvider) to supply every required field,
    this fills neutral defaults for anything missing so a sparse dict still
    yields a valid AnalysisMethod. Provided values always win.
    """
    d = dict(data)
    d.setdefault("category", MethodCategory.CUSTOM)
    d.setdefault("description", "")
    d.setdefault("implementation_type", "tool")
    d.setdefault("version", "")
    d.setdefault("inputs", [])
    d.setdefault("outputs", [])
    if not d.get("supported_modalities"):
        d["supported_modalities"] = [DataModality.UNKNOWN]
    if not d.get("quality_metrics"):
        d["quality_metrics"] = MethodQualityMetrics(
            reproducibility_score=0.5,
            code_availability=False,
            documentation_quality=0.5,
        )
    return AnalysisMethod(**d)


class MethodRegistry:
    """
    Registry of available analysis methods and pipelines.
    """

    def __init__(self, registry_path: Optional[Path] = None, provider: object = None):
        """
        Initialize the method registry.

        Args:
            registry_path: Optional path to load methods from disk
            provider: Optional methods provider exposing ``get_methods() -> list[dict]``
                (e.g. methods_graph's KuzuMethodsGraphProvider). When supplied it
                replaces the hardcoded defaults; when absent, defaults are used.
        """
        self.methods: Dict[str, AnalysisMethod] = {}
        self.registry_path = registry_path

        if provider is not None:
            # An injected methods graph replaces quration's hardcoded registry.
            self.load_from_provider(provider)
        elif registry_path and registry_path.exists():
            self.load_from_disk(registry_path)
        else:
            # Initialize with default methods
            self._initialize_default_methods()

    def load_from_provider(self, provider: object) -> int:
        """Populate the registry from a duck-typed methods provider.

        ``provider.get_methods()`` returns a list of AnalysisMethod-shaped dicts.
        Returns the number of methods loaded.
        """
        methods = provider.get_methods()
        for method_dict in methods:
            self.add_method(analysis_method_from_dict(method_dict))
        return len(methods)

    def _initialize_default_methods(self):
        """Initialize registry with common bioinformatics methods."""

        # GATK Best Practices for Variant Calling
        gatk_variant_calling = AnalysisMethod(
            id="gatk-germline-variant-calling",
            name="GATK Germline Variant Calling",
            category=MethodCategory.VARIANT_CALLING,
            description=(
                "GATK Best Practices workflow for germline short variant discovery "
                "(SNPs + Indels) in whole genome and exome sequencing data."
            ),
            implementation_type="nextflow",
            version="4.4.0.0",
            repository_url="https://github.com/nf-core/sarek",
            documentation_url="https://nf-co.re/sarek",
            inputs=[
                MethodInputSpec(
                    name="reads",
                    description="Paired-end FASTQ files",
                    data_type="FASTQ",
                    required=True,
                    multiple=True,
                    example="sample_R{1,2}.fastq.gz",
                ),
                MethodInputSpec(
                    name="reference_genome",
                    description="Reference genome (FASTA)",
                    data_type="FASTA",
                    required=True,
                    example="GRCh38.fa",
                ),
                MethodInputSpec(
                    name="known_sites",
                    description="Known variant sites for BQSR (VCF)",
                    data_type="VCF",
                    required=True,
                    multiple=True,
                ),
            ],
            outputs=[
                MethodOutputSpec(
                    name="vcf",
                    description="Filtered variant calls",
                    data_type="VCF",
                    file_pattern="*_filtered.vcf.gz",
                ),
                MethodOutputSpec(
                    name="bam",
                    description="Aligned and recalibrated BAM",
                    data_type="BAM",
                    file_pattern="*_recalibrated.bam",
                ),
            ],
            supported_modalities=[DataModality.DNA_SEQ],
            supported_organisms=["human", "mouse"],
            min_samples=1,
            assumptions=[
                MethodAssumption(
                    description="High-quality paired-end sequencing data (Q30 > 80%)",
                    category="data_quality",
                    critical=True,
                ),
                MethodAssumption(
                    description="Sufficient coverage for variant detection (>30x for WGS, >100x for WES)",
                    category="sequencing_depth",
                    critical=True,
                ),
            ],
            caveats=[
                MethodCaveat(
                    description="May miss variants in repetitive regions",
                    severity="medium",
                    workaround="Use specialized tools for complex regions",
                ),
                MethodCaveat(
                    description="Computationally intensive for large cohorts",
                    severity="low",
                    workaround="Use cloud computing or HPC clusters",
                ),
            ],
            quality_metrics=MethodQualityMetrics(
                reproducibility_score=0.95,
                code_availability=True,
                documentation_quality=0.98,
                peer_reviewed=True,
                citation_count=15000,
                last_updated=datetime(2024, 1, 15),
                community_rating=4.8,
            ),
            compute_requirements={
                "cpu_cores": 16,
                "memory_gb": 64,
                "storage_gb": 500,
            },
            estimated_runtime="6-12 hours for 30x WGS sample",
            tags=["variant-calling", "gatk", "best-practices", "germline", "nextflow"],
            publications=["10.1101/gr.107524.110", "10.1038/ng.806"],
        )

        # DESeq2 for RNA-seq differential expression
        deseq2 = AnalysisMethod(
            id="deseq2-differential-expression",
            name="DESeq2 Differential Expression Analysis",
            category=MethodCategory.DIFFERENTIAL_EXPRESSION,
            description=(
                "Statistical analysis of differential gene expression in RNA-seq data "
                "using DESeq2, with normalization and variance shrinkage."
            ),
            implementation_type="nextflow",
            version="1.40.0",
            repository_url="https://github.com/nf-core/rnaseq",
            documentation_url="https://nf-co.re/rnaseq",
            inputs=[
                MethodInputSpec(
                    name="count_matrix",
                    description="Gene count matrix",
                    data_type="TSV",
                    required=True,
                    example="counts.tsv",
                ),
                MethodInputSpec(
                    name="sample_metadata",
                    description="Sample metadata with conditions",
                    data_type="CSV",
                    required=True,
                    example="samples.csv",
                ),
            ],
            outputs=[
                MethodOutputSpec(
                    name="results_table",
                    description="Differential expression results",
                    data_type="CSV",
                    file_pattern="*_deseq2_results.csv",
                ),
                MethodOutputSpec(
                    name="normalized_counts",
                    description="Normalized count matrix",
                    data_type="TSV",
                    file_pattern="*_normalized_counts.tsv",
                ),
                MethodOutputSpec(
                    name="plots",
                    description="MA plot, volcano plot, PCA",
                    data_type="PDF",
                    file_pattern="*_plots.pdf",
                ),
            ],
            supported_modalities=[DataModality.RNA_SEQ],
            supported_organisms=None,  # Works with any organism
            min_samples=3,  # Need replicates for statistical testing
            assumptions=[
                MethodAssumption(
                    description="Count data follows negative binomial distribution",
                    category="statistical",
                    critical=True,
                ),
                MethodAssumption(
                    description="Biological replicates are available (>=3 per condition)",
                    category="experimental_design",
                    critical=True,
                ),
                MethodAssumption(
                    description="Library sizes are similar across samples",
                    category="data_quality",
                    critical=False,
                ),
            ],
            caveats=[
                MethodCaveat(
                    description="Assumes most genes are not differentially expressed",
                    severity="medium",
                    workaround="Use alternative normalization if assumption violated",
                ),
                MethodCaveat(
                    description="May have reduced power with small sample sizes",
                    severity="medium",
                    workaround="Use apeglm shrinkage to improve estimates",
                ),
            ],
            quality_metrics=MethodQualityMetrics(
                reproducibility_score=0.98,
                code_availability=True,
                documentation_quality=0.95,
                peer_reviewed=True,
                citation_count=45000,
                last_updated=datetime(2023, 10, 1),
                community_rating=4.9,
            ),
            compute_requirements={
                "cpu_cores": 4,
                "memory_gb": 16,
                "storage_gb": 50,
            },
            estimated_runtime="30 minutes for 20,000 genes, 50 samples",
            tags=["rnaseq", "differential-expression", "deseq2", "statistics"],
            publications=["10.1186/s13059-014-0550-8"],
        )

        # nf-core/chipseq
        chipseq = AnalysisMethod(
            id="nfcore-chipseq",
            name="nf-core ChIP-seq Pipeline",
            category=MethodCategory.CHIP_SEQ,
            description=(
                "Comprehensive ChIP-seq analysis pipeline including alignment, "
                "peak calling, quality control, and downstream analysis."
            ),
            implementation_type="nextflow",
            version="2.0.0",
            repository_url="https://github.com/nf-core/chipseq",
            documentation_url="https://nf-co.re/chipseq",
            inputs=[
                MethodInputSpec(
                    name="reads",
                    description="Single or paired-end FASTQ files",
                    data_type="FASTQ",
                    required=True,
                    multiple=True,
                ),
                MethodInputSpec(
                    name="reference_genome",
                    description="Reference genome",
                    data_type="FASTA",
                    required=True,
                ),
                MethodInputSpec(
                    name="design_file",
                    description="Design file mapping samples to conditions",
                    data_type="CSV",
                    required=True,
                ),
            ],
            outputs=[
                MethodOutputSpec(
                    name="peaks",
                    description="Called peaks (MACS2)",
                    data_type="BED",
                    file_pattern="*_peaks.narrowPeak",
                ),
                MethodOutputSpec(
                    name="bigwig",
                    description="Coverage tracks",
                    data_type="BigWig",
                    file_pattern="*.bigWig",
                ),
                MethodOutputSpec(
                    name="qc_report",
                    description="MultiQC report",
                    data_type="HTML",
                    file_pattern="multiqc_report.html",
                ),
            ],
            supported_modalities=[DataModality.CHIP_SEQ],
            min_samples=2,  # Need at least treatment + input
            assumptions=[
                MethodAssumption(
                    description="Input/control samples are available",
                    category="experimental_design",
                    critical=True,
                ),
                MethodAssumption(
                    description="Sufficient read depth (>10M reads per sample)",
                    category="sequencing_depth",
                    critical=True,
                ),
            ],
            caveats=[
                MethodCaveat(
                    description="Peak calling parameters may need tuning per experiment",
                    severity="medium",
                    workaround="Adjust MACS2 parameters based on expected peak width",
                ),
            ],
            quality_metrics=MethodQualityMetrics(
                reproducibility_score=0.92,
                code_availability=True,
                documentation_quality=0.94,
                peer_reviewed=True,
                citation_count=2000,
                last_updated=datetime(2024, 2, 1),
                community_rating=4.7,
            ),
            compute_requirements={
                "cpu_cores": 8,
                "memory_gb": 32,
                "storage_gb": 200,
            },
            estimated_runtime="4-6 hours for 20M reads",
            tags=["chipseq", "peak-calling", "macs2", "nextflow", "nf-core"],
            publications=["10.1186/gb-2008-9-9-r137"],
        )

        # Single-cell RNA-seq with Seurat
        seurat_scrna = AnalysisMethod(
            id="seurat-scrna-analysis",
            name="Seurat Single-cell RNA-seq Analysis",
            category=MethodCategory.SINGLE_CELL,
            description=(
                "Comprehensive single-cell RNA-seq analysis using Seurat: "
                "QC, normalization, clustering, differential expression, and visualization."
            ),
            implementation_type="script",
            version="5.0.0",
            repository_url="https://github.com/satijalab/seurat",
            documentation_url="https://satijalab.org/seurat/",
            inputs=[
                MethodInputSpec(
                    name="count_matrix",
                    description="Cell-by-gene count matrix",
                    data_type="MTX",
                    required=True,
                    example="matrix.mtx",
                ),
                MethodInputSpec(
                    name="features",
                    description="Gene features file",
                    data_type="TSV",
                    required=True,
                ),
                MethodInputSpec(
                    name="barcodes",
                    description="Cell barcodes file",
                    data_type="TSV",
                    required=True,
                ),
            ],
            outputs=[
                MethodOutputSpec(
                    name="seurat_object",
                    description="Processed Seurat object",
                    data_type="RDS",
                    file_pattern="seurat_object.rds",
                ),
                MethodOutputSpec(
                    name="clusters",
                    description="Cell cluster assignments",
                    data_type="CSV",
                    file_pattern="clusters.csv",
                ),
                MethodOutputSpec(
                    name="markers",
                    description="Cluster marker genes",
                    data_type="CSV",
                    file_pattern="markers.csv",
                ),
                MethodOutputSpec(
                    name="umap_plot",
                    description="UMAP visualization",
                    data_type="PDF",
                    file_pattern="umap.pdf",
                ),
            ],
            supported_modalities=[
                DataModality.SINGLE_CELL_RNA,
            ],
            min_samples=1,
            assumptions=[
                MethodAssumption(
                    description="Cells have been quality filtered (dead cells removed)",
                    category="data_quality",
                    critical=True,
                ),
                MethodAssumption(
                    description="Sufficient cells per sample (>1000 recommended)",
                    category="sample_size",
                    critical=True,
                ),
            ],
            caveats=[
                MethodCaveat(
                    description="Clustering resolution parameter affects number of clusters",
                    severity="medium",
                    workaround="Test multiple resolutions and use biological knowledge",
                ),
                MethodCaveat(
                    description="Memory intensive for large datasets (>100k cells)",
                    severity="medium",
                    workaround="Use subset analysis or high-memory compute nodes",
                ),
            ],
            quality_metrics=MethodQualityMetrics(
                reproducibility_score=0.90,
                code_availability=True,
                documentation_quality=0.96,
                peer_reviewed=True,
                citation_count=30000,
                last_updated=datetime(2024, 1, 1),
                community_rating=4.8,
            ),
            compute_requirements={
                "cpu_cores": 8,
                "memory_gb": 64,
                "storage_gb": 100,
            },
            estimated_runtime="1-2 hours for 10,000 cells",
            tags=["single-cell", "scrna-seq", "seurat", "clustering"],
            publications=["10.1016/j.cell.2021.04.048"],
        )

        # FastQC for quality control
        fastqc = AnalysisMethod(
            id="fastqc-quality-control",
            name="FastQC Quality Control",
            category=MethodCategory.QUALITY_CONTROL,
            description=(
                "Quality control checks on raw sequence data from high throughput "
                "sequencing pipelines. Provides modular analyses and reports."
            ),
            implementation_type="tool",
            version="0.12.1",
            repository_url="https://github.com/s-andrews/FastQC",
            documentation_url="https://www.bioinformatics.babraham.ac.uk/projects/fastqc/",
            inputs=[
                MethodInputSpec(
                    name="reads",
                    description="FASTQ files to analyze",
                    data_type="FASTQ",
                    required=True,
                    multiple=True,
                ),
            ],
            outputs=[
                MethodOutputSpec(
                    name="html_report",
                    description="HTML QC report",
                    data_type="HTML",
                    file_pattern="*_fastqc.html",
                ),
                MethodOutputSpec(
                    name="zip_data",
                    description="Detailed QC data",
                    data_type="ZIP",
                    file_pattern="*_fastqc.zip",
                ),
            ],
            supported_modalities=[
                DataModality.DNA_SEQ,
                DataModality.RNA_SEQ,
                DataModality.CHIP_SEQ,
                DataModality.ATAC_SEQ,
                DataModality.BISULFITE_SEQ,
            ],
            min_samples=1,
            assumptions=[],
            caveats=[
                MethodCaveat(
                    description="Some warnings may be expected for certain library types",
                    severity="low",
                    workaround="Interpret results in context of library prep method",
                ),
            ],
            quality_metrics=MethodQualityMetrics(
                reproducibility_score=1.0,
                code_availability=True,
                documentation_quality=0.90,
                peer_reviewed=False,
                citation_count=20000,
                last_updated=datetime(2023, 11, 1),
                community_rating=4.6,
            ),
            compute_requirements={
                "cpu_cores": 2,
                "memory_gb": 4,
                "storage_gb": 10,
            },
            estimated_runtime="5-15 minutes per FASTQ file",
            tags=["qc", "quality-control", "fastqc"],
            publications=[],
        )

        # Add all methods to registry
        for method in [gatk_variant_calling, deseq2, chipseq, seurat_scrna, fastqc]:
            self.add_method(method)

    def add_method(self, method: AnalysisMethod) -> None:
        """
        Add a method to the registry.

        Args:
            method: AnalysisMethod instance to add
        """
        self.methods[method.id] = method

    def get_method(self, method_id: str) -> Optional[AnalysisMethod]:
        """
        Retrieve a method by ID.

        Args:
            method_id: Unique method identifier

        Returns:
            AnalysisMethod if found, None otherwise
        """
        return self.methods.get(method_id)

    def list_methods(
        self,
        category: Optional[MethodCategory] = None,
        modality: Optional[DataModality] = None,
        status: Optional[str] = "active",
    ) -> List[AnalysisMethod]:
        """
        List methods with optional filtering.

        Args:
            category: Filter by method category
            modality: Filter by supported data modality
            status: Filter by method status

        Returns:
            List of matching methods
        """
        methods = list(self.methods.values())

        if category:
            methods = [m for m in methods if m.category == category]

        if modality:
            methods = [m for m in methods if modality in m.supported_modalities]

        if status:
            methods = [m for m in methods if m.status == status]

        return methods

    def search_methods(
        self,
        query: str,
        max_results: int = 10,
    ) -> List[AnalysisMethod]:
        """
        Search methods by keywords.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of matching methods, ranked by relevance
        """
        query_lower = query.lower()
        results = []

        for method in self.methods.values():
            # Simple scoring based on keyword matches
            score = 0

            if query_lower in method.name.lower():
                score += 10
            if query_lower in method.description.lower():
                score += 5
            if any(query_lower in tag for tag in method.tags):
                score += 7
            if method.category.value and query_lower in method.category.value:
                score += 8

            if score > 0:
                results.append((score, method))

        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)

        return [method for _, method in results[:max_results]]

    def save_to_disk(self, path: Path) -> None:
        """
        Save registry to disk as JSON.

        Args:
            path: Path to save registry file
        """
        data = {
            "methods": {
                method_id: method.model_dump(mode="json")
                for method_id, method in self.methods.items()
            }
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def load_from_disk(self, path: Path) -> None:
        """
        Load registry from disk.

        Args:
            path: Path to registry JSON file
        """
        with open(path) as f:
            data = json.load(f)

        for method_id, method_data in data.get("methods", {}).items():
            method = AnalysisMethod(**method_data)
            self.methods[method_id] = method

    def get_stats(self) -> Dict[str, any]:
        """
        Get registry statistics.

        Returns:
            Dictionary with registry statistics
        """
        methods = list(self.methods.values())

        return {
            "total_methods": len(methods),
            "by_category": {
                category.value: len([m for m in methods if m.category == category])
                for category in MethodCategory
            },
            "by_status": {
                status: len([m for m in methods if m.status == status])
                for status in ["active", "deprecated", "experimental"]
            },
            "average_quality_score": sum(
                m.quality_metrics.reproducibility_score for m in methods
            )
            / len(methods)
            if methods
            else 0,
        }
