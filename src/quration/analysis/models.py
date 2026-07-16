"""
Data models for the analysis module.

This module defines Pydantic models for analysis plans, pipeline configurations,
and execution results.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, model_validator


class PipelineType(str, Enum):
    """Supported nf-core pipeline types."""

    FETCHNGS = "fetchngs"
    RNASEQ = "rnaseq"
    SAREK = "sarek"  # Variant calling
    CHIPSEQ = "chipseq"
    ATACSEQ = "atacseq"
    SCRNASEQ = "scrnaseq"
    METHYLSEQ = "methylseq"
    AMPLISEQ = "ampliseq"


class ComputeEnvironment(str, Enum):
    """Supported compute environments."""

    LOCAL = "local"
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"
    HPC_SLURM = "slurm"
    HPC_PBS = "pbs"
    KUBERNETES = "k8s"


class ExecutionStatus(str, Enum):
    """Pipeline execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReferenceGenome(BaseModel):
    """Reference genome information."""

    name: str = Field(..., description="Genome name (e.g., GRCh38, GRCm39)")
    organism: str = Field(..., description="Organism name")
    fasta_url: Optional[str] = Field(None, description="URL to FASTA file")
    gtf_url: Optional[str] = Field(None, description="URL to GTF annotation")
    igenomes_ref: Optional[str] = Field(
        None, description="iGenomes reference name if available"
    )


class ComparisonGroup(BaseModel):
    """Experimental comparison group for differential analysis."""

    name: str = Field(..., description="Comparison name")
    condition_a: str = Field(..., description="First condition/group")
    condition_b: str = Field(..., description="Second condition/group")
    sample_ids_a: List[str] = Field(..., description="Sample IDs for condition A")
    sample_ids_b: List[str] = Field(..., description="Sample IDs for condition B")


class PipelineParameters(BaseModel):
    """Base parameters for nf-core pipelines."""

    input: str = Field(..., description="Path to input samplesheet")
    outdir: str = Field(..., description="Output directory")
    genome: Optional[str] = Field(None, description="Reference genome name")
    fasta: Optional[str] = Field(None, description="Path to FASTA file")
    gtf: Optional[str] = Field(None, description="Path to GTF file")

    # Common optional parameters
    skip_qc: bool = Field(False, description="Skip quality control steps")
    extra_params: Dict[str, Any] = Field(
        default_factory=dict, description="Additional pipeline-specific parameters"
    )


class RNASeqParameters(PipelineParameters):
    """Parameters specific to nf-core/rnaseq pipeline."""

    aligner: str = Field("star_salmon", description="Alignment tool")
    pseudo_aligner: Optional[str] = Field(None, description="Pseudo-aligner (salmon, kallisto)")
    trimmer: str = Field("trimgalore", description="Trimming tool")
    skip_trimming: bool = Field(False, description="Skip read trimming")
    save_trimmed: bool = Field(False, description="Save trimmed reads")

    # Differential expression
    comparisons: Optional[List[ComparisonGroup]] = Field(
        None, description="Comparison groups for DE analysis"
    )


class FetchNGSParameters(BaseModel):
    """Parameters for nf-core/fetchngs pipeline."""

    input: str = Field(..., description="Path to accession IDs file")
    outdir: str = Field(..., description="Output directory")
    download_method: str = Field("ftp", description="Download method: ftp, sratools, aspera")
    nf_core_pipeline: Optional[str] = Field(
        None, description="Format output for specific nf-core pipeline"
    )


class AnalysisPlan(BaseModel):
    """LLM-generated analysis plan for a curated dataset."""

    dataset_id: str = Field(..., description="GEO dataset ID (e.g., GSE12345)")
    dataset_title: str = Field(..., description="Dataset title")

    # Analysis recommendations
    recommended_pipelines: List[PipelineType] = Field(
        ..., description="Recommended nf-core pipelines"
    )
    primary_pipeline: PipelineType = Field(
        ..., description="Primary pipeline to run first"
    )

    # Metadata-derived information
    organism: str = Field(..., description="Organism name")
    library_strategy: str = Field(..., description="Library strategy (RNA-Seq, etc.)")
    sample_count: int = Field(..., description="Number of samples")
    has_paired_end: bool = Field(..., description="Whether data is paired-end")

    # Reference genome
    suggested_genome: ReferenceGenome = Field(
        ..., description="Suggested reference genome"
    )

    # Experimental design
    experimental_design: Optional[str] = Field(
        None, description="Description of experimental design"
    )
    comparison_groups: List[ComparisonGroup] = Field(
        default_factory=list, description="Suggested comparison groups"
    )

    # Analysis rationale
    rationale: str = Field(
        ..., description="LLM explanation of why these analyses are recommended"
    )
    expected_outputs: List[str] = Field(
        ..., description="Expected analysis outputs"
    )
    estimated_runtime: Optional[str] = Field(
        None, description="Estimated runtime"
    )

    # Data availability
    requires_download: bool = Field(
        True, description="Whether raw data needs to be downloaded"
    )
    sra_ids: List[str] = Field(
        default_factory=list, description="SRA accession IDs for download"
    )

    created_at: datetime = Field(
        default_factory=datetime.now, description="Plan creation timestamp"
    )


class PipelineConfig(BaseModel):
    """Configuration for running an nf-core pipeline."""

    pipeline_type: PipelineType
    pipeline_version: Optional[str] = Field(None, description="Pipeline version")

    parameters: Union[PipelineParameters, RNASeqParameters, FetchNGSParameters]

    # Execution settings
    compute_env: ComputeEnvironment = Field(
        ComputeEnvironment.LOCAL, description="Compute environment"
    )
    profile: List[str] = Field(
        default_factory=lambda: ["docker"], description="Nextflow profiles"
    )
    work_dir: Optional[str] = Field(None, description="Nextflow work directory")
    resume: bool = Field(False, description="Resume previous run")

    # Resource limits
    max_cpus: Optional[int] = Field(None, description="Maximum CPUs")
    max_memory: Optional[str] = Field(None, description="Maximum memory (e.g., 128.GB)")
    max_time: Optional[str] = Field(None, description="Maximum time (e.g., 48.h)")


class ExecutionResult(BaseModel):
    """Result of pipeline execution."""

    pipeline_type: PipelineType
    dataset_id: str

    status: ExecutionStatus

    # Execution details
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Paths
    work_dir: str
    output_dir: str
    log_file: Optional[str] = None

    # Results
    output_files: Dict[str, str] = Field(
        default_factory=dict, description="Key output files"
    )
    metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Summary metrics"
    )

    # Error information
    error_message: Optional[str] = None
    exit_code: Optional[int] = None

    # Nextflow info
    nextflow_version: Optional[str] = None
    pipeline_version: Optional[str] = None

    @model_validator(mode="after")
    def calculate_duration(self):
        """Fill duration_seconds from the timestamps when not explicitly provided.

        Runs after all fields are set, so it's immune to field ordering and to Pydantic
        skipping field-validators on unset defaults."""
        if self.duration_seconds is None and self.completed_at and self.started_at:
            self.duration_seconds = (
                self.completed_at - self.started_at
            ).total_seconds()
        return self


class SampleSheet(BaseModel):
    """Samplesheet for nf-core pipelines."""

    samples: List[Dict[str, str]] = Field(..., description="Sample entries")

    def to_csv(self, output_path: Path) -> None:
        """Write samplesheet to CSV file."""
        import csv

        if not self.samples:
            raise ValueError("No samples to write")

        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.samples[0].keys())
            writer.writeheader()
            writer.writerows(self.samples)

    @classmethod
    def from_curated_dataset(
        cls, curated_dataset: Dict[str, Any], fastq_dir: Path
    ) -> "SampleSheet":
        """Generate samplesheet from curated dataset metadata."""
        samples = []

        for sample in curated_dataset.get("samples", []):
            sample_id = sample.get("sample_id")

            # Basic entry for RNA-seq
            entry = {
                "sample": sample_id,
                "fastq_1": str(fastq_dir / f"{sample_id}_1.fastq.gz"),
                "fastq_2": str(fastq_dir / f"{sample_id}_2.fastq.gz"),
                "strandedness": "auto",  # Can be inferred from metadata
            }
            samples.append(entry)

        return cls(samples=samples)
