"""
Tests for analysis module Pydantic models.
"""

import pytest
from datetime import datetime
from pathlib import Path

from quration.analysis.models import (
    AnalysisPlan,
    ComparisonGroup,
    ComputeEnvironment,
    ExecutionResult,
    ExecutionStatus,
    FetchNGSParameters,
    PipelineConfig,
    PipelineType,
    ReferenceGenome,
    RNASeqParameters,
    SampleSheet,
)


class TestReferenceGenome:
    """Test ReferenceGenome model."""

    def test_create_reference_genome(self):
        """Test creating a reference genome."""
        genome = ReferenceGenome(
            name="GRCh38",
            organism="Homo sapiens",
            igenomes_ref="GRCh38",
        )

        assert genome.name == "GRCh38"
        assert genome.organism == "Homo sapiens"
        assert genome.igenomes_ref == "GRCh38"

    def test_reference_genome_optional_fields(self):
        """Test reference genome with optional fields."""
        genome = ReferenceGenome(
            name="GRCh38",
            organism="Homo sapiens",
            fasta_url="https://example.com/genome.fa",
            gtf_url="https://example.com/genes.gtf",
        )

        assert genome.fasta_url == "https://example.com/genome.fa"
        assert genome.gtf_url == "https://example.com/genes.gtf"


class TestComparisonGroup:
    """Test ComparisonGroup model."""

    def test_create_comparison_group(self):
        """Test creating a comparison group."""
        group = ComparisonGroup(
            name="tumor_vs_normal",
            condition_a="tumor",
            condition_b="normal",
            sample_ids_a=["sample1", "sample2"],
            sample_ids_b=["sample3", "sample4"],
        )

        assert group.name == "tumor_vs_normal"
        assert len(group.sample_ids_a) == 2
        assert len(group.sample_ids_b) == 2


class TestRNASeqParameters:
    """Test RNASeqParameters model."""

    def test_create_rnaseq_parameters(self):
        """Test creating RNA-seq parameters."""
        params = RNASeqParameters(
            input="samplesheet.csv",
            outdir="/output",
            genome="GRCh38",
        )

        assert params.input == "samplesheet.csv"
        assert params.outdir == "/output"
        assert params.genome == "GRCh38"
        assert params.aligner == "star_salmon"  # Default

    def test_rnaseq_parameters_with_comparisons(self):
        """Test RNA-seq parameters with comparison groups."""
        comparison = ComparisonGroup(
            name="test",
            condition_a="A",
            condition_b="B",
            sample_ids_a=["s1"],
            sample_ids_b=["s2"],
        )

        params = RNASeqParameters(
            input="samplesheet.csv",
            outdir="/output",
            genome="GRCh38",
            comparisons=[comparison],
        )

        assert params.comparisons is not None
        assert len(params.comparisons) == 1
        assert params.comparisons[0].name == "test"

    def test_rnaseq_parameters_custom_aligner(self):
        """Test RNA-seq parameters with custom aligner."""
        params = RNASeqParameters(
            input="samplesheet.csv",
            outdir="/output",
            genome="GRCh38",
            aligner="hisat2",
        )

        assert params.aligner == "hisat2"


class TestFetchNGSParameters:
    """Test FetchNGSParameters model."""

    def test_create_fetchngs_parameters(self):
        """Test creating fetchngs parameters."""
        params = FetchNGSParameters(
            input="ids.csv",
            outdir="/output",
        )

        assert params.input == "ids.csv"
        assert params.outdir == "/output"
        assert params.download_method == "ftp"  # Default

    def test_fetchngs_parameters_custom_method(self):
        """Test fetchngs with custom download method."""
        params = FetchNGSParameters(
            input="ids.csv",
            outdir="/output",
            download_method="aspera",
            nf_core_pipeline="rnaseq",
        )

        assert params.download_method == "aspera"
        assert params.nf_core_pipeline == "rnaseq"


class TestPipelineConfig:
    """Test PipelineConfig model."""

    def test_create_pipeline_config(self):
        """Test creating a pipeline configuration."""
        params = RNASeqParameters(
            input="samplesheet.csv",
            outdir="/output",
            genome="GRCh38",
        )

        config = PipelineConfig(
            pipeline_type=PipelineType.RNASEQ,
            parameters=params,
        )

        assert config.pipeline_type == PipelineType.RNASEQ
        assert config.compute_env == ComputeEnvironment.LOCAL  # Default
        assert "docker" in config.profile  # Default profile

    def test_pipeline_config_with_resources(self):
        """Test pipeline config with resource limits."""
        params = RNASeqParameters(
            input="samplesheet.csv",
            outdir="/output",
        )

        config = PipelineConfig(
            pipeline_type=PipelineType.RNASEQ,
            parameters=params,
            max_cpus=32,
            max_memory="128.GB",
            max_time="48.h",
        )

        assert config.max_cpus == 32
        assert config.max_memory == "128.GB"
        assert config.max_time == "48.h"


class TestAnalysisPlan:
    """Test AnalysisPlan model."""

    def test_create_analysis_plan(self, sample_analysis_plan):
        """Test creating an analysis plan."""
        plan = sample_analysis_plan

        assert plan.dataset_id == "GSE123456"
        assert plan.primary_pipeline == PipelineType.RNASEQ
        assert plan.organism == "Homo sapiens"
        assert plan.sample_count == 3
        assert len(plan.comparison_groups) == 1

    def test_analysis_plan_with_multiple_pipelines(self):
        """Test analysis plan with multiple recommended pipelines."""
        plan = AnalysisPlan(
            dataset_id="GSE123456",
            dataset_title="Test",
            recommended_pipelines=[PipelineType.RNASEQ, PipelineType.CHIPSEQ],
            primary_pipeline=PipelineType.RNASEQ,
            organism="Homo sapiens",
            library_strategy="RNA-Seq",
            sample_count=5,
            has_paired_end=True,
            suggested_genome=ReferenceGenome(
                name="GRCh38",
                organism="Homo sapiens",
            ),
            rationale="Test rationale",
            expected_outputs=["Output 1", "Output 2"],
        )

        assert len(plan.recommended_pipelines) == 2
        assert PipelineType.RNASEQ in plan.recommended_pipelines
        assert PipelineType.CHIPSEQ in plan.recommended_pipelines

    def test_analysis_plan_with_sra_ids(self):
        """Test analysis plan with SRA IDs."""
        plan = AnalysisPlan(
            dataset_id="GSE123456",
            dataset_title="Test",
            recommended_pipelines=[PipelineType.RNASEQ],
            primary_pipeline=PipelineType.RNASEQ,
            organism="Homo sapiens",
            library_strategy="RNA-Seq",
            sample_count=3,
            has_paired_end=True,
            suggested_genome=ReferenceGenome(name="GRCh38", organism="Homo sapiens"),
            rationale="Test",
            expected_outputs=["Output"],
            sra_ids=["SRR123456", "SRR123457"],
            requires_download=False,
        )

        assert len(plan.sra_ids) == 2
        assert not plan.requires_download


class TestExecutionResult:
    """Test ExecutionResult model."""

    def test_create_execution_result(self):
        """Test creating an execution result."""
        started = datetime.now()

        result = ExecutionResult(
            pipeline_type=PipelineType.RNASEQ,
            dataset_id="GSE123456",
            status=ExecutionStatus.COMPLETED,
            started_at=started,
            work_dir="/work",
            output_dir="/output",
        )

        assert result.pipeline_type == PipelineType.RNASEQ
        assert result.status == ExecutionStatus.COMPLETED
        assert result.started_at == started

    def test_execution_result_duration_calculation(self):
        """Test automatic duration calculation."""
        started = datetime(2024, 1, 1, 10, 0, 0)
        completed = datetime(2024, 1, 1, 12, 0, 0)  # 2 hours later

        result = ExecutionResult(
            pipeline_type=PipelineType.RNASEQ,
            dataset_id="GSE123456",
            status=ExecutionStatus.COMPLETED,
            started_at=started,
            completed_at=completed,
            work_dir="/work",
            output_dir="/output",
        )

        # Duration should be 2 hours = 7200 seconds
        assert result.duration_seconds == 7200.0

    def test_execution_result_with_error(self):
        """Test execution result with error information."""
        result = ExecutionResult(
            pipeline_type=PipelineType.RNASEQ,
            dataset_id="GSE123456",
            status=ExecutionStatus.FAILED,
            started_at=datetime.now(),
            work_dir="/work",
            output_dir="/output",
            error_message="Pipeline failed due to memory error",
            exit_code=137,
        )

        assert result.status == ExecutionStatus.FAILED
        assert result.error_message == "Pipeline failed due to memory error"
        assert result.exit_code == 137


class TestSampleSheet:
    """Test SampleSheet model."""

    def test_create_samplesheet(self):
        """Test creating a samplesheet."""
        samples = [
            {
                "sample": "sample1",
                "fastq_1": "/path/to/sample1_1.fastq.gz",
                "fastq_2": "/path/to/sample1_2.fastq.gz",
                "strandedness": "auto",
            },
            {
                "sample": "sample2",
                "fastq_1": "/path/to/sample2_1.fastq.gz",
                "fastq_2": "/path/to/sample2_2.fastq.gz",
                "strandedness": "auto",
            },
        ]

        sheet = SampleSheet(samples=samples)

        assert len(sheet.samples) == 2
        assert sheet.samples[0]["sample"] == "sample1"

    def test_samplesheet_to_csv(self, tmp_path):
        """Test writing samplesheet to CSV."""
        samples = [
            {
                "sample": "sample1",
                "fastq_1": "/path/file1.fastq.gz",
                "strandedness": "auto",
            }
        ]

        sheet = SampleSheet(samples=samples)
        output_path = tmp_path / "samplesheet.csv"

        sheet.to_csv(output_path)

        assert output_path.exists()

        # Read and verify
        import csv
        with open(output_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["sample"] == "sample1"

    def test_samplesheet_from_curated_dataset(self, sample_curated_dataset, tmp_path):
        """Test creating samplesheet from curated dataset."""
        fastq_dir = tmp_path / "fastq"
        fastq_dir.mkdir()

        # Create mock FASTQ files
        for sample in sample_curated_dataset["samples"]:
            sample_id = sample["sample_id"]
            (fastq_dir / f"{sample_id}_1.fastq.gz").touch()
            (fastq_dir / f"{sample_id}_2.fastq.gz").touch()

        sheet = SampleSheet.from_curated_dataset(sample_curated_dataset, fastq_dir)

        assert len(sheet.samples) == 3
        assert sheet.samples[0]["sample"] == "GSM111111"


class TestEnums:
    """Test enum types."""

    def test_pipeline_type_enum(self):
        """Test PipelineType enum values."""
        assert PipelineType.RNASEQ.value == "rnaseq"
        assert PipelineType.FETCHNGS.value == "fetchngs"
        assert PipelineType.SAREK.value == "sarek"

    def test_compute_environment_enum(self):
        """Test ComputeEnvironment enum values."""
        assert ComputeEnvironment.LOCAL.value == "local"
        assert ComputeEnvironment.AWS.value == "aws"
        assert ComputeEnvironment.HPC_SLURM.value == "slurm"

    def test_execution_status_enum(self):
        """Test ExecutionStatus enum values."""
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.RUNNING.value == "running"
        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"
