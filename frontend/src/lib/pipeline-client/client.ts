/**
 * API client for Nextflow pipeline operations.
 */

import { API_BASE_URL, DEFAULT_API_BASE_URL } from "../apiBaseUrl";
import type {
  PipelineCatalogEntry,
  PipelineExecution,
  PipelineOutput,
  OmicsType,
  PipelineStatus,
  ExecutePipelineRequest,
  ExecutePipelineResponse,
  GetExecutionStatusResponse,
} from "./types";

export class PipelineClient {
  private baseUrl: string;

  constructor(baseUrl: string = DEFAULT_API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * List available pipelines.
   */
  async listPipelines(options?: {
    omicsType?: OmicsType;
    search?: string;
    tags?: string[];
    enabledOnly?: boolean;
  }): Promise<PipelineCatalogEntry[]> {
    const params = new URLSearchParams();

    if (options?.omicsType) {
      params.append("omics_type", options.omicsType);
    }
    if (options?.search) {
      params.append("search", options.search);
    }
    if (options?.tags && options.tags.length > 0) {
      params.append("tags", options.tags.join(","));
    }
    if (options?.enabledOnly !== undefined) {
      params.append("enabled_only", String(options.enabledOnly));
    }

    const url = `${this.baseUrl}/pipelines?${params.toString()}`;
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`Failed to list pipelines: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get details for a specific pipeline.
   */
  async getPipeline(pipelineId: string): Promise<PipelineCatalogEntry> {
    // URL encode the pipeline ID to handle 'nf-core/rnaseq' format
    const encodedId = encodeURIComponent(pipelineId);
    const url = `${this.baseUrl}/pipelines/${encodedId}`;
    const response = await fetch(url);

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Pipeline not found: ${pipelineId}`);
      }
      throw new Error(`Failed to get pipeline: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Execute a pipeline.
   */
  async executePipeline(
    request: ExecutePipelineRequest
  ): Promise<ExecutePipelineResponse> {
    const url = `${this.baseUrl}/pipelines/execute`;
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(
        `Failed to execute pipeline: ${error.detail || response.statusText}`
      );
    }

    return response.json();
  }

  /**
   * Get execution status.
   */
  async getExecutionStatus(
    executionId: string,
    options?: {
      includeLogs?: boolean;
      logLines?: number;
    }
  ): Promise<GetExecutionStatusResponse> {
    const params = new URLSearchParams();

    if (options?.includeLogs) {
      params.append("include_logs", "true");
    }
    if (options?.logLines) {
      params.append("log_lines", String(options.logLines));
    }

    const url = `${this.baseUrl}/pipelines/executions/${executionId}?${params.toString()}`;
    const response = await fetch(url);

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error(`Execution not found: ${executionId}`);
      }
      throw new Error(`Failed to get execution status: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * List all executions.
   */
  async listExecutions(options?: {
    pipelineId?: string;
    status?: PipelineStatus;
  }): Promise<PipelineExecution[]> {
    const params = new URLSearchParams();

    if (options?.pipelineId) {
      params.append("pipeline_id", options.pipelineId);
    }
    if (options?.status) {
      params.append("status", options.status);
    }

    const url = `${this.baseUrl}/pipelines/executions?${params.toString()}`;
    const response = await fetch(url);

    if (!response.ok) {
      throw new Error(`Failed to list executions: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Cancel a running execution.
   */
  async cancelExecution(executionId: string): Promise<{ message: string }> {
    const url = `${this.baseUrl}/pipelines/executions/${executionId}`;
    const response = await fetch(url, {
      method: "DELETE",
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(
        `Failed to cancel execution: ${error.detail || response.statusText}`
      );
    }

    return response.json();
  }

  /**
   * Get processed output from a completed execution.
   */
  async getExecutionOutput(executionId: string): Promise<PipelineOutput> {
    const url = `${this.baseUrl}/pipelines/executions/${executionId}/output`;
    const response = await fetch(url);

    if (!response.ok) {
      const error = await response.json();
      throw new Error(
        `Failed to get execution output: ${error.detail || response.statusText}`
      );
    }

    return response.json();
  }

  /**
   * Poll execution status until completion.
   *
   * @param executionId - Execution ID to monitor
   * @param onProgress - Callback for progress updates
   * @param pollInterval - Polling interval in milliseconds (default: 5000)
   * @returns Final execution status
   */
  async pollExecutionStatus(
    executionId: string,
    onProgress?: (execution: PipelineExecution) => void,
    pollInterval: number = 5000
  ): Promise<PipelineExecution> {
    const terminalStatuses: PipelineStatus[] = [
      "completed",
      "failed",
      "cancelled",
    ];

    while (true) {
      const { execution } = await this.getExecutionStatus(executionId);

      if (onProgress) {
        onProgress(execution);
      }

      if (terminalStatuses.includes(execution.status)) {
        return execution;
      }

      // Wait before next poll
      await new Promise((resolve) => setTimeout(resolve, pollInterval));
    }
  }
}

// Default client instance
export const pipelineClient = new PipelineClient(API_BASE_URL);
