"use strict";

function renderAgentSuggestion(result) {
  if (result && typeof result.markdown === "string") {
    return result.markdown;
  }

  const suggestion = (result && result.suggestion) || {};
  const actions = Array.isArray(suggestion.next_actions) ? suggestion.next_actions : [];
  const risks = Array.isArray(suggestion.highest_risks) ? suggestion.highest_risks : [];
  const mustNot = Array.isArray(suggestion.must_not_do) ? suggestion.must_not_do : [];
  const actionRows = actions.length
    ? actions.map((item) => `- **${item.kind || "action"}** - ${item.title || "Untitled action"}${item.proposal_id ? ` - proposal \`${item.proposal_id}\`` : ""}${item.target_file ? ` - \`${item.target_file}\`` : ""}`).join("\n")
    : "- No model-generated actions are available.";

  return [
    "# Dogma Agent Suggestion",
    "",
    `- Status: ${(result && result.status) || "unknown"}`,
    `- Provider: ${(result && result.llm_status && result.llm_status.provider) || "unknown"}`,
    `- LLM executed: ${String(Boolean(result && result.llm_executed)).toLowerCase()}`,
    "",
    "## User Instruction",
    "",
    (result && result.instruction) || "not supplied",
    "",
    "## Agent Summary",
    "",
    suggestion.summary || (result && result.message) || "No summary available.",
    "",
    "## Highest Risks",
    "",
    risks.length ? risks.map((item) => `- ${item}`).join("\n") : "- No model-generated risks are available.",
    "",
    "## Next Actions",
    "",
    actionRows,
    "",
    "## Must Not Do Yet",
    "",
    mustNot.length ? mustNot.map((item) => `- ${item}`).join("\n") : "- Do not bypass Dogma guardrails or apply patches without review.",
    ""
  ].join("\n");
}

module.exports = {
  renderAgentSuggestion
};
