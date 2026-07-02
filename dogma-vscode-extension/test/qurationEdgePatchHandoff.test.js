"use strict";

const assert = require("assert");
const {
  buildGraphEditCandidate,
  buildQurationEdgePatchHandoff,
  renderQurationEdgePatchHandoff
} = require("../src/qurationEdgePatchHandoff");

const workPackage = {
  contract_version: "dogma-quration-edge-work-package.v1",
  generated_at: "2026-06-20T00:10:00.000Z",
  edge_id: "bioedge.condition_transcript_abundance",
  quration_graph: {
    graph_id: "graph-1",
    graph_url: "http://localhost:3000/canvas/graph-1",
    query: "Does control vs treatment change transcript abundance?"
  },
  selected_edge: {
    id: "bioedge.condition_transcript_abundance",
    title: "control vs treatment changes Transcript abundance",
    relation: "changes",
    status: "untested/unvalidated"
  },
  quration_edge_plan: {
    plan: {
      expected_direction: "increase"
    }
  },
  dogma_edge_evaluation: {
    plan: {
      status: "blocked",
      task_class: "differential_expression",
      coverage_gaps: [
        "methods_graph.audited_substrate_missing",
        "quration.edge.unvalidated"
      ],
      contracts: [
        {
          stage: "Grounding",
          status: "coverage_gap",
          detail: "No audited methods graph configured."
        }
      ]
    }
  }
};

const patchPreview = {
  status: "preview",
  applied: false,
  message: "Patch was not applied.",
  proposal: {
    id: "nextflow-sample-validation-1",
    title: "Validate sample rows",
    kind: "nextflow_sample_validation",
    target_file: "pipeline.nf",
    diff: "--- a/pipeline.nf\n+++ b/pipeline.nf\n+def validateSampleRow(row) {}",
    safety: {
      scope: "single_file",
      requires_review: true,
      auto_apply: false
    }
  }
};

const candidate = buildGraphEditCandidate(workPackage, patchPreview.proposal);
assert.deepStrictEqual(candidate, {
  op: "set_test",
  edge_id: "bioedge.condition_transcript_abundance",
  pipeline: "local:pipeline.nf",
  data_accession: null,
  expected: "increase"
});

assert.strictEqual(buildGraphEditCandidate(workPackage, { target_file: "README.md" }), null);

const handoff = buildQurationEdgePatchHandoff({
  workPackage,
  patchPreview,
  generatedAt: "2026-06-20T00:12:00.000Z"
});

assert.strictEqual(handoff.contract_version, "dogma-quration-edge-patch-handoff.v1");
assert.strictEqual(handoff.quration_graph.graph_id, "graph-1");
assert.strictEqual(handoff.selected_edge.id, "bioedge.condition_transcript_abundance");
assert.strictEqual(handoff.local_patch.proposal_id, "nextflow-sample-validation-1");
assert.strictEqual(handoff.local_patch.applied, false);
assert.strictEqual(handoff.quration_review.graph_edit_candidate_status, "review_only_not_applied");
assert.strictEqual(handoff.quration_review.graph_edit_candidate.op, "set_test");
assert.strictEqual(handoff.dogma_guardrails.status, "blocked");
assert(handoff.dogma_guardrails.coverage_gaps.includes("quration.edge.unvalidated"));
assert(handoff.source_artifacts.includes(".dogma/patch-apply-preview.md"));

const applied = buildQurationEdgePatchHandoff({
  workPackage,
  patchPreview,
  patchApply: { ...patchPreview, status: "applied", applied: true, message: "Patch applied." },
  generatedAt: "2026-06-20T00:13:00.000Z"
});
assert.strictEqual(applied.local_patch.applied, true);
assert.strictEqual(applied.local_patch.apply_status, "applied");
assert(applied.source_artifacts.includes(".dogma/patch-apply-result.md"));

const markdown = renderQurationEdgePatchHandoff(handoff);
assert(markdown.includes("# Dogma quration Edge Patch Handoff"));
assert(markdown.includes("quration's graph web UI"));
assert(markdown.includes("- Graph ID: graph-1"));
assert(markdown.includes("- Edge ID: bioedge.condition_transcript_abundance"));
assert(markdown.includes("- Proposal ID: nextflow-sample-validation-1"));
assert(markdown.includes("- Applied: false"));
assert(markdown.includes("GraphEdit.set_test"));
assert(markdown.includes("\"op\": \"set_test\""));
assert(markdown.includes("methods_graph.audited_substrate_missing"));
assert(markdown.includes("| Grounding | coverage_gap | No audited methods graph configured. |"));
assert(markdown.includes("not biological evidence"));
assert(markdown.includes("```diff"));
assert(markdown.includes("+def validateSampleRow(row) {}"));

console.log("quration edge patch handoff tests passed");
