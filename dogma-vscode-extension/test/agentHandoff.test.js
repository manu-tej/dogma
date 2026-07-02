"use strict";

const assert = require("assert");
const {
  buildAgentHandoffRecord,
  renderAgentHandoffMarkdown,
  renderCursorRules
} = require("../src/agentHandoff");

const record = buildAgentHandoffRecord({
  workspaceName: "dogma-demo-workspace",
  generatedAt: "2026-06-20T00:00:00.000Z",
  scan: {
    scan_source: "local service",
    issue_count: 3,
    issue_counts: { errors: 1, warnings: 2 },
    trust_status: "untrusted",
    human_data: true
  },
  activeEditor: {
    path: "pipeline.nf",
    language_id: "nextflow",
    selection: { is_empty: false }
  },
  settings: {
    agentProvider: "claude_subscription"
  },
  artifacts: {
    qurationStatus: { status: "ready" },
    qurationGraph: {
      graph_id: "graph-1",
      graph_url: "http://localhost:3000/canvas/graph-1"
    },
    qurationEdgeSelection: {
      selected_edge: {
        id: "edge-1",
        claim: "treatment changes transcript abundance",
        state: "untested"
      }
    },
    qurationEdgeWorkPackage: { contract_version: "dogma-quration-edge-work-package.v1" },
    ideReadiness: {
      status: "blocked",
      gates: [
        { id: "workspace_trust", state: "blocked" },
        { id: "methods_graph", state: "warning" }
      ]
    },
    methodsGraphPreflight: {
      service: "dogma-local-service",
      status: "configuration_gap",
      substrate_status: "configuration_gap",
      verdict: { status: "not_evaluable" },
      method_chain: { method_ids: ["nfcore.rnaseq.star_salmon"] },
      coverage_gaps: ["methods_graph.audited_substrate_missing", "methods_graph.container_missing"],
      next_actions: ["Configure DOGMA_METHODS_GRAPH_DB before real execution."]
    },
    llmProviderStatus: {
      provider: "claude_subscription",
      status: "ready"
    }
  }
});

assert.strictEqual(record.contract_version, "dogma-agent-handoff.v1");
assert.strictEqual(record.workspace.errors, 1);
assert.strictEqual(record.workspace.human_data, true);
assert.strictEqual(record.active_editor.path, "pipeline.nf");
assert.strictEqual(record.quration.graph_id, "graph-1");
assert.strictEqual(record.quration.selected_edge_id, "edge-1");
assert.strictEqual(record.guardrails.workspace_trust, "blocked");
assert.strictEqual(record.guardrails.methods_graph, "configuration_gap");
assert.strictEqual(record.methods_graph_preflight.status, "configuration_gap");
assert.deepStrictEqual(record.methods_graph_preflight.method_ids, ["nfcore.rnaseq.star_salmon"]);
assert(record.methods_graph_preflight.coverage_gaps.includes("methods_graph.container_missing"));
assert.strictEqual(record.artifacts.quration_edge_work_package, "present");
assert.strictEqual(record.artifacts.methods_graph_preflight, "present");
assert.strictEqual(record.output_paths.cursor_rules, ".cursor/rules/dogma-bioinformatics.mdc");

const markdown = renderAgentHandoffMarkdown(record);
assert(markdown.includes("# Dogma Agent Handoff"));
assert(markdown.includes("local IDE/co-scientist work"));
assert(markdown.includes("methods-graph remains the guardrail authority"));
assert(markdown.includes("dogma-demo-workspace"));
assert(markdown.includes("treatment changes transcript abundance"));
assert(markdown.includes("methods-graph is the authority"));
assert(markdown.includes("nfcore.rnaseq.star_salmon"));
assert(markdown.includes("methods_graph.container_missing"));
assert(markdown.includes("Configure DOGMA_METHODS_GRAPH_DB"));
assert(markdown.includes("Do not assert support/refute/resolved verdicts"));
assert(markdown.includes(".cursor/rules/dogma-bioinformatics.mdc"));

const rules = renderCursorRules(record);
assert(rules.includes("alwaysApply: true"));
assert(rules.includes("# Dogma Bioinformatics Guardrails"));
assert(rules.includes("quration graph: graph-1"));
assert(rules.includes("methods-graph preflight: configuration_gap"));
assert(rules.includes("methods_graph.audited_substrate_missing"));
assert(rules.includes("missing methods-graph method"));
assert(rules.includes("Do not run real workflows"));
assert(rules.includes("coverage gap"));

console.log("agent handoff renderer tests passed");
