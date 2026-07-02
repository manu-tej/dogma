"use strict";

const assert = require("assert");
const { renderAgentSuggestion } = require("../src/agentSuggestion");

const rendered = renderAgentSuggestion({
  status: "llm_completed",
  instruction: "Fix sample sheet validation.",
  llm_executed: true,
  llm_status: { provider: "claude_subscription" },
  suggestion: {
    summary: "Preview the Nextflow sample validation patch before applying it.",
    highest_risks: ["duplicate sample_id"],
    next_actions: [
      {
        kind: "patch_preview",
        title: "Preview sample validation patch",
        proposal_id: "nextflow-sample-validation-1",
        target_file: "pipeline.nf"
      }
    ],
    must_not_do: ["do not run a real workflow yet"]
  }
});

assert(rendered.includes("# Dogma Agent Suggestion"));
assert(rendered.includes("claude_subscription"));
assert(rendered.includes("Fix sample sheet validation."));
assert(rendered.includes("Preview sample validation patch"));
assert(rendered.includes("nextflow-sample-validation-1"));

const direct = renderAgentSuggestion({ markdown: "# Existing\n" });
assert.strictEqual(direct, "# Existing\n");

console.log("agent suggestion renderer tests passed");
