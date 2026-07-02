"use strict";

const http = require("http");
const https = require("https");

function joinEndpoint(baseUrl, endpoint) {
  const url = new URL(baseUrl);
  const basePath = url.pathname.replace(/\/$/, "");
  url.pathname = `${basePath}${endpoint}`;
  return url.toString();
}

function requestJson(url, options = {}) {
  const timeoutMs = options.timeoutMs || 2000;
  const method = options.method || (options.body ? "POST" : "GET");
  const body = options.body ? JSON.stringify(options.body) : undefined;
  const parsed = new URL(url);
  const transport = parsed.protocol === "https:" ? https : http;

  return new Promise((resolve, reject) => {
    const request = transport.request(
      parsed,
      {
        method,
        headers: {
          Accept: "application/json",
          ...(body ? { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) } : {})
        }
      },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          let payload = {};
          if (text.trim()) {
            try {
              payload = JSON.parse(text);
            } catch (error) {
              reject(new Error(`Dogma local service returned invalid JSON: ${error.message}`));
              return;
            }
          }

          if (response.statusCode < 200 || response.statusCode >= 300) {
            const message = payload.message || payload.error || `HTTP ${response.statusCode}`;
            reject(new Error(`Dogma local service request failed: ${message}`));
            return;
          }

          resolve(payload);
        });
      }
    );

    request.on("error", (error) => reject(error));
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error(`Dogma local service timed out after ${timeoutMs} ms`));
    });
    if (body) request.write(body);
    request.end();
  });
}

function normalizeIssue(issue) {
  return {
    severity: issue.severity || "info",
    file: issue.file || "workspace",
    line: Number(issue.line || 1),
    message: issue.message || issue.code || "Dogma service finding.",
    code: issue.code
  };
}

function itemPath(item) {
  return typeof item === "string" ? item : item.path;
}

function sumField(items, field) {
  return items.reduce((total, item) => total + Number((typeof item === "object" && item[field]) || 0), 0);
}

function normalizeServiceContext(serviceContext = {}, summary = {}, trust = {}) {
  const bedItems = serviceContext.bed_files || [];
  const vcfItems = serviceContext.vcf_files || [];
  const annotationItems = serviceContext.annotation_files || [];
  const fastqItems = serviceContext.fastq_files || [];
  const reference = serviceContext.reference || {};
  const privacy = serviceContext.privacy || {};
  const metadataFiles = serviceContext.metadata_files || [];
  const sampleInfo = serviceContext.samples || {};

  return {
    scanSource: "local service",
    summary,
    trust,
    sampleFile: serviceContext.sample_file || undefined,
    metadataFile: metadataFiles[0],
    workflowFiles: serviceContext.workflow_files || summary.workflow_files || [],
    bedFiles: bedItems.map(itemPath).filter(Boolean),
    vcfFiles: vcfItems.map(itemPath).filter(Boolean),
    annotationFiles: annotationItems.map(itemPath).filter(Boolean),
    fastqFiles: fastqItems.map(itemPath).filter(Boolean),
    samples: {
      count: Number(sampleInfo.count || summary.samples || 0),
      conditions: sampleInfo.conditions || summary.conditions || [],
      strandedness: sampleInfo.strandedness || [],
      ids: sampleInfo.ids || []
    },
    reference: {
      ...reference,
      genome_build: reference.genome_build || summary.genome_build,
      annotation: reference.annotation || summary.annotation
    },
    privacy: {
      ...privacy,
      contains_human_data: privacy.contains_human_data ?? privacy.human_data ?? summary.human_data
    },
    counts: {
      intervals: sumField(bedItems, "intervals"),
      variants: sumField(vcfItems, "records"),
      annotations: sumField(annotationItems, "features"),
      fastqReads: sumField(fastqItems, "reads"),
      fastqBases: sumField(fastqItems, "bases")
    },
    qcReports: serviceContext.qc_reports || [],
    dataInventory: serviceContext.data_inventory || { fastq: [], bam: [], cram: [] },
    workflowGraphs: [],
    workflowProcesses: serviceContext.workflow_processes || summary.workflow_processes || [],
    workflowCalls: serviceContext.workflow_includes || []
  };
}

function normalizeServiceScanResult(payload) {
  return {
    source: "local service",
    service: payload.service,
    version: payload.version,
    root: payload.root,
    files: payload.files || [],
    summary: payload.summary || {},
    trust: payload.trust || {},
    issues: (payload.issues || []).map(normalizeIssue),
    context: normalizeServiceContext(payload.context || {}, payload.summary || {}, payload.trust || {})
  };
}

async function scanWithLocalService(options) {
  const request = options.requestJson || requestJson;
  const endpoint = joinEndpoint(options.serviceUrl, "/scan");
  const payload = await request(endpoint, {
    method: "POST",
    body: {
      root: options.rootPath,
      max_files: options.maxFiles
    },
    timeoutMs: options.timeoutMs
  });
  return normalizeServiceScanResult(payload);
}

async function getRunPlanWithLocalService(options) {
  const request = options.requestJson || requestJson;
  return request(joinEndpoint(options.serviceUrl, "/run-plan"), {
    method: "POST",
    body: {
      root: options.rootPath,
      max_files: options.maxFiles
    },
    timeoutMs: options.timeoutMs
  });
}

async function getAssistantContextWithLocalService(options) {
  const request = options.requestJson || requestJson;
  return request(joinEndpoint(options.serviceUrl, "/assistant-context"), {
    method: "POST",
    body: {
      root: options.rootPath,
      max_files: options.maxFiles
    },
    timeoutMs: options.timeoutMs
  });
}

async function getMethodGuardrailsWithLocalService(options) {
  const request = options.requestJson || requestJson;
  return request(joinEndpoint(options.serviceUrl, "/guardrails"), {
    method: "POST",
    body: {
      root: options.rootPath,
      max_files: options.maxFiles
    },
    timeoutMs: options.timeoutMs
  });
}

async function getEvidenceLedgerWithLocalService(options) {
  const request = options.requestJson || requestJson;
  return request(joinEndpoint(options.serviceUrl, "/evidence-ledger"), {
    method: "POST",
    body: {
      root: options.rootPath,
      max_files: options.maxFiles
    },
    timeoutMs: options.timeoutMs
  });
}

async function getEdgeEvaluationPlanWithLocalService(options) {
  const request = options.requestJson || requestJson;
  const body = {
    root: options.rootPath,
    max_files: options.maxFiles
  };
  if (options.selectedEdge) {
    body.selected_edge = options.selectedEdge;
  }
  return request(joinEndpoint(options.serviceUrl, "/edge-evaluation-plan"), {
    method: "POST",
    body,
    timeoutMs: options.timeoutMs
  });
}

async function getBiologicalGraphWithLocalService(options) {
  const request = options.requestJson || requestJson;
  return request(joinEndpoint(options.serviceUrl, "/biological-graph"), {
    method: "POST",
    body: {
      root: options.rootPath,
      max_files: options.maxFiles
    },
    timeoutMs: options.timeoutMs
  });
}

async function getQurationHandoffWithLocalService(options) {
  const request = options.requestJson || requestJson;
  return request(joinEndpoint(options.serviceUrl, "/quration-handoff"), {
    method: "POST",
    body: {
      root: options.rootPath,
      max_files: options.maxFiles
    },
    timeoutMs: options.timeoutMs
  });
}

async function getMethodsGraphSubstrateWithLocalService(options) {
  const request = options.requestJson || requestJson;
  return request(joinEndpoint(options.serviceUrl, "/methods-graph-substrate"), {
    method: "POST",
    body: {
      root: options.rootPath,
      max_files: options.maxFiles
    },
    timeoutMs: options.timeoutMs
  });
}

async function getMethodsGraphPreflightWithLocalService(options) {
  const request = options.requestJson || requestJson;
  return request(joinEndpoint(options.serviceUrl, "/methods-graph-preflight"), {
    method: "POST",
    body: {
      root: options.rootPath,
      max_files: options.maxFiles
    },
    timeoutMs: options.timeoutMs
  });
}

async function getLlmStatusWithLocalService(options) {
  const request = options.requestJson || requestJson;
  return request(joinEndpoint(options.serviceUrl, "/llm-status"), {
    method: "POST",
    body: {
      root: options.rootPath,
      max_files: options.maxFiles,
      provider: options.provider,
      cli_path: options.cliPath,
      model: options.model,
      timeout_seconds: options.timeoutSeconds
    },
    timeoutMs: options.timeoutMs
  });
}

async function getAgentSuggestionWithLocalService(options) {
  const request = options.requestJson || requestJson;
  return request(joinEndpoint(options.serviceUrl, "/agent-suggestion"), {
    method: "POST",
    body: {
      root: options.rootPath,
      max_files: options.maxFiles,
      instruction: options.instruction,
      use_llm: Boolean(options.useLlm),
      provider: options.provider,
      cli_path: options.cliPath,
      model: options.model,
      timeout_seconds: options.timeoutSeconds,
      editor_context: options.editorContext
    },
    timeoutMs: options.timeoutMs
  });
}

async function executeWithLocalService(options) {
  const request = options.requestJson || requestJson;
  return request(joinEndpoint(options.serviceUrl, "/execute"), {
    method: "POST",
    body: {
      root: options.rootPath,
      max_files: options.maxFiles,
      command_id: options.commandId,
      timeout_seconds: options.timeoutSeconds,
      execute: Boolean(options.execute)
    },
    timeoutMs: options.timeoutMs
  });
}

async function getPatchProposalsWithLocalService(options) {
  const request = options.requestJson || requestJson;
  return request(joinEndpoint(options.serviceUrl, "/patch-proposals"), {
    method: "POST",
    body: {
      root: options.rootPath,
      max_files: options.maxFiles
    },
    timeoutMs: options.timeoutMs
  });
}

async function applyPatchWithLocalService(options) {
  const request = options.requestJson || requestJson;
  return request(joinEndpoint(options.serviceUrl, "/apply-patch"), {
    method: "POST",
    body: {
      root: options.rootPath,
      max_files: options.maxFiles,
      proposal_id: options.proposalId,
      apply: Boolean(options.apply)
    },
    timeoutMs: options.timeoutMs
  });
}

async function getTrustStatusWithLocalService(options) {
  const result = await scanWithLocalService(options);
  return {
    service: result.service,
    root: result.root,
    trust: result.trust,
    summary: result.summary
  };
}

async function trustWorkspaceWithLocalService(options) {
  const request = options.requestJson || requestJson;
  return request(joinEndpoint(options.serviceUrl, "/trust"), {
    method: "POST",
    body: {
      root: options.rootPath,
      max_files: options.maxFiles,
      reason: options.reason
    },
    timeoutMs: options.timeoutMs
  });
}

async function checkLocalService(options) {
  const request = options.requestJson || requestJson;
  return request(joinEndpoint(options.serviceUrl, "/health"), {
    method: "GET",
    timeoutMs: options.timeoutMs
  });
}

module.exports = {
  applyPatchWithLocalService,
  checkLocalService,
  executeWithLocalService,
  getAssistantContextWithLocalService,
  getAgentSuggestionWithLocalService,
  getBiologicalGraphWithLocalService,
  getEdgeEvaluationPlanWithLocalService,
  getEvidenceLedgerWithLocalService,
  getLlmStatusWithLocalService,
  getMethodGuardrailsWithLocalService,
  getMethodsGraphPreflightWithLocalService,
  getMethodsGraphSubstrateWithLocalService,
  getPatchProposalsWithLocalService,
  getQurationHandoffWithLocalService,
  getRunPlanWithLocalService,
  getTrustStatusWithLocalService,
  joinEndpoint,
  normalizeIssue,
  normalizeServiceContext,
  normalizeServiceScanResult,
  requestJson,
  scanWithLocalService,
  trustWorkspaceWithLocalService
};
