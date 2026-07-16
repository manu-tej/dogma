"""
Pipeline registry containing catalog of available Nextflow pipelines.

This module maintains the catalog of supported nf-core and custom pipelines,
including their parameters, documentation, and metadata mapping configuration.
"""

from typing import Dict, List, Optional
from ..models.nextflow import (
    PipelineCatalogEntry,
    PipelineParameter,
    ParameterType,
    OmicsType,
)


class PipelineRegistry:
    """
    Registry of available Nextflow pipelines.

    Maintains the catalog of supported pipelines with their parameters,
    documentation, and configuration.
    """

    def __init__(self):
        self._pipelines: Dict[str, PipelineCatalogEntry] = {}
        self._initialize_catalog()

    def _initialize_catalog(self):
        """Initialize the pipeline catalog with nf-core pipelines."""

        # ===================================================================
        # BULK RNA-SEQ PIPELINE
        # ===================================================================
        self._pipelines["nf-core/rnaseq"] = PipelineCatalogEntry(
            id="nf-core/rnaseq",
            name="nf-core RNA-seq",
            version="3.14.0",
            omics_types=[OmicsType.BULK_RNASEQ],
            description="RNA sequencing analysis pipeline with comprehensive QC",
            long_description=(
                "nf-core/rnaseq is a bioinformatics pipeline for RNA sequencing data analysis. "
                "It performs quality control, trimming, alignment (STAR, RSEM, HISAT2, or Salmon), "
                "quantification at gene/transcript level, and generates comprehensive QC reports. "
                "Supports both reference genome and transcriptome-based analysis."
            ),
            documentation_url="https://nf-co.re/rnaseq/3.14.0/",
            repository_url="https://github.com/nf-core/rnaseq",
            input_format="FASTQ files or BAM files with samplesheet (CSV)",
            output_format="Gene/transcript counts, QC metrics, MultiQC report",
            citation=(
                "Ewels PA, Peltzer A, Fillinger S, et al. The nf-core framework for "
                "community-curated bioinformatics pipelines. Nat Biotechnol. 2020;38(3):276-278."
            ),
            tags=["rna-seq", "transcriptomics", "gene-expression", "nf-core"],
            parameters=[
                PipelineParameter(
                    name="--input",
                    type=ParameterType.FILE,
                    description="Path to samplesheet (CSV) with sample metadata and FASTQ paths",
                    required=True,
                    example="samplesheet.csv",
                    group="Input/Output"
                ),
                PipelineParameter(
                    name="--outdir",
                    type=ParameterType.DIRECTORY,
                    description="Output directory for results",
                    required=True,
                    example="./results",
                    group="Input/Output"
                ),
                PipelineParameter(
                    name="--genome",
                    type=ParameterType.CHOICE,
                    description="Reference genome identifier",
                    required=False,
                    choices=["GRCh38", "GRCh37", "GRCm39", "GRCm38"],
                    example="GRCh38",
                    group="Reference Genome"
                ),
                PipelineParameter(
                    name="--fasta",
                    type=ParameterType.FILE,
                    description="Path to FASTA genome file (if not using --genome)",
                    required=False,
                    group="Reference Genome"
                ),
                PipelineParameter(
                    name="--gtf",
                    type=ParameterType.FILE,
                    description="Path to GTF annotation file (if not using --genome)",
                    required=False,
                    group="Reference Genome"
                ),
                PipelineParameter(
                    name="--aligner",
                    type=ParameterType.CHOICE,
                    description="Alignment tool to use",
                    required=False,
                    default="star_salmon",
                    choices=["star_salmon", "star_rsem", "hisat2", "salmon"],
                    group="Alignment"
                ),
                PipelineParameter(
                    name="--pseudo_aligner",
                    type=ParameterType.CHOICE,
                    description="Pseudo-aligner to use (alternative to --aligner)",
                    required=False,
                    choices=["salmon", "kallisto"],
                    group="Alignment"
                ),
                PipelineParameter(
                    name="--trimmer",
                    type=ParameterType.CHOICE,
                    description="Trimming tool to use",
                    required=False,
                    default="trimgalore",
                    choices=["trimgalore", "fastp"],
                    group="Read Trimming"
                ),
                PipelineParameter(
                    name="--skip_trimming",
                    type=ParameterType.BOOLEAN,
                    description="Skip read trimming step",
                    required=False,
                    default=False,
                    group="Read Trimming"
                ),
                PipelineParameter(
                    name="--extra_fastp_args",
                    type=ParameterType.STRING,
                    description="Additional arguments for fastp",
                    required=False,
                    group="Read Trimming"
                ),
            ],
            output_mapping={
                "gene_counts": "quantification.gene_counts",
                "transcript_counts": "quantification.transcript_counts",
                "multiqc_report": "quality_metrics.multiqc",
                "fastqc_html": "quality_metrics.fastqc",
                "alignment_stats": "quality_metrics.alignment",
            },
            recommended_cpus=8,
            recommended_memory_gb=32,
            estimated_runtime_hours=4.0,
        )

        # ===================================================================
        # SINGLE-CELL RNA-SEQ PIPELINE
        # ===================================================================
        self._pipelines["nf-core/scrnaseq"] = PipelineCatalogEntry(
            id="nf-core/scrnaseq",
            name="nf-core Single-Cell RNA-seq",
            version="2.6.0",
            omics_types=[OmicsType.SINGLE_CELL],
            description="Single-cell RNA-seq analysis for 10x, DropSeq, and SmartSeq protocols",
            long_description=(
                "nf-core/scrnaseq is a bioinformatics pipeline for processing single-cell RNA-seq data. "
                "It supports multiple protocols (10x Genomics, DropSeq, SmartSeq) and provides "
                "alignment, quantification, empty droplet detection, and quality control. "
                "Includes multiple aligner options and downstream analysis integration."
            ),
            documentation_url="https://nf-co.re/scrnaseq/2.6.0/",
            repository_url="https://github.com/nf-core/scrnaseq",
            input_format="FASTQ files with samplesheet (CSV)",
            output_format="Count matrices, QC metrics, filtered cells",
            citation=(
                "Ewels PA, Peltzer A, Fillinger S, et al. The nf-core framework for "
                "community-curated bioinformatics pipelines. Nat Biotechnol. 2020;38(3):276-278."
            ),
            tags=["single-cell", "scrna-seq", "10x-genomics", "nf-core"],
            parameters=[
                PipelineParameter(
                    name="--input",
                    type=ParameterType.FILE,
                    description="Path to samplesheet (CSV) with sample information",
                    required=True,
                    example="samplesheet.csv",
                    group="Input/Output"
                ),
                PipelineParameter(
                    name="--outdir",
                    type=ParameterType.DIRECTORY,
                    description="Output directory for results",
                    required=True,
                    example="./results",
                    group="Input/Output"
                ),
                PipelineParameter(
                    name="--protocol",
                    type=ParameterType.CHOICE,
                    description="Single-cell protocol used",
                    required=True,
                    choices=["10XV1", "10XV2", "10XV3", "10XV4", "dropseq", "smartseq", "auto"],
                    example="10XV3",
                    group="Protocol"
                ),
                PipelineParameter(
                    name="--aligner",
                    type=ParameterType.CHOICE,
                    description="Alignment/quantification tool",
                    required=False,
                    default="alevin",
                    choices=["alevin", "star", "kallisto", "cellranger"],
                    group="Alignment"
                ),
                PipelineParameter(
                    name="--genome",
                    type=ParameterType.CHOICE,
                    description="Reference genome identifier",
                    required=False,
                    choices=["GRCh38", "GRCh37", "GRCm39", "GRCm38"],
                    group="Reference Genome"
                ),
                PipelineParameter(
                    name="--fasta",
                    type=ParameterType.FILE,
                    description="Path to genome FASTA file",
                    required=False,
                    group="Reference Genome"
                ),
                PipelineParameter(
                    name="--gtf",
                    type=ParameterType.FILE,
                    description="Path to GTF annotation file",
                    required=False,
                    group="Reference Genome"
                ),
            ],
            output_mapping={
                "counts_matrix": "quantification.counts",
                "filtered_matrix": "quantification.filtered_counts",
                "barcode_whitelist": "quality_metrics.barcodes",
                "empty_droplets": "quality_metrics.droplets",
                "multiqc_report": "quality_metrics.multiqc",
            },
            recommended_cpus=16,
            recommended_memory_gb=64,
            estimated_runtime_hours=6.0,
        )

        # ===================================================================
        # PROTEOMICS LFQ PIPELINE
        # ===================================================================
        self._pipelines["nf-core/proteomicslfq"] = PipelineCatalogEntry(
            id="nf-core/proteomicslfq",
            name="nf-core Proteomics LFQ",
            version="1.0.0",
            omics_types=[OmicsType.PROTEOMICS],
            description="Label-free quantification (LFQ) proteomics analysis",
            long_description=(
                "nf-core/proteomicslfq performs comprehensive proteomics analysis including "
                "conversion to indexed mzML, database search, re-scoring, FDR filtering, "
                "protein inference, and label-free quantification. Includes downstream "
                "statistical analysis with MSstats and quality control with PTXQC."
            ),
            documentation_url="https://nf-co.re/proteomicslfq/1.0.0/",
            repository_url="https://github.com/nf-core/proteomicslfq",
            input_format="Raw mass spectrometry files (mzML, RAW) with SDRF metadata",
            output_format="Protein/peptide quantification, QC reports",
            citation=(
                "Dai C, Füllgrabe A, Pfeuffer J, et al. A proteomics sample metadata "
                "representation for multiomics integration and big data analysis. "
                "Nat Commun. 2021;12:5854."
            ),
            tags=["proteomics", "mass-spectrometry", "lfq", "nf-core"],
            parameters=[
                PipelineParameter(
                    name="--input",
                    type=ParameterType.FILE,
                    description="Path to SDRF (Sample to Data Relation Format) file",
                    required=True,
                    example="sdrf.tsv",
                    group="Input/Output"
                ),
                PipelineParameter(
                    name="--outdir",
                    type=ParameterType.DIRECTORY,
                    description="Output directory for results",
                    required=True,
                    example="./results",
                    group="Input/Output"
                ),
                PipelineParameter(
                    name="--database",
                    type=ParameterType.FILE,
                    description="Path to protein database (FASTA)",
                    required=True,
                    group="Database Search"
                ),
                PipelineParameter(
                    name="--search_engines",
                    type=ParameterType.CHOICE,
                    description="Search engine(s) to use",
                    required=False,
                    default="comet",
                    choices=["comet", "msgf", "xtandem"],
                    group="Database Search"
                ),
                PipelineParameter(
                    name="--enzyme",
                    type=ParameterType.CHOICE,
                    description="Enzyme used for digestion",
                    required=False,
                    default="Trypsin",
                    choices=["Trypsin", "Trypsin/P", "Lys-C", "Arg-C", "Asp-N", "Glu-C"],
                    group="Database Search"
                ),
                PipelineParameter(
                    name="--precursor_mass_tolerance",
                    type=ParameterType.INTEGER,
                    description="Precursor mass tolerance (ppm)",
                    required=False,
                    default=5,
                    group="Database Search"
                ),
                PipelineParameter(
                    name="--fragment_mass_tolerance",
                    type=ParameterType.FLOAT,
                    description="Fragment mass tolerance (Da)",
                    required=False,
                    default=0.03,
                    group="Database Search"
                ),
            ],
            output_mapping={
                "protein_groups": "quantification.proteins",
                "peptides": "quantification.peptides",
                "msstats_results": "statistics.msstats",
                "ptxqc_report": "quality_metrics.ptxqc",
                "multiqc_report": "quality_metrics.multiqc",
            },
            recommended_cpus=16,
            recommended_memory_gb=64,
            estimated_runtime_hours=8.0,
        )

        # ===================================================================
        # METABOLOMICS PIPELINE
        # ===================================================================
        self._pipelines["nf-core/metaboigniter"] = PipelineCatalogEntry(
            id="nf-core/metaboigniter",
            name="nf-core MetaboIGNITER",
            version="2.0.0",
            omics_types=[OmicsType.METABOLOMICS],
            description="Mass spectrometry-based metabolomics pre-processing and analysis",
            long_description=(
                "nf-core/metaboigniter performs comprehensive pre-processing of mass spectrometry "
                "metabolomics data. It performs MS1-based quantification and MS2-based identification "
                "using combinations of different modules. Supports both XCMS and OpenMS workflows."
            ),
            documentation_url="https://nf-co.re/metaboigniter/2.0.0/",
            repository_url="https://github.com/nf-core/metaboigniter",
            input_format="Raw mass spectrometry files (mzML, mzXML) with samplesheet",
            output_format="Metabolite identifications, quantification matrix, QC reports",
            citation=(
                "Pfeuffer J, Bielow C, Wein S, et al. OpenMS 3 enables reproducible analysis "
                "of large-scale mass spectrometry data. Nat Methods. 2024;21:365–367."
            ),
            tags=["metabolomics", "mass-spectrometry", "xcms", "openms", "nf-core"],
            parameters=[
                PipelineParameter(
                    name="--input",
                    type=ParameterType.FILE,
                    description="Path to samplesheet with MS file paths and metadata",
                    required=True,
                    example="samplesheet.csv",
                    group="Input/Output"
                ),
                PipelineParameter(
                    name="--outdir",
                    type=ParameterType.DIRECTORY,
                    description="Output directory for results",
                    required=True,
                    example="./results",
                    group="Input/Output"
                ),
                PipelineParameter(
                    name="--quant_method",
                    type=ParameterType.CHOICE,
                    description="Quantification method",
                    required=False,
                    default="openms",
                    choices=["openms", "xcms"],
                    group="Quantification"
                ),
                PipelineParameter(
                    name="--need_centroiding",
                    type=ParameterType.BOOLEAN,
                    description="Whether data needs centroiding",
                    required=False,
                    default=False,
                    group="Pre-processing"
                ),
                PipelineParameter(
                    name="--perform_identification",
                    type=ParameterType.BOOLEAN,
                    description="Perform metabolite identification",
                    required=False,
                    default=True,
                    group="Identification"
                ),
                PipelineParameter(
                    name="--id_database",
                    type=ParameterType.FILE,
                    description="Path to metabolite database for identification",
                    required=False,
                    group="Identification"
                ),
            ],
            output_mapping={
                "feature_matrix": "quantification.features",
                "identifications": "identification.metabolites",
                "multiqc_report": "quality_metrics.multiqc",
            },
            recommended_cpus=8,
            recommended_memory_gb=32,
            estimated_runtime_hours=6.0,
        )

        # ===================================================================
        # ADDITIONAL USEFUL PIPELINES
        # ===================================================================

        # DIA Proteomics
        self._pipelines["nf-core/diaproteomics"] = PipelineCatalogEntry(
            id="nf-core/diaproteomics",
            name="nf-core DIA Proteomics",
            version="1.2.4",
            omics_types=[OmicsType.PROTEOMICS],
            description="Data-Independent Acquisition (DIA) proteomics analysis",
            long_description=(
                "Automated quantitative analysis pipeline for DIA proteomics mass spectrometry "
                "measurements. Supports library generation and DIA analysis workflows."
            ),
            documentation_url="https://nf-co.re/diaproteomics/1.2.4/",
            repository_url="https://github.com/nf-core/diaproteomics",
            input_format="Raw mass spectrometry files (mzML, RAW)",
            output_format="Protein/peptide quantification, spectral library",
            tags=["proteomics", "dia", "mass-spectrometry", "nf-core"],
            parameters=[
                PipelineParameter(
                    name="--input",
                    type=ParameterType.FILE,
                    description="Path to input samplesheet",
                    required=True,
                    group="Input/Output"
                ),
                PipelineParameter(
                    name="--outdir",
                    type=ParameterType.DIRECTORY,
                    description="Output directory",
                    required=True,
                    group="Input/Output"
                ),
            ],
            output_mapping={},
            recommended_cpus=16,
            recommended_memory_gb=64,
        )

    def list_pipelines(
        self,
        omics_type: Optional[OmicsType] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None,
        enabled_only: bool = True,
    ) -> List[PipelineCatalogEntry]:
        """
        List available pipelines with optional filtering.

        Args:
            omics_type: Filter by omics type
            search: Search in name/description
            tags: Filter by tags
            enabled_only: Only return enabled pipelines

        Returns:
            List of matching pipeline catalog entries
        """
        results = list(self._pipelines.values())

        # Filter by enabled status
        if enabled_only:
            results = [p for p in results if p.enabled]

        # Filter by omics type
        if omics_type:
            results = [p for p in results if omics_type in p.omics_types]

        # Search in name and description
        if search:
            search_lower = search.lower()
            results = [
                p for p in results
                if search_lower in p.name.lower() or search_lower in p.description.lower()
            ]

        # Filter by tags
        if tags:
            results = [
                p for p in results
                if any(tag in p.tags for tag in tags)
            ]

        return results

    def get_pipeline(self, pipeline_id: str) -> Optional[PipelineCatalogEntry]:
        """
        Get a specific pipeline by ID.

        Args:
            pipeline_id: Pipeline identifier

        Returns:
            Pipeline catalog entry or None if not found
        """
        return self._pipelines.get(pipeline_id)

    def get_pipeline_parameters(self, pipeline_id: str) -> Optional[List[PipelineParameter]]:
        """
        Get parameters for a specific pipeline.

        Args:
            pipeline_id: Pipeline identifier

        Returns:
            List of pipeline parameters or None if pipeline not found
        """
        pipeline = self.get_pipeline(pipeline_id)
        return pipeline.parameters if pipeline else None

    def add_pipeline(self, pipeline: PipelineCatalogEntry) -> None:
        """
        Add a custom pipeline to the registry.

        Args:
            pipeline: Pipeline catalog entry to add
        """
        self._pipelines[pipeline.id] = pipeline

    def remove_pipeline(self, pipeline_id: str) -> bool:
        """
        Remove a pipeline from the registry.

        Args:
            pipeline_id: Pipeline identifier

        Returns:
            True if removed, False if not found
        """
        if pipeline_id in self._pipelines:
            del self._pipelines[pipeline_id]
            return True
        return False

    def get_pipelines_by_omics_type(self, omics_type: OmicsType) -> List[PipelineCatalogEntry]:
        """
        Get all pipelines for a specific omics type.

        Args:
            omics_type: Omics type to filter by

        Returns:
            List of matching pipelines
        """
        return self.list_pipelines(omics_type=omics_type)


# Singleton instance
_registry: Optional[PipelineRegistry] = None


def get_pipeline_registry() -> PipelineRegistry:
    """
    Get the global pipeline registry instance.

    Returns:
        PipelineRegistry singleton
    """
    global _registry
    if _registry is None:
        _registry = PipelineRegistry()
    return _registry
