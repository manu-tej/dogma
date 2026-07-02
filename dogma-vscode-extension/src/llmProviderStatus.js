"use strict";

function renderLlmProviderStatus(result) {
  if (result && typeof result.markdown === "string" && result.markdown.trim()) {
    return result.markdown.endsWith("\n") ? result.markdown : `${result.markdown}\n`;
  }
  const subscription = (result && result.claude_subscription) || {};
  return [
    "# Dogma LLM Provider Status",
    "",
    "Dogma follows quration's provider pattern: typed local-service actions, not raw agent/tool access.",
    "",
    `- Status: ${(result && result.status) || "unknown"}`,
    `- Provider: ${(result && result.provider) || "none"}`,
    `- CLI path: ${subscription.cli_path || "claude"}`,
    `- Resolved CLI path: ${subscription.resolved_cli_path || "not found"}`,
    `- Attempted CLI paths: ${(subscription.attempted_cli_paths || []).join(", ") || "none"}`,
    `- Tools disabled: ${String(Boolean(subscription.tools_disabled)).toLowerCase()}`,
    `- No session persistence: ${String(Boolean(subscription.no_session_persistence)).toLowerCase()}`,
    ""
  ].join("\n");
}

module.exports = {
  renderLlmProviderStatus
};
