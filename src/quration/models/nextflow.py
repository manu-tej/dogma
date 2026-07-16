"""
Data models for Nextflow pipeline integration.

This module defines the schemas for:
- Pipeline catalog entries
- Pipeline parameters and configuration
- Pipeline execution tracking
- Output metadata mapping
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator


class OmicsType(str, Enum):
    """Types of omics analyses supported."""
    BULK_RNASEQ = "bulk_rnaseq"
    SINGLE_CELL = "single_cell"
    PROTEOMICS = "proteomics"
    METABOLOMICS = "metabolomics"
    GENOMICS = "genomics"
    EPIGENOMICS = "epigenomics"
    METAGENOMICS = "metagenomics"


class PipelineStatus(str, Enum):
    """Status of pipeline execution."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ParameterType(str, Enum):
    """Types of pipeline parameters."""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    FILE = "file"
    DIRECTORY = "directory"
    CHOICE = "choice"


class PipelineParameter(BaseModel):
    """Definition of a single pipeline parameter."""
    name: str = Field(..., description="Parameter name (e.g., '--genome')")
    type: ParameterType = Field(..., description="Parameter type")
    description: str = Field(..., description="Human-readable description")
    required: bool = Field(default=False, description="Whether parameter is required")
    default: Optional[Any] = Field(default=None, description="Default value")
    choices: Optional[List[str]] = Field(default=None, description="Valid choices for choice type")
    example: Optional[str] = Field(default=None, description="Example value")
    group: str = Field(default="General", description="Parameter group for UI organization")

    @field_validator("choices")
    @classmethod
    def validate_choices(cls, v, info):
        """Ensure choices are provided for choice type."""
        if info.data.get("type") == ParameterType.CHOICE and not v:
            raise ValueError("Choices must be provided for choice type parameters")
        return v


class PipelineCatalogEntry(BaseModel):
    """Catalog entry for a Nextflow pipeline."""
    id: str = Field(..., description="Unique pipeline identifier (e.g., 'nf-core/rnaseq')")
    name: str = Field(..., description="Display name")
    version: str = Field(..., description="Pipeline version")
    omics_types: List[OmicsType] = Field(..., description="Types of omics analyses this pipeline supports")
    description: str = Field(..., description="Short description")
    long_description: Optional[str] = Field(default=None, description="Detailed description")
    documentation_url: HttpUrl = Field(..., description="URL to pipeline documentation")
    repository_url: HttpUrl = Field(..., description="URL to source code repository")
    parameters: List[PipelineParameter] = Field(default_factory=list, description="Pipeline parameters")
    input_format: str = Field(..., description="Description of expected input format (e.g., 'FASTQ files')")
    output_format: str = Field(..., description="Description of output format")
    example_command: Optional[str] = Field(default=None, description="Example Nextflow command")
    citation: Optional[str] = Field(default=None, description="Citation for the pipeline")
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    enabled: bool = Field(default=True, description="Whether pipeline is enabled for use")

    # Metadata mapping configuration
    output_mapping: Optional[Dict[str, str]] = Field(
        default=None,
        description="Mapping of pipeline outputs to quration metadata schema fields"
    )

    # Resource recommendations
    recommended_cpus: Optional[int] = Field(default=None, description="Recommended CPU cores")
    recommended_memory_gb: Optional[int] = Field(default=None, description="Recommended memory in GB")
    estimated_runtime_hours: Optional[float] = Field(default=None, description="Estimated runtime")


class PipelineInput(BaseModel):
    """Input specification for pipeline execution."""
    dataset_id: Optional[str] = Field(default=None, description="GEO dataset ID if applicable")
    input_files: List[str] = Field(..., description="Paths to input files")
    samplesheet: Optional[str] = Field(default=None, description="Path to samplesheet if required")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Associated metadata")


class PipelineConfiguration(BaseModel):
    """Configuration for pipeline execution."""
    pipeline_id: str = Field(..., description="Pipeline identifier")
    pipeline_version: str = Field(..., description="Pipeline version to use")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Pipeline parameters")
    profile: str = Field(default="docker", description="Nextflow profile (docker, singularity, conda)")
    work_dir: Optional[str] = Field(default=None, description="Nextflow work directory")
    output_dir: str = Field(..., description="Output directory for results")
    resume: bool = Field(default=False, description="Resume previous execution")
    max_cpus: Optional[int] = Field(default=None, description="Maximum CPUs to use")
    max_memory_gb: Optional[int] = Field(default=None, description="Maximum memory in GB")
    max_time_hours: Optional[int] = Field(default=None, description="Maximum execution time")


class PipelineExecution(BaseModel):
    """Tracking information for a pipeline execution."""
    execution_id: str = Field(..., description="Unique execution identifier")
    pipeline_id: str = Field(..., description="Pipeline identifier")
    pipeline_version: str = Field(..., description="Pipeline version")
    status: PipelineStatus = Field(default=PipelineStatus.PENDING, description="Execution status")
    configuration: PipelineConfiguration = Field(..., description="Execution configuration")
    input_spec: PipelineInput = Field(..., description="Input specification")

    # Execution tracking
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")

    # Nextflow tracking
    nextflow_run_id: Optional[str] = Field(default=None, description="Nextflow run ID")
    nextflow_session_id: Optional[str] = Field(default=None, description="Nextflow session ID")
    work_directory: Optional[str] = Field(default=None, description="Nextflow work directory")
    output_directory: Optional[str] = Field(default=None, description="Output directory")

    # Results and errors
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    log_file: Optional[str] = Field(default=None, description="Path to execution log")

    # Progress tracking
    progress_percent: float = Field(default=0.0, description="Progress percentage (0-100)")
    current_step: Optional[str] = Field(default=None, description="Current execution step")

    # Resource usage
    cpu_usage: Optional[float] = Field(default=None, description="CPU usage percentage")
    memory_usage_gb: Optional[float] = Field(default=None, description="Memory usage in GB")

    # Output metadata
    output_files: List[str] = Field(default_factory=list, description="Generated output files")
    multiqc_report: Optional[str] = Field(default=None, description="Path to MultiQC report")
    pipeline_report: Optional[str] = Field(default=None, description="Path to pipeline report")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PipelineOutput(BaseModel):
    """Structured output from a completed pipeline."""
    execution_id: str = Field(..., description="Execution identifier")
    pipeline_id: str = Field(..., description="Pipeline identifier")
    status: PipelineStatus = Field(..., description="Execution status")

    # Output files
    output_directory: str = Field(..., description="Output directory path")
    primary_outputs: List[str] = Field(default_factory=list, description="Primary result files")
    qc_outputs: List[str] = Field(default_factory=list, description="QC report files")
    intermediate_outputs: List[str] = Field(default_factory=list, description="Intermediate files")

    # Reports
    multiqc_report_path: Optional[str] = Field(default=None, description="MultiQC HTML report")
    execution_report_path: Optional[str] = Field(default=None, description="Nextflow execution report")
    execution_timeline_path: Optional[str] = Field(default=None, description="Nextflow timeline")

    # Mapped metadata
    mapped_metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Output data mapped to quration metadata schema"
    )

    # Summary statistics
    summary_stats: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Summary statistics extracted from outputs"
    )


class NextflowConfig(BaseModel):
    """Configuration for Nextflow runtime."""
    nextflow_executable: str = Field(default="nextflow", description="Path to Nextflow executable")
    nf_core_executable: Optional[str] = Field(default=None, description="Path to nf-core tools")
    work_dir: str = Field(default="./work", description="Default work directory")
    output_dir: str = Field(default="./results", description="Default output directory")
    cache_dir: Optional[str] = Field(default=None, description="Nextflow cache directory")
    enable_conda: bool = Field(default=False, description="Enable Conda support")
    enable_docker: bool = Field(default=True, description="Enable Docker support")
    enable_singularity: bool = Field(default=False, description="Enable Singularity support")
    default_profile: str = Field(default="docker", description="Default execution profile")
    max_retries: int = Field(default=3, description="Maximum execution retries")
    trace_enabled: bool = Field(default=True, description="Enable execution trace")
    report_enabled: bool = Field(default=True, description="Enable execution reports")
    timeline_enabled: bool = Field(default=True, description="Enable execution timeline")
    dag_enabled: bool = Field(default=True, description="Enable DAG visualization")


# API Request/Response Models

class ListPipelinesRequest(BaseModel):
    """Request to list available pipelines."""
    omics_type: Optional[OmicsType] = Field(default=None, description="Filter by omics type")
    search: Optional[str] = Field(default=None, description="Search in name/description")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags")
    enabled_only: bool = Field(default=True, description="Only show enabled pipelines")


class ExecutePipelineRequest(BaseModel):
    """Request to execute a pipeline."""
    pipeline_id: str = Field(..., description="Pipeline to execute")
    pipeline_version: Optional[str] = Field(default=None, description="Specific version (latest if not specified)")
    input_spec: PipelineInput = Field(..., description="Input specification")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Pipeline parameters")
    profile: str = Field(default="docker", description="Execution profile")
    output_dir: Optional[str] = Field(default=None, description="Output directory")
    resume: bool = Field(default=False, description="Resume if previous run exists")


class ExecutePipelineResponse(BaseModel):
    """Response from pipeline execution request."""
    execution_id: str = Field(..., description="Unique execution ID")
    pipeline_id: str = Field(..., description="Pipeline ID")
    status: PipelineStatus = Field(..., description="Initial status")
    message: str = Field(..., description="Status message")
    output_directory: str = Field(..., description="Output directory")


class GetExecutionStatusResponse(BaseModel):
    """Response for execution status query."""
    execution: PipelineExecution = Field(..., description="Execution details")
    logs: Optional[str] = Field(default=None, description="Recent log output")
