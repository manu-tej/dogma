"use strict";

const assert = require("assert");
const { renderAgentWorkbenchHtml } = require("../src/agentWorkbench");

const html = renderAgentWorkbenchHtml({
  instruction: "Fix demo safely",
  useLlm: true,
  statusMessage: "Ready.",
  result: {
    status: "llm_completed",
    llm_executed: true,
    message: "Claude produced a guarded Dogma agent suggestion.",
    suggestion: {
      summary: "Preview the sample validation patch.",
      highest_risks: ["duplicate sample_id"],
      next_actions: [
        {
          kind: "patch_preview",
          title: "Preview sample validation patch",
          proposal_id: "nextflow-sample-validation-1",
          target_file: "pipeline.nf",
          rationale: "Rows need validation before tuple creation."
        }
      ],
      must_not_do: ["do not execute real workflow"]
    }
  },
  patchProposals: {
    proposals: [
      {
        id: "nextflow-sample-validation-1",
        title: "Add sample validation",
        target_file: "pipeline.nf",
        rationale: "Validate sample rows."
      }
    ]
  }
});

assert(html.includes("Dogma Agent"));
assert(html.includes("Fix demo safely"));
assert(html.includes("llm_completed"));
assert(html.includes("Preview sample validation patch"));
assert(html.includes("Open Diff"));
assert(html.includes("nextflow-sample-validation-1"));
assert(html.includes('command: "runAgent"'));
assert(html.includes('data-command="previewProposal"'));
assert(html.includes('data-command="applyProposal"'));
assert(html.includes("local Claude"));

console.log("agent workbench renderer tests passed");
