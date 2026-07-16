/**
 * TypeScript types for Nextflow pipeline integration.
 *
 * These types correspond to the Python models in src/quration/models/nextflow.py
 */

export type OmicsType =
  | "bulk_rnaseq"
  | "single_cell"
  | "proteomics"
  | "metabolomics"
  | "genomics"
  | "epigenomics"
  | "metagenomics";

export type PipelineStatus =
  | "pending"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type ParameterType =
  | "string"
  | "integer"
  | "float"
  | "boolean"
  | "file"
  | "directory"
  | "choice";

export interface PipelineParameter {
  name: string;
  type: ParameterType;
  description: string;
  required: boolean;
  default?: any;
  choices?: string[];
  example?: string;
  group: string;
}

export interface PipelineCatalogEntry {
  id: string;
  name: string;
  version: string;
  omics_types: OmicsType[];
  description: string;
  long_description?: string;
  documentation_url: string;
  repository_url: string;
  parameters: PipelineParameter[];
  input_format: string;
  output_format: string;
  example_command?: string;
  citation?: string;
  tags: string[];
  enabled: boolean;
  output_mapping?: Record<string, string>;
  recommended_cpus?: number;
  recommended_memory_gb?: number;
  estimated_runtime_hours?: number;
}

export interface PipelineInput {
  dataset_id?: string;
  input_files: string[];
  samplesheet?: string;
  metadata?: Record<string, any>;
}

export interface PipelineConfiguration {
  pipeline_id: string;
  pipeline_version: string;
  parameters: Record<string, any>;
  profile: string;
  work_dir?: string;
  output_dir: string;
  resume: boolean;
  max_cpus?: number;
  max_memory_gb?: number;
  max_time_hours?: number;
}

export interface PipelineExecution {
  execution_id: string;
  pipeline_id: string;
  pipeline_version: string;
  status: PipelineStatus;
  configuration: PipelineConfiguration;
  input_spec: PipelineInput;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  nextflow_run_id?: string;
  nextflow_session_id?: string;
  work_directory?: string;
  output_directory?: string;
  error_message?: string;
  log_file?: string;
  progress_percent: number;
  current_step?: string;
  cpu_usage?: number;
  memory_usage_gb?: number;
  output_files: string[];
  multiqc_report?: string;
  pipeline_report?: string;
}

export interface PipelineOutput {
  execution_id: string;
  pipeline_id: string;
  status: PipelineStatus;
  output_directory: string;
  primary_outputs: string[];
  qc_outputs: string[];
  intermediate_outputs: string[];
  multiqc_report_path?: string;
  execution_report_path?: string;
  execution_timeline_path?: string;
  mapped_metadata?: Record<string, any>;
  summary_stats?: Record<string, any>;
}

// API Request/Response types

export interface ListPipelinesRequest {
  omics_type?: OmicsType;
  search?: string;
  tags?: string[];
  enabled_only?: boolean;
}

export interface ExecutePipelineRequest {
  pipeline_id: string;
  pipeline_version?: string;
  input_spec: PipelineInput;
  parameters: Record<string, any>;
  profile?: string;
  output_dir?: string;
  resume?: boolean;
}

export interface ExecutePipelineResponse {
  execution_id: string;
  pipeline_id: string;
  status: PipelineStatus;
  message: string;
  output_directory: string;
}

export interface GetExecutionStatusResponse {
  execution: PipelineExecution;
  logs?: string;
}
