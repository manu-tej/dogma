"use strict";

const assert = require("assert");
const {
  applyPatchWithLocalService,
  executeWithLocalService,
  getAgentSuggestionWithLocalService,
  getAssistantContextWithLocalService,
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
  normalizeServiceScanResult,
  scanWithLocalService,
  trustWorkspaceWithLocalService
} = require("../src/localServiceClient");

const payload = {
  service: "dogma-local-service",
  version: "0.1.0",
  root: "/workspace/demo",
  files: [
    { path: "sample_sheet.csv", type: "sample_sheet", size: 100 },
    { path: "intervals.bed", type: "bed", size: 50 }
  ],
  summary: {
    errors: 1,
    warnings: 2,
    risk_level: "blocked",
    genome_build: "GRCh38",
    samples: 3,
    workflow_files: ["pipeline.nf"],
    workflow_processes: ["FASTQC"]
  },
  trust: {
    status: "untrusted",
    trusted: false,
    human_data: true,
    blockers: ["Human data is detected."]
  },
  context: {
    sample_file: "sample_sheet.csv",
    metadata_files: ["metadata.json"],
    workflow_files: ["pipeline.nf"],
    workflow_processes: ["FASTQC"],
    bed_files: [{ path: "intervals.bed", intervals: 3 }],
    vcf_files: [{ path: "variants.vcf", records: 2 }],
    annotation_files: [{ path: "genes.gtf", features: 3, feature_types: ["gene"] }],
    fastq_files: [{ path: "reads/S1_R1.fastq.gz", reads: 2, bases: 16, gc_percent: 50 }],
    samples: {
      count: 3,
      ids: ["S1", "S2", "S3"],
      conditions: ["control"],
      strandedness: ["reverse"]
    },
    reference: {
      genome_build: "GRCh38",
      annotation: "GENCODE v44"
    },
    privacy: {
      human_data: true
    },
    data_inventory: {
      fastq: ["reads/S1_R1.fastq.gz"],
      bam: [],
      cram: []
    },
    qc_reports: [{ path: "multiqc_general_stats.txt", samples: 3, metrics: 8 }]
  },
  issues: [
    {
      severity: "error",
      file: "sample_sheet.csv",
      line: 3,
      code: "sample_sheet.duplicate_sample_id",
      message: "Duplicate sample_id."
    }
  ]
};

assert.strictEqual(joinEndpoint("http://127.0.0.1:8765", "/scan"), "http://127.0.0.1:8765/scan");
assert.strictEqual(joinEndpoint("http://127.0.0.1:8765/api/", "/scan"), "http://127.0.0.1:8765/api/scan");

assert.deepStrictEqual(normalizeIssue({ file: "x.bed" }), {
  severity: "info",
  file: "x.bed",
  line: 1,
  message: "Dogma service finding.",
  code: undefined
});

const normalized = normalizeServiceScanResult(payload);
assert.strictEqual(normalized.source, "local service");
assert.strictEqual(normalized.issues[0].code, "sample_sheet.duplicate_sample_id");
assert.strictEqual(normalized.context.scanSource, "local service");
assert.strictEqual(normalized.context.sampleFile, "sample_sheet.csv");
assert.strictEqual(normalized.context.metadataFile, "metadata.json");
assert.deepStrictEqual(normalized.context.workflowFiles, ["pipeline.nf"]);
assert.deepStrictEqual(normalized.context.workflowProcesses, ["FASTQC"]);
assert.deepStrictEqual(normalized.context.bedFiles, ["intervals.bed"]);
assert.deepStrictEqual(normalized.context.vcfFiles, ["variants.vcf"]);
assert.deepStrictEqual(normalized.context.annotationFiles, ["genes.gtf"]);
assert.deepStrictEqual(normalized.context.fastqFiles, ["reads/S1_R1.fastq.gz"]);
assert.strictEqual(normalized.context.samples.count, 3);
assert.strictEqual(normalized.context.reference.genome_build, "GRCh38");
assert.strictEqual(normalized.context.privacy.contains_human_data, true);
assert.strictEqual(normalized.trust.status, "untrusted");
assert.strictEqual(normalized.context.trust.status, "untrusted");
assert.strictEqual(normalized.context.summary.risk_level, "blocked");
assert.strictEqual(normalized.context.counts.intervals, 3);
assert.strictEqual(normalized.context.counts.variants, 2);
assert.strictEqual(normalized.context.counts.annotations, 3);
assert.strictEqual(normalized.context.counts.fastqReads, 2);
assert.strictEqual(normalized.context.counts.fastqBases, 16);
assert.deepStrictEqual(normalized.context.dataInventory.fastq, ["reads/S1_R1.fastq.gz"]);
assert.strictEqual(normalized.context.qcReports[0].metrics, 8);

(async () => {
  const result = await scanWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/scan");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.root, "/workspace/demo");
      assert.strictEqual(options.body.max_files, 25);
      return payload;
    }
  });
  assert.strictEqual(result.context.sampleFile, "sample_sheet.csv");

  const runPlan = await getRunPlanWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/run-plan");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.root, "/workspace/demo");
      return { status: "blocked", commands: [] };
    }
  });
  assert.strictEqual(runPlan.status, "blocked");

  const assistantContext = await getAssistantContextWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/assistant-context");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.root, "/workspace/demo");
      assert.strictEqual(options.body.max_files, 25);
      return { redaction: { sample_ids_redacted: true }, markdown: "# Dogma Assistant Context Bundle\n" };
    }
  });
  assert.strictEqual(assistantContext.redaction.sample_ids_redacted, true);

  const guardrails = await getMethodGuardrailsWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/guardrails");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.root, "/workspace/demo");
      assert.strictEqual(options.body.max_files, 25);
      return { summary: { pass: 1 }, checks: [{ code: "quration.factual_ledger_not_verdict" }] };
    }
  });
  assert.strictEqual(guardrails.summary.pass, 1);

  const ledger = await getEvidenceLedgerWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/evidence-ledger");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.root, "/workspace/demo");
      assert.strictEqual(options.body.max_files, 25);
      return { summary: { total: 2 }, entries: [{ id: "workspace-context" }] };
    }
  });
  assert.strictEqual(ledger.summary.total, 2);

  const edgePlan = await getEdgeEvaluationPlanWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    selectedEdge: {
      id: "pipeline.nf:FASTQC->ALIGN_STAR:1",
      from: "FASTQC",
      to: "ALIGN_STAR",
      title: "FASTQC -> ALIGN_STAR"
    },
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/edge-evaluation-plan");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.root, "/workspace/demo");
      assert.strictEqual(options.body.max_files, 25);
      assert.strictEqual(options.body.selected_edge.from, "FASTQC");
      assert.strictEqual(options.body.selected_edge.to, "ALIGN_STAR");
      return { task_class: "differential_expression", selected_edge: options.body.selected_edge, contracts: [{ stage: "Readout" }] };
    }
  });
  assert.strictEqual(edgePlan.task_class, "differential_expression");
  assert.strictEqual(edgePlan.selected_edge.id, "pipeline.nf:FASTQC->ALIGN_STAR:1");

  const biologicalGraph = await getBiologicalGraphWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/biological-graph");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.root, "/workspace/demo");
      assert.strictEqual(options.body.max_files, 25);
      return { task_class: "differential_expression", edges: [{ id: "bioedge.condition_transcript_abundance" }] };
    }
  });
  assert.strictEqual(biologicalGraph.edges[0].id, "bioedge.condition_transcript_abundance");

  const qurationHandoff = await getQurationHandoffWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/quration-handoff");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.root, "/workspace/demo");
      assert.strictEqual(options.body.max_files, 25);
      return { contract_version: "quration-handoff.v1", causal_graph: { edges: [{ state: "untested" }] } };
    }
  });
  assert.strictEqual(qurationHandoff.contract_version, "quration-handoff.v1");
  assert.strictEqual(qurationHandoff.causal_graph.edges[0].state, "untested");

  const substrate = await getMethodsGraphSubstrateWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/methods-graph-substrate");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.root, "/workspace/demo");
      return { status: "configuration_gap", authoritative_surface: [] };
    }
  });
  assert.strictEqual(substrate.status, "configuration_gap");

  const preflight = await getMethodsGraphPreflightWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/methods-graph-preflight");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.root, "/workspace/demo");
      assert.strictEqual(options.body.max_files, 25);
      return { status: "configuration_gap", coverage_gaps: ["methods_graph.audited_substrate_missing"] };
    }
  });
  assert.strictEqual(preflight.status, "configuration_gap");

  const llmStatus = await getLlmStatusWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    provider: "claude_subscription",
    cliPath: "/usr/local/bin/claude",
    model: "sonnet",
    timeoutSeconds: 180,
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/llm-status");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.root, "/workspace/demo");
      assert.strictEqual(options.body.provider, "claude_subscription");
      assert.strictEqual(options.body.cli_path, "/usr/local/bin/claude");
      assert.strictEqual(options.body.model, "sonnet");
      assert.strictEqual(options.body.timeout_seconds, 180);
      return { status: "ready", provider: "claude_subscription" };
    }
  });
  assert.strictEqual(llmStatus.provider, "claude_subscription");

  const agentSuggestion = await getAgentSuggestionWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    instruction: "Suggest next edit",
    useLlm: true,
    provider: "claude_subscription",
    cliPath: "claude",
    model: "sonnet",
    timeoutSeconds: 180,
    editorContext: {
      path: "sample_sheet.csv",
      language_id: "csv",
      selected_text: "SYN_001,control"
    },
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/agent-suggestion");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.root, "/workspace/demo");
      assert.strictEqual(options.body.instruction, "Suggest next edit");
      assert.strictEqual(options.body.use_llm, true);
      assert.strictEqual(options.body.provider, "claude_subscription");
      assert.strictEqual(options.body.cli_path, "claude");
      assert.strictEqual(options.body.model, "sonnet");
      assert.strictEqual(options.body.timeout_seconds, 180);
      assert.strictEqual(options.body.editor_context.path, "sample_sheet.csv");
      assert.strictEqual(options.body.editor_context.selected_text, "SYN_001,control");
      return { status: "llm_completed", llm_executed: true };
    }
  });
  assert.strictEqual(agentSuggestion.status, "llm_completed");

  const execution = await executeWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    commandId: "nextflow-1",
    timeoutSeconds: 10,
    execute: false,
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/execute");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.command_id, "nextflow-1");
      assert.strictEqual(options.body.timeout_seconds, 10);
      assert.strictEqual(options.body.execute, false);
      return { status: "preview", executed: false };
    }
  });
  assert.strictEqual(execution.status, "preview");

  const proposals = await getPatchProposalsWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/patch-proposals");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.root, "/workspace/demo");
      return { proposal_count: 1, proposals: [] };
    }
  });
  assert.strictEqual(proposals.proposal_count, 1);

  const patchPreview = await applyPatchWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    proposalId: "nextflow-sample-validation-1",
    maxFiles: 25,
    apply: false,
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/apply-patch");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.proposal_id, "nextflow-sample-validation-1");
      assert.strictEqual(options.body.apply, false);
      return { status: "preview", applied: false };
    }
  });
  assert.strictEqual(patchPreview.status, "preview");

  const trustStatus = await getTrustStatusWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/scan");
      assert.strictEqual(options.body.root, "/workspace/demo");
      return payload;
    }
  });
  assert.strictEqual(trustStatus.trust.status, "untrusted");

  const trusted = await trustWorkspaceWithLocalService({
    serviceUrl: "http://127.0.0.1:8765",
    rootPath: "/workspace/demo",
    maxFiles: 25,
    reason: "unit test",
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://127.0.0.1:8765/trust");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.body.reason, "unit test");
      return { trust: { status: "trusted" }, write: { status: "written" } };
    }
  });
  assert.strictEqual(trusted.trust.status, "trusted");
  console.log("local service client tests passed");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
