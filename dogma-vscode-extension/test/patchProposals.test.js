"use strict";

const assert = require("assert");
const { renderPatchApplyResult, renderPatchProposals } = require("../src/patchProposals");

const result = {
  root: "/workspace/demo",
  proposal_count: 2,
  scan_summary: { risk_level: "blocked", errors: 3, warnings: 8 },
  methods_graph_preflight: {
    status: "configuration_gap",
    substrate_status: "missing",
    verdict: null,
    method_chain: { method_ids: ["m:fastqc"] },
    coverage_gaps: ["methods_graph.audited_substrate_missing"],
    next_actions: ["Configure DOGMA_METHODS_GRAPH_DB to an audited Kuzu database with ingest.lock.json."]
  },
  proposals: [
    {
      id: "nextflow-sample-validation-1",
      title: "Add sample sheet row validation",
      kind: "nextflow.sample_sheet_validation",
      severity: "warning",
      target_file: "pipeline.nf",
      rationale: "Validate rows before tuple creation.",
      safety: { requires_review: true, auto_apply: false, scope: "single-file Nextflow text edit" },
      diff: "--- a/pipeline.nf\n+++ b/pipeline.nf\n+def validateSampleRow(row) {}\n"
    },
    {
      id: "metadata-sample-id-policy-1",
      title: "Add sample identifier policy",
      kind: "metadata.missing_sample_id_policy",
      severity: "warning",
      target_file: "metadata.json",
      rationale: "Declare sample identifier handling.",
      safety: { requires_review: true, auto_apply: false, scope: "single-file metadata JSON edit" },
      diff: "--- a/metadata.json\n+++ b/metadata.json\n+    \"sample_id_policy\": \"Sample identifiers must be unique\"\n"
    }
  ]
};

const rendered = renderPatchProposals(result);
assert(rendered.includes("# Dogma Patch Proposals"));
assert(rendered.includes("Proposal count: 2"));
assert(rendered.includes("nextflow.sample_sheet_validation"));
assert(rendered.includes("metadata.missing_sample_id_policy"));
assert(rendered.includes("```diff"));
assert(rendered.includes("+def validateSampleRow"));
assert(rendered.includes("single-file metadata JSON edit"));
assert(rendered.includes("## Methods-Graph Preflight"));
assert(rendered.includes("Status: configuration_gap"));
assert(rendered.includes("methods_graph.audited_substrate_missing"));

const applyResult = renderPatchApplyResult({
  status: "preview",
  applied: false,
  message: "Patch was not applied.",
  proposal: result.proposals[0],
  methods_graph_preflight: result.methods_graph_preflight
});
assert(applyResult.includes("# Dogma Patch Apply Result"));
assert(applyResult.includes("Applied: false"));
assert(applyResult.includes("pipeline.nf"));
assert(applyResult.includes("Configure DOGMA_METHODS_GRAPH_DB"));

console.log("patch proposal renderer tests passed");
