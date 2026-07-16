"""Pydantic models for FastAPI endpoints."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

TherapyScope = Literal["specific", "broad"]


class QuerySpecModel(BaseModel):
    """Request model for GEO search query specification."""

    disease_terms: List[str] = Field(
        ...,
        alias="diseaseTerms",
        description="List of disease terms to search for",
        min_length=1
    )
    therapy_class: Optional[str] = Field(
        None,
        alias="therapyClass",
        description="Optional therapy class (e.g., 'immunotherapy')"
    )
    therapy_scope: TherapyScope = Field(
        ...,
        alias="therapyScope",
        description="Therapy scope: 'specific' or 'broad'"
    )
    targets_or_genes: List[str] = Field(
        default_factory=list,
        alias="targetsOrGenes",
        description="List of target genes or molecules"
    )
    study_keywords: List[str] = Field(
        default_factory=list,
        alias="studyKeywords",
        description="Additional study keywords"
    )
    must_have_clinical: bool = Field(
        False,
        alias="mustHaveClinical",
        description="Whether the dataset must have clinical data"
    )
    min_samples: Optional[int] = Field(
        None,
        alias="minSamples",
        description="Minimum number of samples required",
        ge=1
    )

    class Config:
        populate_by_name = True  # Allow both snake_case and camelCase
        json_schema_extra = {
            "example": {
                "diseaseTerms": ["melanoma"],
                "therapyClass": "immunotherapy",
                "therapyScope": "specific",
                "targetsOrGenes": ["PD-1", "CTLA4"],
                "studyKeywords": ["checkpoint inhibitor", "resistance"],
                "mustHaveClinical": True,
                "minSamples": 20,
            }
        }


class ConditionModel(BaseModel):
    """Model for experimental condition."""

    name: str = Field(..., description="Condition name")
    n: Optional[int] = Field(None, description="Number of samples in this condition")


class ExperimentalDesignModel(BaseModel):
    """Model for experimental design information."""

    conditions: Optional[List[ConditionModel]] = Field(
        None, description="List of experimental conditions"
    )
    design_type: Optional[str] = Field(
        None, alias="designType", description="Type of experimental design (e.g., 'case-control')"
    )
    tech: Optional[str] = Field(
        None, description="Sequencing/array technology used"
    )
    notes: str = Field("", description="Additional design notes")
    is_partial: bool = Field(
        True, alias="isPartial", description="Whether design information is partial/incomplete"
    )

    class Config:
        populate_by_name = True  # Allow both snake_case and camelCase


class GsmSampleModel(BaseModel):
    """Model for GSM (sample) record."""

    gsm_id: str = Field(..., alias="gsmId", description="GSM accession ID")
    title: str = Field(..., description="Sample title")
    sample_type: Optional[str] = Field(None, alias="sampleType", description="Type of sample")
    characteristics: dict[str, str] = Field(
        default_factory=dict, description="Sample characteristics"
    )
    raw_metadata: Any = Field(None, alias="rawMetadata", description="Raw metadata from GEO")

    class Config:
        populate_by_name = True  # Allow both snake_case and camelCase


class GeoDatasetCandidateModel(BaseModel):
    """Response model for GEO dataset candidate."""

    gse_id: str = Field(..., alias="gseId", description="GSE accession ID")
    title: str = Field(..., description="Dataset title")
    summary: str = Field(..., description="Dataset summary/abstract")
    organism: Optional[str] = Field(None, description="Organism (e.g., 'Homo sapiens')")
    experimental_design: ExperimentalDesignModel = Field(
        ..., alias="experimentalDesign", description="Parsed experimental design"
    )
    n_samples: Optional[int] = Field(None, alias="nSamples", description="Number of samples")
    platforms: List[str] = Field(
        default_factory=list, description="Platform IDs (GPL)"
    )
    primary_pmid: Optional[str] = Field(
        None, alias="primaryPmid", description="Primary PubMed ID for associated publication"
    )
    maybe_has_survival_data: bool = Field(
        False, alias="maybeHasSurvivalData", description="Heuristic flag for potential survival data"
    )
    match_reasons: List[str] = Field(
        default_factory=list, alias="matchReasons", description="Reasons why this dataset matched the query"
    )
    raw_metadata: Any = Field(None, alias="rawMetadata", description="Raw metadata from GEO")
    matched_queries: List[str] = Field(
        default_factory=list, alias="matchedQueries", description="GEO queries that matched this dataset"
    )
    samples: List[GsmSampleModel] = Field(
        default_factory=list, description="GSM sample records"
    )
    samples_fetched: bool = Field(
        False, alias="samplesFetched", description="Whether GSM samples were fetched"
    )

    class Config:
        populate_by_name = True  # Allow both snake_case and camelCase
        json_schema_extra = {
            "example": {
                "gse_id": "GSE123456",
                "title": "Melanoma immunotherapy response study",
                "summary": "RNA-seq analysis of melanoma patients treated with anti-PD-1",
                "experimental_design": {
                    "conditions": [
                        {"name": "responder", "n": 15},
                        {"name": "non-responder", "n": 12},
                    ],
                    "design_type": "case-control",
                    "tech": "Illumina HiSeq 2500",
                    "notes": "Paired tumor samples pre/post treatment",
                    "is_partial": False,
                },
                "n_samples": 27,
                "platforms": ["GPL16791"],
                "primary_pmid": "12345678",
                "maybe_has_survival_data": True,
                "match_reasons": [
                    "Matches disease terms: melanoma",
                    "Mentions therapy: immunotherapy",
                    "Mentions genes/targets: PD-1",
                ],
                "matched_queries": [
                    "melanoma[All Fields] AND immunotherapy[All Fields]"
                ],
                "samples": [],
                "samples_fetched": False,
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str = Field(..., description="Error message")


class ProgressEvent(BaseModel):
    """Progress event for streaming search updates."""

    step: str = Field(..., description="Current step identifier")
    status: Literal["pending", "running", "complete", "error"] = Field(
        ..., description="Status of this step"
    )
    message: str = Field(..., description="Human-readable status message")
    progress: Optional[int] = Field(None, description="Current progress count (e.g., 5)")
    total: Optional[int] = Field(None, description="Total items to process (e.g., 10)")


# Proteomics Models

class ProteomicsQuerySpecModel(BaseModel):
    """Request model for proteomics search query specification."""

    disease_terms: List[str] = Field(
        ...,
        alias="diseaseTerms",
        description="List of disease terms to search for",
        min_length=1
    )
    therapy_class: Optional[str] = Field(
        None,
        alias="therapyClass",
        description="Optional therapy class (e.g., 'immunotherapy')"
    )
    therapy_scope: TherapyScope = Field(
        ...,
        alias="therapyScope",
        description="Therapy scope: 'specific' or 'broad'"
    )
    targets_or_proteins: List[str] = Field(
        default_factory=list,
        alias="targetsOrProteins",
        description="List of target proteins or genes"
    )
    study_keywords: List[str] = Field(
        default_factory=list,
        alias="studyKeywords",
        description="Additional study keywords"
    )
    must_have_quantification: bool = Field(
        False,
        alias="mustHaveQuantification",
        description="Whether the dataset must have quantitative proteomics data"
    )
    min_samples: Optional[int] = Field(
        None,
        alias="minSamples",
        description="Minimum number of samples required",
        ge=1
    )
    organism: Optional[str] = Field(
        "Homo sapiens",
        description="Organism filter (e.g., 'Homo sapiens', 'Mus musculus')"
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "diseaseTerms": ["breast cancer"],
                "therapyClass": "targeted therapy",
                "therapyScope": "specific",
                "targetsOrProteins": ["HER2", "EGFR"],
                "studyKeywords": ["phosphoproteomics", "drug resistance"],
                "mustHaveQuantification": True,
                "minSamples": 10,
                "organism": "Homo sapiens",
            }
        }


class ProteomicsConditionModel(BaseModel):
    """Model for proteomics experimental condition."""

    name: str = Field(..., description="Condition name")
    n_replicates: Optional[int] = Field(None, alias="nReplicates", description="Number of replicates")
    treatment: Optional[str] = Field(None, description="Treatment applied")

    class Config:
        populate_by_name = True


class ProteomicsExperimentalDesignModel(BaseModel):
    """Model for proteomics experimental design."""

    conditions: Optional[List[ProteomicsConditionModel]] = Field(
        None, description="List of experimental conditions"
    )
    design_type: Optional[str] = Field(
        None, alias="designType", description="Type of experimental design"
    )
    instrument: Optional[str] = Field(None, description="Mass spectrometry instrument")
    quantification_method: Optional[str] = Field(
        None, alias="quantificationMethod", description="Quantification method (e.g., TMT, label-free)"
    )
    acquisition_strategy: Optional[str] = Field(
        None, alias="acquisitionStrategy", description="Acquisition strategy (DDA, DIA, etc.)"
    )
    notes: str = Field("", description="Additional design notes")
    is_partial: bool = Field(
        True, alias="isPartial", description="Whether design information is partial/incomplete"
    )

    class Config:
        populate_by_name = True


class ProteomicsAssayModel(BaseModel):
    """Model for proteomics assay/run."""

    assay_id: str = Field(..., alias="assayId", description="Assay identifier")
    title: str = Field(..., description="Assay title")
    sample_type: Optional[str] = Field(None, alias="sampleType", description="Sample type")
    characteristics: dict[str, str] = Field(
        default_factory=dict, description="Sample characteristics"
    )
    raw_metadata: Any = Field(None, alias="rawMetadata", description="Raw metadata")

    class Config:
        populate_by_name = True


class ProteomicsDatasetCandidateModel(BaseModel):
    """Response model for proteomics dataset candidate."""

    accession: str = Field(..., description="PRIDE/ProteomeXchange accession (e.g., PXD012345)")
    title: str = Field(..., description="Dataset title")
    description: str = Field(..., description="Dataset description")
    experimental_design: ProteomicsExperimentalDesignModel = Field(
        ..., alias="experimentalDesign", description="Parsed experimental design"
    )
    n_assays: Optional[int] = Field(None, alias="nAssays", description="Number of assays/runs")
    organism: Optional[str] = Field(None, description="Organism")
    instruments: List[str] = Field(default_factory=list, description="Mass spec instruments used")
    experiment_types: List[str] = Field(
        default_factory=list, alias="experimentTypes", description="Experiment types"
    )
    quantification_methods: List[str] = Field(
        default_factory=list, alias="quantificationMethods", description="Quantification methods"
    )
    tissues: List[str] = Field(default_factory=list, description="Tissue types")
    diseases: List[str] = Field(default_factory=list, description="Diseases studied")
    cell_types: List[str] = Field(default_factory=list, alias="cellTypes", description="Cell types")
    primary_doi: Optional[str] = Field(None, alias="primaryDoi", description="Primary DOI")
    primary_pmid: Optional[str] = Field(None, alias="primaryPmid", description="Primary PubMed ID")
    has_protein_data: bool = Field(
        False, alias="hasProteinData", description="Has protein identification data"
    )
    has_peptide_data: bool = Field(
        False, alias="hasPeptideData", description="Has peptide data"
    )
    has_quantification_data: bool = Field(
        False, alias="hasQuantificationData", description="Has quantification data"
    )
    match_reasons: List[str] = Field(
        default_factory=list, alias="matchReasons", description="Reasons for matching"
    )
    matched_queries: List[str] = Field(
        default_factory=list, alias="matchedQueries", description="Queries that matched"
    )
    raw_metadata: Any = Field(None, alias="rawMetadata", description="Raw metadata from PRIDE")
    assays: List[ProteomicsAssayModel] = Field(default_factory=list, description="Assay records")
    assays_fetched: bool = Field(
        False, alias="assaysFetched", description="Whether assays were fetched"
    )

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "accession": "PXD012345",
                "title": "Phosphoproteomics of breast cancer drug resistance",
                "description": "TMT-based quantitative phosphoproteomics...",
                "experimentalDesign": {
                    "conditions": [
                        {"name": "sensitive", "nReplicates": 3},
                        {"name": "resistant", "nReplicates": 3},
                    ],
                    "designType": "case-control",
                    "instrument": "Orbitrap Fusion Lumos",
                    "quantificationMethod": "TMT11plex",
                    "acquisitionStrategy": "DDA",
                    "notes": "Phosphopeptide enrichment using TiO2",
                    "isPartial": False,
                },
                "nAssays": 6,
                "organism": "Homo sapiens",
                "instruments": ["Orbitrap Fusion Lumos"],
                "experimentTypes": ["Phosphoproteomics", "TMT labeling"],
                "quantificationMethods": ["TMT11plex"],
                "tissues": ["breast"],
                "diseases": ["breast cancer"],
                "cellTypes": ["cancer cell line"],
                "primaryDoi": "10.1038/s41586-020-1234-5",
                "primaryPmid": "32123456",
                "hasProteinData": True,
                "hasPeptideData": True,
                "hasQuantificationData": True,
                "matchReasons": [
                    "Disease term 'breast cancer' found",
                    "Has quantification data"
                ],
                "matchedQueries": ["breast cancer phosphoproteomics"],
            }
        }


# ============================================================================
# Analysis Module Models
# ============================================================================

class ComparisonGroupModel(BaseModel):
    """Model for experimental comparison group."""

    name: str = Field(..., description="Comparison name")
    condition_a: str = Field(..., alias="conditionA", description="First condition/group")
    condition_b: str = Field(..., alias="conditionB", description="Second condition/group")
    sample_ids_a: List[str] = Field(..., alias="sampleIdsA", description="Sample IDs for condition A")
    sample_ids_b: List[str] = Field(..., alias="sampleIdsB", description="Sample IDs for condition B")

    class Config:
        populate_by_name = True


class ReferenceGenomeModel(BaseModel):
    """Model for reference genome information."""

    name: str = Field(..., description="Genome name (e.g., GRCh38)")
    organism: str = Field(..., description="Organism name")
    igenomes_ref: Optional[str] = Field(None, alias="igenomesRef", description="iGenomes reference name")

    class Config:
        populate_by_name = True


class AnalysisPlanModel(BaseModel):
    """Model for analysis plan response."""

    dataset_id: str = Field(..., alias="datasetId", description="Dataset ID (e.g., GSE123456)")
    dataset_title: str = Field(..., alias="datasetTitle", description="Dataset title")
    recommended_pipelines: List[str] = Field(..., alias="recommendedPipelines", description="Recommended nf-core pipelines")
    primary_pipeline: str = Field(..., alias="primaryPipeline", description="Primary pipeline to run")
    organism: str = Field(..., description="Organism name")
    library_strategy: str = Field(..., alias="libraryStrategy", description="Library strategy (e.g., RNA-Seq)")
    sample_count: int = Field(..., alias="sampleCount", description="Number of samples")
    has_paired_end: bool = Field(..., alias="hasPairedEnd", description="Whether data is paired-end")
    suggested_genome: ReferenceGenomeModel = Field(..., alias="suggestedGenome", description="Suggested reference genome")
    comparison_groups: List[ComparisonGroupModel] = Field(default_factory=list, alias="comparisonGroups", description="Suggested comparison groups")
    rationale: str = Field(..., description="Explanation of recommendations")
    expected_outputs: List[str] = Field(..., alias="expectedOutputs", description="Expected analysis outputs")
    estimated_runtime: Optional[str] = Field(None, alias="estimatedRuntime", description="Estimated runtime")
    requires_download: bool = Field(True, alias="requiresDownload", description="Whether raw data needs downloading")
    sra_ids: List[str] = Field(default_factory=list, alias="sraIds", description="SRA accession IDs")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "datasetId": "GSE123456",
                "datasetTitle": "RNA-seq analysis of breast cancer",
                "recommendedPipelines": ["rnaseq"],
                "primaryPipeline": "rnaseq",
                "organism": "Homo sapiens",
                "libraryStrategy": "RNA-Seq",
                "sampleCount": 24,
                "hasPairedEnd": True,
                "suggestedGenome": {
                    "name": "GRCh38",
                    "organism": "Homo sapiens",
                    "igenomesRef": "GRCh38"
                },
                "comparisonGroups": [
                    {
                        "name": "tumor_vs_normal",
                        "conditionA": "tumor",
                        "conditionB": "normal",
                        "sampleIdsA": ["GSM1", "GSM2"],
                        "sampleIdsB": ["GSM3", "GSM4"]
                    }
                ],
                "rationale": "RNA-seq pipeline recommended for gene expression analysis",
                "expectedOutputs": ["Gene counts", "Differential expression results"],
                "estimatedRuntime": "4-6 hours",
                "requiresDownload": False,
                "sraIds": ["SRR123456", "SRR123457"]
            }
        }


class PipelineInfoModel(BaseModel):
    """Model for pipeline information."""

    name: str = Field(..., description="Pipeline name (e.g., nf-core/rnaseq)")
    pipeline_type: str = Field(..., alias="pipelineType", description="Pipeline type")
    version: str = Field(..., description="Latest version")
    description: str = Field(..., description="Pipeline description")
    supported_strategies: List[str] = Field(..., alias="supportedStrategies", description="Supported library strategies")
    homepage_url: str = Field(..., alias="homepageUrl", description="Pipeline homepage URL")

    class Config:
        populate_by_name = True


class GenerateAnalysisPlanRequest(BaseModel):
    """Request model for generating an analysis plan."""

    curated_dataset: dict = Field(..., alias="curatedDataset", description="Curated dataset metadata (JSON)")

    class Config:
        populate_by_name = True


class FetchDataRequest(BaseModel):
    """Request model for fetching raw data."""

    dataset_id: str = Field(..., alias="datasetId", description="GEO dataset ID (e.g., GSE123456)")
    email: str = Field(..., description="Email for NCBI API (required)")
    api_key: Optional[str] = Field(None, alias="apiKey", description="NCBI API key (optional)")
    download_method: str = Field("ftp", alias="downloadMethod", description="Download method (ftp, sratools, aspera)")

    class Config:
        populate_by_name = True


class FetchDataResponse(BaseModel):
    """Response model for data fetching."""

    status: str = Field(..., description="Fetch status (pending, running, completed, failed)")
    dataset_id: str = Field(..., alias="datasetId", description="Dataset ID")
    message: str = Field(..., description="Status message")
    output_dir: Optional[str] = Field(None, alias="outputDir", description="Output directory path")

    class Config:
        populate_by_name = True


# ============================================================================
# Pipeline Execution Models
# ============================================================================

class PipelineParametersModel(BaseModel):
    """Model for pipeline parameters."""

    input: str = Field(..., description="Path to input samplesheet")
    outdir: str = Field(..., alias="outdir", description="Output directory")
    genome: Optional[str] = Field(None, description="Reference genome name")
    fasta: Optional[str] = Field(None, description="Path to FASTA file")
    gtf: Optional[str] = Field(None, description="Path to GTF file")
    skip_qc: bool = Field(False, alias="skipQc", description="Skip QC steps")
    extra_params: Dict[str, Any] = Field(default_factory=dict, alias="extraParams", description="Extra parameters")

    class Config:
        populate_by_name = True


class ExecutePipelineRequest(BaseModel):
    """Request model for executing a pipeline."""

    pipeline_type: str = Field(..., alias="pipelineType", description="Pipeline type (rnaseq, fetchngs, etc.)")
    dataset_id: str = Field(..., alias="datasetId", description="Dataset ID")
    parameters: PipelineParametersModel = Field(..., description="Pipeline parameters")

    # Execution settings
    compute_env: str = Field("local", alias="computeEnv", description="Compute environment")
    profile: List[str] = Field(default_factory=lambda: ["docker"], description="Nextflow profiles")
    resume: bool = Field(False, description="Resume previous run")

    # Resource limits
    max_cpus: Optional[int] = Field(None, alias="maxCpus", description="Maximum CPUs")
    max_memory: Optional[str] = Field(None, alias="maxMemory", description="Maximum memory (e.g., 128.GB)")
    max_time: Optional[str] = Field(None, alias="maxTime", description="Maximum time (e.g., 48.h)")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "pipelineType": "rnaseq",
                "datasetId": "GSE123456",
                "parameters": {
                    "input": "/data/samplesheet.csv",
                    "outdir": "/data/results/GSE123456",
                    "genome": "GRCh38"
                },
                "computeEnv": "local",
                "profile": ["docker"],
                "resume": False
            }
        }


class ExecutionStatusModel(BaseModel):
    """Model for execution status response."""

    execution_id: str = Field(..., alias="executionId", description="Unique execution ID")
    pipeline_type: str = Field(..., alias="pipelineType", description="Pipeline type")
    dataset_id: str = Field(..., alias="datasetId", description="Dataset ID")
    status: str = Field(..., description="Execution status (pending, running, completed, failed, cancelled)")

    # Timestamps
    started_at: str = Field(..., alias="startedAt", description="Start timestamp (ISO format)")
    completed_at: Optional[str] = Field(None, alias="completedAt", description="Completion timestamp")
    duration_seconds: Optional[float] = Field(None, alias="durationSeconds", description="Duration in seconds")

    # Progress
    progress: Optional[int] = Field(None, description="Progress percentage (0-100)")
    current_step: Optional[str] = Field(None, alias="currentStep", description="Current pipeline step")

    # Paths
    output_dir: str = Field(..., alias="outputDir", description="Output directory")
    log_file: Optional[str] = Field(None, alias="logFile", description="Log file path")

    # Results
    error_message: Optional[str] = Field(None, alias="errorMessage", description="Error message if failed")
    exit_code: Optional[int] = Field(None, alias="exitCode", description="Exit code")

    class Config:
        populate_by_name = True


class ExecutionResultModel(BaseModel):
    """Model for execution results."""

    execution_id: str = Field(..., alias="executionId", description="Execution ID")
    status: str = Field(..., description="Final status")

    # Output files
    output_files: Dict[str, str] = Field(default_factory=dict, alias="outputFiles", description="Key output files")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Summary metrics")

    # QC reports
    multiqc_report: Optional[str] = Field(None, alias="multiqcReport", description="MultiQC report path")

    class Config:
        populate_by_name = True


class ExecutionListResponse(BaseModel):
    """Model for listing executions."""

    executions: List[ExecutionStatusModel] = Field(..., description="List of executions")
    total: int = Field(..., description="Total number of executions")

    class Config:
        populate_by_name = True


class CancelExecutionResponse(BaseModel):
    """Response model for canceling execution."""

    execution_id: str = Field(..., alias="executionId", description="Execution ID")
    status: str = Field(..., description="New status (cancelled)")
    message: str = Field(..., description="Cancellation message")

    class Config:
        populate_by_name = True
