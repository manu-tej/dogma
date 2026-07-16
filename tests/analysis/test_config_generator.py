"""
Tests for configuration generation.
"""

import csv
import pytest
from pathlib import Path

from quration.analysis.config_generator import ConfigGenerator
from quration.analysis.models import ComputeEnvironment, PipelineType


class TestConfigGenerator:
    """Test configuration generator."""

    def test_create_config_generator(self):
        """Test creating a config generator."""
        gen = ConfigGenerator()

        assert gen.compute_env == ComputeEnvironment.LOCAL

    def test_create_with_custom_env(self):
        """Test creating with custom compute environment."""
        gen = ConfigGenerator(compute_env=ComputeEnvironment.AWS)

        assert gen.compute_env == ComputeEnvironment.AWS


class TestFetchNGSConfig:
    """Test fetchngs configuration generation."""

    def test_generate_fetchngs_config(self, tmp_output_dir, sample_sra_ids):
        """Test generating fetchngs configuration."""
        gen = ConfigGenerator()

        config = gen.generate_fetchngs_config(
            sra_ids=sample_sra_ids,
            output_dir=tmp_output_dir,
        )

        assert config.pipeline_type == PipelineType.FETCHNGS
        assert config.parameters.download_method == "ftp"
        assert (tmp_output_dir / "sra_ids.csv").exists()

    def test_fetchngs_config_creates_ids_file(self, tmp_output_dir, sample_sra_ids):
        """Test that SRA IDs file is created correctly."""
        gen = ConfigGenerator()

        config = gen.generate_fetchngs_config(
            sra_ids=sample_sra_ids,
            output_dir=tmp_output_dir,
        )

        ids_file = tmp_output_dir / "sra_ids.csv"
        assert ids_file.exists()

        # Verify contents
        with open(ids_file) as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 3
            assert rows[0][0] == "SRR123456"

    def test_fetchngs_config_custom_method(self, tmp_output_dir, sample_sra_ids):
        """Test fetchngs with custom download method."""
        gen = ConfigGenerator()

        config = gen.generate_fetchngs_config(
            sra_ids=sample_sra_ids,
            output_dir=tmp_output_dir,
            download_method="aspera",
            for_pipeline="rnaseq",
        )

        assert config.parameters.download_method == "aspera"
        assert config.parameters.nf_core_pipeline == "rnaseq"


class TestRNASeqConfig:
    """Test RNA-seq configuration generation."""

    def test_generate_rnaseq_config(
        self, sample_analysis_plan, sample_curated_dataset, mock_fastq_dir, tmp_output_dir
    ):
        """Test generating RNA-seq configuration."""
        gen = ConfigGenerator()

        config = gen.generate_rnaseq_config(
            plan=sample_analysis_plan,
            fastq_dir=mock_fastq_dir,
            output_dir=tmp_output_dir,
            curated_dataset=sample_curated_dataset,
        )

        assert config.pipeline_type == PipelineType.RNASEQ
        assert config.parameters.genome == "GRCh38"
        assert config.parameters.aligner == "star_salmon"

    def test_rnaseq_config_creates_samplesheet(
        self, sample_analysis_plan, sample_curated_dataset, mock_fastq_dir, tmp_output_dir
    ):
        """Test that samplesheet is created."""
        gen = ConfigGenerator()

        config = gen.generate_rnaseq_config(
            plan=sample_analysis_plan,
            fastq_dir=mock_fastq_dir,
            output_dir=tmp_output_dir,
            curated_dataset=sample_curated_dataset,
        )

        samplesheet = tmp_output_dir / "samplesheet.csv"
        assert samplesheet.exists()

        # Verify samplesheet content
        with open(samplesheet) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 3  # 3 samples
            assert rows[0]["sample"] == "GSM111111"
            assert "fastq_1" in rows[0]
            assert "fastq_2" in rows[0]

    def test_rnaseq_config_custom_aligner(
        self, sample_analysis_plan, sample_curated_dataset, mock_fastq_dir, tmp_output_dir
    ):
        """Test RNA-seq config with custom aligner."""
        gen = ConfigGenerator()

        config = gen.generate_rnaseq_config(
            plan=sample_analysis_plan,
            fastq_dir=mock_fastq_dir,
            output_dir=tmp_output_dir,
            curated_dataset=sample_curated_dataset,
            aligner="hisat2",
        )

        assert config.parameters.aligner == "hisat2"


class TestSamplesheetCreation:
    """Test samplesheet creation functionality."""

    def test_create_rnaseq_samplesheet(
        self, sample_curated_dataset, mock_fastq_dir, tmp_output_dir
    ):
        """Test creating RNA-seq samplesheet."""
        gen = ConfigGenerator()
        output_path = tmp_output_dir / "test_samplesheet.csv"

        gen._create_rnaseq_samplesheet(
            curated_dataset=sample_curated_dataset,
            fastq_dir=mock_fastq_dir,
            output_path=output_path,
            is_paired_end=True,
        )

        assert output_path.exists()

        # Read and verify
        with open(output_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            assert len(rows) == 3
            assert "sample" in rows[0]
            assert "fastq_1" in rows[0]
            assert "fastq_2" in rows[0]
            assert "strandedness" in rows[0]

    def test_create_single_end_samplesheet(
        self, sample_curated_dataset, mock_fastq_dir, tmp_output_dir
    ):
        """Test creating single-end samplesheet."""
        gen = ConfigGenerator()
        output_path = tmp_output_dir / "test_samplesheet.csv"

        gen._create_rnaseq_samplesheet(
            curated_dataset=sample_curated_dataset,
            fastq_dir=mock_fastq_dir,
            output_path=output_path,
            is_paired_end=False,
        )

        # Read and verify
        with open(output_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)

            # Single-end should not have fastq_2
            assert "fastq_1" in rows[0]
            assert "fastq_2" not in rows[0]


class TestContrastFile:
    """Test contrast file generation."""

    def test_generate_contrast_file(self, sample_analysis_plan, tmp_output_dir):
        """Test generating contrast file for differential analysis."""
        gen = ConfigGenerator()
        contrast_file = tmp_output_dir / "contrasts.csv"

        gen.generate_contrast_file(sample_analysis_plan, contrast_file)

        assert contrast_file.exists()

        # Read and verify
        with open(contrast_file) as f:
            reader = csv.reader(f)
            rows = list(reader)

            assert len(rows) == 2  # Header + 1 comparison
            assert rows[0] == ["comparison", "condition_a", "condition_b"]
            assert rows[1][0] == "tumor_vs_normal"

    def test_contrast_file_no_comparisons(self, tmp_output_dir):
        """Test contrast file with no comparison groups."""
        from quration.analysis.models import AnalysisPlan, PipelineType, ReferenceGenome

        plan = AnalysisPlan(
            dataset_id="TEST",
            dataset_title="Test",
            recommended_pipelines=[PipelineType.RNASEQ],
            primary_pipeline=PipelineType.RNASEQ,
            organism="Homo sapiens",
            library_strategy="RNA-Seq",
            sample_count=3,
            has_paired_end=True,
            suggested_genome=ReferenceGenome(name="GRCh38", organism="Homo sapiens"),
            rationale="Test",
            expected_outputs=[],
            comparison_groups=[],  # No comparisons
        )

        gen = ConfigGenerator()
        contrast_file = tmp_output_dir / "contrasts.csv"

        gen.generate_contrast_file(plan, contrast_file)

        # File should not be created if no comparisons
        assert not contrast_file.exists()


class TestCustomConfig:
    """Test custom Nextflow config generation."""

    def test_generate_custom_config(self, tmp_output_dir):
        """Test generating custom Nextflow config."""
        from quration.analysis.models import PipelineConfig, PipelineType, RNASeqParameters

        params = RNASeqParameters(
            input="samplesheet.csv",
            outdir="/output",
            genome="GRCh38",
        )

        config = PipelineConfig(
            pipeline_type=PipelineType.RNASEQ,
            parameters=params,
            max_cpus=16,
            max_memory="64.GB",
        )

        gen = ConfigGenerator()
        config_file = tmp_output_dir / "nextflow.config"

        gen.generate_custom_config(config, config_file)

        assert config_file.exists()

        # Read and verify
        content = config_file.read_text()
        assert "cpus = 16" in content
        assert "memory = '64.GB'" in content

    def test_custom_config_with_parameters(self, tmp_output_dir):
        """Test custom config with additional parameters."""
        from quration.analysis.models import PipelineConfig, PipelineType, RNASeqParameters

        params = RNASeqParameters(
            input="samplesheet.csv",
            outdir="/output",
        )

        config = PipelineConfig(
            pipeline_type=PipelineType.RNASEQ,
            parameters=params,
        )

        gen = ConfigGenerator()
        config_file = tmp_output_dir / "nextflow.config"

        custom_params = {
            "email": "user@example.com",
            "save_reference": True,
        }

        gen.generate_custom_config(config, config_file, custom_params=custom_params)

        content = config_file.read_text()
        assert "email = 'user@example.com'" in content
        assert "save_reference = True" in content


class TestProfileSelection:
    """Test Nextflow profile selection."""

    def test_local_profile(self):
        """Test local environment uses docker profile."""
        gen = ConfigGenerator(compute_env=ComputeEnvironment.LOCAL)
        profiles = gen._get_default_profiles()

        assert "docker" in profiles

    def test_aws_profile(self):
        """Test AWS environment uses awsbatch profile."""
        gen = ConfigGenerator(compute_env=ComputeEnvironment.AWS)
        profiles = gen._get_default_profiles()

        assert "awsbatch" in profiles

    def test_slurm_profile(self):
        """Test SLURM environment uses slurm profile."""
        gen = ConfigGenerator(compute_env=ComputeEnvironment.HPC_SLURM)
        profiles = gen._get_default_profiles()

        assert "slurm" in profiles
