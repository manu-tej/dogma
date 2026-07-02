"use strict";

const assert = require("assert");
const { renderSidecarHtml } = require("../src/sidecarView");

const html = renderSidecarHtml({
  scanSource: "local service",
  context: {
    assay: "bulk RNA-seq",
    organism: "human",
    reference: { genome_build: "GRCh38", annotation: "GENCODE v44" },
    workflowProcesses: ["FASTQC", "ALIGN_STAR"],
    fastqFiles: ["reads/SYN_004_R1.fastq"],
    samples: { count: 3, conditions: ["control", "treatment"] },
    counts: { fastqReads: 2 },
    trust: { status: "untrusted", trusted: false, human_data: true }
  },
  activeEditor: {
    path: "sample_sheet.csv",
    language_id: "csv",
    selection: { is_empty: false },
    selected_text: "SYN_001,control",
    current_line: "SYN_001,control,reads/SYN_001_R1.fastq.gz,reads/SYN_001_R2.fastq.gz"
  },
  artifacts: {
    qurationGraph: {
      contract_version: "dogma-quration-graph.v1",
      graph_id: "graph-123",
      graph_url: "http://localhost:3000/canvas/graph-123",
      query: "Does treatment change transcript abundance?",
      summary: { nodes: 6, edges: 1, edge_states: { untested: 1 } }
    },
    qurationEdgeSelection: {
      contract_version: "dogma-quration-edge-selection.v1",
      selected_edge: {
        id: "edge-1",
        claim: "treatment changes transcript abundance",
        state: "untested",
        validation_status: "unvalidated"
      },
      next_actions: ["Use Dogma quration edge commands to build a work package."]
    },
    qurationStatus: {
      contract_version: "dogma-quration-status.v1",
      status: "ready",
      backend: { reachable: true, status: "degraded" },
      canvas: { reachable: true }
    },
    llmProviderStatus: {
      service: "dogma-local-service",
      status: "ready",
      provider: "claude_subscription",
      claude_subscription: {
        resolved_cli_path: "/usr/local/bin/claude"
      }
    },
    qurationEdgeAgentSuggestion: {
      contract_version: "dogma-quration-edge-agent-suggestion.v1",
      edge_id: "edge-1",
      suggestion: {
        status: "ready_for_review",
        patch_preview_count: 2,
        llm_executed: false
      }
    },
    agentHandoff: {
      contract_version: "dogma-agent-handoff.v1",
      workspace: { name: "dogma-demo-workspace" },
      guardrails: { methods_graph: "configuration_gap" },
      output_paths: { cursor_rules: ".cursor/rules/dogma-bioinformatics.mdc" }
    },
    methodsGraphPreflight: {
      service: "dogma-local-service",
      status: "configuration_gap",
      substrate_status: "configuration_gap",
      coverage_gaps: ["methods_graph.audited_substrate_missing"]
    },
    ideReadiness: {
      contract_version: "dogma-ide-readiness.v1",
      status: "blocked",
      gates: [
        { id: "workspace_trust", state: "blocked", detail: "untrusted human data workspace" },
        { id: "methods_graph", state: "warning", detail: "coverage gap" },
        { id: "quration", state: "ready", detail: "ready" }
      ],
      next_actions: ["Run `Dogma: Check Workspace Trust` before local operations."]
    }
  },
  issues: [
    {
      severity: "error",
      file: "sample_sheet.csv",
      line: 3,
      message: "Duplicate sample_id."
    },
    {
      severity: "warning",
      file: "metadata.json",
      line: 1,
      message: "Annotation missing."
    }
  ]
});

assert(html.includes("Dogma"));
assert(html.includes("local service"));
assert(html.includes("blocked"));
assert(html.includes("bulk RNA-seq"));
assert(html.includes("Active Investigation"));
assert(html.includes("graph-123"));
assert(html.includes("Does treatment change transcript abundance?"));
assert(html.includes("6 node(s), 1 edge(s); untested"));
assert(html.includes("treatment changes transcript abundance"));
assert(html.includes("untested/unvalidated"));
assert(html.includes("ready; degraded; canvas reachable"));
assert(html.includes("blocked; 1 blocked, 1 warning"));
assert(html.includes("claude_subscription: ready; CLI found"));
assert(html.includes("methods-graph"));
assert(html.includes("configuration_gap; configuration_gap; 1 coverage gap(s)"));
assert(html.includes("Agent handoff"));
assert(html.includes("dogma-demo-workspace; methods-graph configuration_gap; .cursor/rules/dogma-bioinformatics.mdc"));
assert(html.includes("ready_for_review; 2 patch proposal(s); prompt-ready"));
assert(html.includes("Trust Workspace: untrusted human data workspace"));
assert(html.includes("dogma.runNextIdeAction"));
assert(html.includes("Run Next: Trust Workspace"));
assert(html.includes("Bioinformatics State"));
assert(html.includes("2 reads"));
assert(html.includes("control, treatment"));
assert(html.includes("untrusted"));
assert(html.includes("local operations gated"));
assert(html.includes("GRCh38"));
assert(html.includes("FASTQC"));
assert(html.includes("Active File"));
assert(html.includes("Active File Findings"));
assert(html.includes("selected text included"));
assert(html.includes("1 in this file"));
assert(html.includes("Duplicate sample_id."));
assert(html.includes("dogma.openFinding"));
assert(html.includes("data-payload=\"{&quot;file&quot;:&quot;sample_sheet.csv&quot;,&quot;line&quot;:3}\""));
assert(html.includes("data-payload=\"{&quot;file&quot;:&quot;metadata.json&quot;,&quot;line&quot;:1}\""));
assert(html.includes("payloadFor(button)"));
assert(html.includes("dogma.prepareIdeSession"));
assert(html.includes("Prepare IDE Session"));
assert(html.includes("dogma.checkIdeReadiness"));
assert(html.includes("Check IDE Readiness"));
assert(html.includes("dogma.scanWithLocalService"));
assert(html.includes("dogma.previewActiveBioFile"));
assert(html.includes("dogma.askDogmaAboutSelection"));
assert(html.includes("dogma.previewActiveFilePatch"));
assert(html.includes("dogma.applyActiveFilePatch"));
assert(html.includes("dogma.reviewActiveFinding"));
assert(html.includes("dogma.openAgentWorkbench"));
assert(html.includes("dogma.generateAgentHandoff"));
assert(html.includes("Agent Handoff"));
assert(html.includes("dogma.reviewActiveFile"));
assert(html.includes("dogma.openBiologicalGraphWorkbench"));
assert(html.includes("Local Biological Guardrails"));
assert(!html.includes("Open Biological Graph"));
assert(html.includes("quration"));
assert(html.includes("dogma.importWorkspaceToQuration"));
assert(html.includes("Import To quration"));
assert(html.includes("dogma.checkQurationStatus"));
assert(html.includes("Check quration Status"));
assert(html.includes("dogma.refreshQurationGraphHistory"));
assert(html.includes("Refresh Graph History"));
assert(html.includes("dogma.pullQurationGraphContext"));
assert(html.includes("Pull Graph Context"));
assert(html.includes("dogma.openCurrentQurationGraph"));
assert(html.includes("Open Current Graph"));
assert(html.includes("dogma.pullQurationGraphEvents"));
assert(html.includes("Pull Graph Events"));
assert(html.includes("dogma.pullQurationFailedEvents"));
assert(html.includes("Pull Failed Events"));
assert(html.includes("dogma.selectQurationEdge"));
assert(html.includes("Select quration Edge"));
assert(html.includes("dogma.fetchQurationEdgePlan"));
assert(html.includes("Fetch quration Edge Plan"));
assert(html.includes("dogma.generateQurationEdgeEvaluationPlan"));
assert(html.includes("quration Edge Plan"));
assert(html.includes("dogma.generateQurationEdgeWorkPackage"));
assert(html.includes("Edge Work Package"));
assert(html.includes("dogma.suggestFromQurationEdgeWorkPackage"));
assert(html.includes("Suggest From Edge Package"));
assert(html.includes("dogma.previewQurationEdgeSuggestedPatch"));
assert(html.includes("Preview Edge Patch"));
assert(html.includes("dogma.generateQurationEdgePatchHandoff"));
assert(html.includes("Edge Patch Handoff"));
assert(html.includes("dogma.resolveQurationSelectedEdgeReadout"));
assert(html.includes("Resolve Edge Readout"));
assert(html.includes("dogma.applyQurationEdgeSuggestedPatch"));
assert(html.includes("Apply Edge Patch"));
assert(html.includes("dogma.openLastQurationImport"));
assert(html.includes("Open Last Import"));
assert(html.includes("dogma.generateQurationHandoff"));
assert(html.includes("dogma.openQurationCanvasFromWorkspace"));
assert(html.includes("dogma.openQurationGraphUi"));
assert(html.includes("Guardrails"));
assert(html.includes("dogma.generateMethodsGraphPreflight"));
assert(html.includes("dogma.generateMethodsGraphSubstrate"));
assert(html.includes("dogma.generateMethodGuardrails"));
assert(html.includes("dogma.generateEvidenceLedger"));
assert(html.includes("dogma.generateEdgeEvaluationPlan"));
assert(html.includes("dogma.checkLlmProvider"));
assert(html.includes("Local Service"));
assert(html.includes("dogma.checkWorkspaceTrust"));
assert(html.includes("dogma.trustWorkspaceForLocalOperations"));
assert(html.includes("acquireVsCodeApi"));

const emptyHtml = renderSidecarHtml();
assert(emptyHtml.includes("waiting"));
assert(emptyHtml.includes("No Dogma findings yet"));
assert(emptyHtml.includes("No file-backed active editor"));
assert(emptyHtml.includes("No active Dogma investigation artifacts yet"));
assert(emptyHtml.includes("Scan With Local Service"));

console.log("sidecar view tests passed");
