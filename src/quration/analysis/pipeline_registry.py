"""
Registry of nf-core pipelines with metadata and selection logic.

This module maintains a registry of supported nf-core pipelines and provides
logic to match curated dataset metadata to appropriate analysis pipelines.
"""

from typing import Dict, List, Optional, Set

from .models import PipelineType, ReferenceGenome


class PipelineMetadata:
    """Metadata for an nf-core pipeline."""

    def __init__(
        self,
        pipeline_type: PipelineType,
        name: str,
        description: str,
        supported_library_strategies: Set[str],
        required_metadata_fields: Set[str],
        latest_version: str,
        homepage_url: str,
        typical_use_cases: List[str],
    ):
        self.pipeline_type = pipeline_type
        self.name = name
        self.description = description
        self.supported_library_strategies = supported_library_strategies
        self.required_metadata_fields = required_metadata_fields
        self.latest_version = latest_version
        self.homepage_url = homepage_url
        self.typical_use_cases = typical_use_cases


class GenomeRegistry:
    """Registry of reference genomes for common model organisms."""

    GENOMES = {
        # Human
        "Homo sapiens": {
            "default": "GRCh38",
            "genomes": {
                "GRCh38": ReferenceGenome(
                    name="GRCh38",
                    organism="Homo sapiens",
                    igenomes_ref="GRCh38",
                ),
                "GRCh37": ReferenceGenome(
                    name="GRCh37",
                    organism="Homo sapiens",
                    igenomes_ref="GRCh37",
                ),
            },
        },
        # Mouse
        "Mus musculus": {
            "default": "GRCm39",
            "genomes": {
                "GRCm39": ReferenceGenome(
                    name="GRCm39",
                    organism="Mus musculus",
                    igenomes_ref="GRCm39",
                ),
                "GRCm38": ReferenceGenome(
                    name="GRCm38",
                    organism="Mus musculus",
                    igenomes_ref="GRCm38",
                ),
            },
        },
        # Rat
        "Rattus norvegicus": {
            "default": "Rnor_6.0",
            "genomes": {
                "Rnor_6.0": ReferenceGenome(
                    name="Rnor_6.0",
                    organism="Rattus norvegicus",
                    igenomes_ref="Rnor_6.0",
                ),
            },
        },
        # Zebrafish
        "Danio rerio": {
            "default": "GRCz11",
            "genomes": {
                "GRCz11": ReferenceGenome(
                    name="GRCz11",
                    organism="Danio rerio",
                    igenomes_ref="GRCz11",
                ),
            },
        },
        # Drosophila
        "Drosophila melanogaster": {
            "default": "BDGP6",
            "genomes": {
                "BDGP6": ReferenceGenome(
                    name="BDGP6",
                    organism="Drosophila melanogaster",
                    igenomes_ref="BDGP6",
                ),
            },
        },
        # C. elegans
        "Caenorhabditis elegans": {
            "default": "WBcel235",
            "genomes": {
                "WBcel235": ReferenceGenome(
                    name="WBcel235",
                    organism="Caenorhabditis elegans",
                    igenomes_ref="WBcel235",
                ),
            },
        },
        # Arabidopsis
        "Arabidopsis thaliana": {
            "default": "TAIR10",
            "genomes": {
                "TAIR10": ReferenceGenome(
                    name="TAIR10",
                    organism="Arabidopsis thaliana",
                    igenomes_ref="TAIR10",
                ),
            },
        },
        # S. cerevisiae
        "Saccharomyces cerevisiae": {
            "default": "R64-1-1",
            "genomes": {
                "R64-1-1": ReferenceGenome(
                    name="R64-1-1",
                    organism="Saccharomyces cerevisiae",
                    igenomes_ref="R64-1-1",
                ),
            },
        },
    }

    @classmethod
    def get_default_genome(cls, organism: str) -> Optional[ReferenceGenome]:
        """Get the default reference genome for an organism."""
        if organism in cls.GENOMES:
            default_name = cls.GENOMES[organism]["default"]
            return cls.GENOMES[organism]["genomes"][default_name]
        return None

    @classmethod
    def get_genome(cls, organism: str, genome_name: str) -> Optional[ReferenceGenome]:
        """Get a specific genome version for an organism."""
        if organism in cls.GENOMES:
            return cls.GENOMES[organism]["genomes"].get(genome_name)
        return None


class PipelineRegistry:
    """Registry of supported nf-core pipelines."""

    PIPELINES: Dict[PipelineType, PipelineMetadata] = {
        PipelineType.FETCHNGS: PipelineMetadata(
            pipeline_type=PipelineType.FETCHNGS,
            name="nf-core/fetchngs",
            description="Download FASTQ files from public databases (SRA, ENA, DDBJ)",
            supported_library_strategies={"*"},  # Works with all
            required_metadata_fields={"accession_ids"},
            latest_version="1.12.0",
            homepage_url="https://nf-co.re/fetchngs",
            typical_use_cases=[
                "Download raw sequencing data from SRA/ENA",
                "Prepare data for downstream nf-core pipelines",
            ],
        ),
        PipelineType.RNASEQ: PipelineMetadata(
            pipeline_type=PipelineType.RNASEQ,
            name="nf-core/rnaseq",
            description="RNA sequencing analysis: alignment, quantification, QC, and differential expression",
            supported_library_strategies={"RNA-Seq", "mRNA-Seq", "total RNA-Seq"},
            required_metadata_fields={"organism", "fastq_files"},
            latest_version="3.21.0",
            homepage_url="https://nf-co.re/rnaseq",
            typical_use_cases=[
                "Gene expression quantification",
                "Differential expression analysis",
                "Transcript isoform analysis",
                "Quality control of RNA-seq data",
            ],
        ),
        PipelineType.SAREK: PipelineMetadata(
            pipeline_type=PipelineType.SAREK,
            name="nf-core/sarek",
            description="Variant calling for WGS, WES, and targeted sequencing",
            supported_library_strategies={
                "WGS",
                "WXS",
                "WES",
                "Targeted-Capture",
                "AMPLICON",
            },
            required_metadata_fields={"organism", "fastq_files"},
            latest_version="3.4.0",
            homepage_url="https://nf-co.re/sarek",
            typical_use_cases=[
                "Germline variant calling",
                "Somatic variant calling",
                "CNV detection",
                "Structural variant calling",
            ],
        ),
        PipelineType.CHIPSEQ: PipelineMetadata(
            pipeline_type=PipelineType.CHIPSEQ,
            name="nf-core/chipseq",
            description="ChIP-seq analysis: peak calling and differential binding",
            supported_library_strategies={"ChIP-Seq", "ChIP-seq"},
            required_metadata_fields={"organism", "fastq_files"},
            latest_version="2.0.0",
            homepage_url="https://nf-co.re/chipseq",
            typical_use_cases=[
                "Transcription factor binding sites",
                "Histone modification profiling",
                "Peak calling and annotation",
                "Differential binding analysis",
            ],
        ),
        PipelineType.ATACSEQ: PipelineMetadata(
            pipeline_type=PipelineType.ATACSEQ,
            name="nf-core/atacseq",
            description="ATAC-seq analysis: chromatin accessibility profiling",
            supported_library_strategies={"ATAC-seq", "ATAC-Seq"},
            required_metadata_fields={"organism", "fastq_files"},
            latest_version="2.1.2",
            homepage_url="https://nf-co.re/atacseq",
            typical_use_cases=[
                "Chromatin accessibility profiling",
                "Open chromatin regions identification",
                "Transcription factor footprinting",
            ],
        ),
        PipelineType.SCRNASEQ: PipelineMetadata(
            pipeline_type=PipelineType.SCRNASEQ,
            name="nf-core/scrnaseq",
            description="Single-cell RNA-seq analysis",
            supported_library_strategies={"scRNA-Seq", "10x", "Drop-Seq"},
            required_metadata_fields={"organism", "fastq_files"},
            latest_version="2.7.1",
            homepage_url="https://nf-co.re/scrnaseq",
            typical_use_cases=[
                "Single-cell gene expression quantification",
                "Cell type identification",
                "Clustering and visualization",
            ],
        ),
        PipelineType.METHYLSEQ: PipelineMetadata(
            pipeline_type=PipelineType.METHYLSEQ,
            name="nf-core/methylseq",
            description="Bisulfite sequencing analysis for DNA methylation",
            supported_library_strategies={
                "Bisulfite-Seq",
                "WGBS",
                "RRBS",
                "MBD-Seq",
            },
            required_metadata_fields={"organism", "fastq_files"},
            latest_version="2.6.0",
            homepage_url="https://nf-co.re/methylseq",
            typical_use_cases=[
                "DNA methylation profiling",
                "Differential methylation analysis",
                "CpG island analysis",
            ],
        ),
    }

    @classmethod
    def get_pipeline(cls, pipeline_type: PipelineType) -> Optional[PipelineMetadata]:
        """Get metadata for a specific pipeline."""
        return cls.PIPELINES.get(pipeline_type)

    @classmethod
    def match_pipelines(
        cls, library_strategy: str, available_metadata: Set[str]
    ) -> List[PipelineMetadata]:
        """
        Match pipelines based on library strategy and available metadata.

        Args:
            library_strategy: The library strategy from curated metadata
            available_metadata: Set of available metadata field names

        Returns:
            List of matching pipeline metadata, sorted by relevance
        """
        matches = []

        for pipeline in cls.PIPELINES.values():
            # Skip fetchngs in matching (it's always available)
            if pipeline.pipeline_type == PipelineType.FETCHNGS:
                continue

            # Check if library strategy matches
            if "*" in pipeline.supported_library_strategies:
                strategy_match = True
            else:
                strategy_match = library_strategy in pipeline.supported_library_strategies

            # Check if required metadata is available
            metadata_match = pipeline.required_metadata_fields.issubset(
                available_metadata
            )

            if strategy_match and metadata_match:
                matches.append(pipeline)

        return matches

    @classmethod
    def list_all_pipelines(cls) -> List[PipelineMetadata]:
        """List all available pipelines."""
        return list(cls.PIPELINES.values())

    @classmethod
    def get_pipeline_for_strategy(cls, library_strategy: str) -> Optional[PipelineMetadata]:
        """Get the most appropriate pipeline for a library strategy."""
        matches = cls.match_pipelines(library_strategy, {"organism", "fastq_files"})
        return matches[0] if matches else None


def normalize_library_strategy(strategy: str) -> str:
    """
    Normalize library strategy names to match pipeline registry.

    Handles common variations and aliases.
    """
    strategy_mapping = {
        # RNA-Seq variants
        "rna-seq": "RNA-Seq",
        "rna seq": "RNA-Seq",
        "rnaseq": "RNA-Seq",
        "mrna-seq": "mRNA-Seq",
        "mrna seq": "mRNA-Seq",
        "total rna": "total RNA-Seq",
        # Variant calling
        "wgs": "WGS",
        "whole genome": "WGS",
        "wes": "WES",
        "wxs": "WXS",
        "exome": "WES",
        "whole exome": "WES",
        # ChIP-Seq
        "chip-seq": "ChIP-Seq",
        "chip seq": "ChIP-Seq",
        "chipseq": "ChIP-Seq",
        # ATAC-Seq
        "atac-seq": "ATAC-seq",
        "atac seq": "ATAC-seq",
        "atacseq": "ATAC-seq",
        # Single-cell
        "scrna-seq": "scRNA-Seq",
        "scrna seq": "scRNA-Seq",
        "single cell rna": "scRNA-Seq",
        "10x": "10x",
        # Methylation
        "bisulfite-seq": "Bisulfite-Seq",
        "bisulfite seq": "Bisulfite-Seq",
        "wgbs": "WGBS",
        "rrbs": "RRBS",
    }

    normalized = strategy_mapping.get(strategy.lower(), strategy)
    return normalized
