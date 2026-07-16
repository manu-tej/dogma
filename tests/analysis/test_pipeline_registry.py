"""
Tests for pipeline registry and matching logic.
"""

import pytest

from quration.analysis.models import PipelineType
from quration.analysis.pipeline_registry import (
    GenomeRegistry,
    PipelineRegistry,
    normalize_library_strategy,
)


class TestPipelineRegistry:
    """Test pipeline registry functionality."""

    def test_get_pipeline(self):
        """Test retrieving pipeline metadata."""
        pipeline = PipelineRegistry.get_pipeline(PipelineType.RNASEQ)

        assert pipeline is not None
        assert pipeline.name == "nf-core/rnaseq"
        assert pipeline.pipeline_type == PipelineType.RNASEQ
        assert "RNA-Seq" in pipeline.supported_library_strategies

    def test_list_all_pipelines(self):
        """Test listing all pipelines."""
        pipelines = PipelineRegistry.list_all_pipelines()

        assert len(pipelines) > 0
        assert any(p.pipeline_type == PipelineType.RNASEQ for p in pipelines)
        assert any(p.pipeline_type == PipelineType.FETCHNGS for p in pipelines)

    def test_match_pipelines_rnaseq(self):
        """Test matching RNA-seq data to pipelines."""
        available_metadata = {"organism", "fastq_files"}
        matches = PipelineRegistry.match_pipelines("RNA-Seq", available_metadata)

        assert len(matches) > 0
        assert any(m.pipeline_type == PipelineType.RNASEQ for m in matches)

    def test_match_pipelines_chipseq(self):
        """Test matching ChIP-seq data to pipelines."""
        available_metadata = {"organism", "fastq_files"}
        matches = PipelineRegistry.match_pipelines("ChIP-Seq", available_metadata)

        assert len(matches) > 0
        assert any(m.pipeline_type == PipelineType.CHIPSEQ for m in matches)

    def test_match_pipelines_no_metadata(self):
        """Test matching with insufficient metadata."""
        available_metadata = set()  # No metadata
        matches = PipelineRegistry.match_pipelines("RNA-Seq", available_metadata)

        # Should not match any pipelines due to missing required metadata
        assert len(matches) == 0

    def test_get_pipeline_for_strategy(self):
        """Test getting pipeline for a specific strategy."""
        pipeline = PipelineRegistry.get_pipeline_for_strategy("RNA-Seq")

        assert pipeline is not None
        assert pipeline.pipeline_type == PipelineType.RNASEQ

    def test_get_pipeline_for_unknown_strategy(self):
        """Test getting pipeline for unknown strategy."""
        pipeline = PipelineRegistry.get_pipeline_for_strategy("UNKNOWN-SEQ")

        assert pipeline is None


class TestLibraryStrategyNormalization:
    """Test library strategy normalization."""

    def test_normalize_rnaseq_variants(self):
        """Test normalizing various RNA-seq naming conventions."""
        assert normalize_library_strategy("rna-seq") == "RNA-Seq"
        assert normalize_library_strategy("rnaseq") == "RNA-Seq"
        assert normalize_library_strategy("RNA SEQ") == "RNA-Seq"
        assert normalize_library_strategy("mrna-seq") == "mRNA-Seq"

    def test_normalize_chipseq_variants(self):
        """Test normalizing ChIP-seq variants."""
        assert normalize_library_strategy("chip-seq") == "ChIP-Seq"
        assert normalize_library_strategy("chipseq") == "ChIP-Seq"
        assert normalize_library_strategy("CHIP SEQ") == "ChIP-Seq"

    def test_normalize_atacseq_variants(self):
        """Test normalizing ATAC-seq variants."""
        assert normalize_library_strategy("atac-seq") == "ATAC-seq"
        assert normalize_library_strategy("atacseq") == "ATAC-seq"

    def test_normalize_wgs_variants(self):
        """Test normalizing WGS variants."""
        assert normalize_library_strategy("wgs") == "WGS"
        assert normalize_library_strategy("whole genome") == "WGS"

    def test_normalize_unknown_strategy(self):
        """Test normalizing unknown strategy returns original."""
        assert normalize_library_strategy("UNKNOWN-SEQ") == "UNKNOWN-SEQ"


class TestGenomeRegistry:
    """Test genome registry functionality."""

    def test_get_default_genome_human(self):
        """Test getting default genome for human."""
        genome = GenomeRegistry.get_default_genome("Homo sapiens")

        assert genome is not None
        assert genome.name == "GRCh38"
        assert genome.organism == "Homo sapiens"
        assert genome.igenomes_ref == "GRCh38"

    def test_get_default_genome_mouse(self):
        """Test getting default genome for mouse."""
        genome = GenomeRegistry.get_default_genome("Mus musculus")

        assert genome is not None
        assert genome.name == "GRCm39"
        assert genome.organism == "Mus musculus"

    def test_get_default_genome_unknown(self):
        """Test getting default genome for unknown organism."""
        genome = GenomeRegistry.get_default_genome("Unknown organism")

        assert genome is None

    def test_get_specific_genome_version(self):
        """Test getting specific genome version."""
        genome = GenomeRegistry.get_genome("Homo sapiens", "GRCh37")

        assert genome is not None
        assert genome.name == "GRCh37"
        assert genome.organism == "Homo sapiens"

    def test_get_nonexistent_genome_version(self):
        """Test getting non-existent genome version."""
        genome = GenomeRegistry.get_genome("Homo sapiens", "GRCh99")

        assert genome is None

    def test_all_model_organisms_have_genomes(self):
        """Test that all major model organisms have genomes defined."""
        organisms = [
            "Homo sapiens",
            "Mus musculus",
            "Rattus norvegicus",
            "Danio rerio",
            "Drosophila melanogaster",
            "Caenorhabditis elegans",
        ]

        for organism in organisms:
            genome = GenomeRegistry.get_default_genome(organism)
            assert genome is not None, f"No genome found for {organism}"
