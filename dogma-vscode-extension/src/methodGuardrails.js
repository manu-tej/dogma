"use strict";

function renderFallback(result) {
  const checks = result.checks || [];
  const summary = result.summary || {};
  const rows = checks.length
    ? checks.map((check) => `| ${check.status || "warning"} | ${check.code || "guardrail"} | ${check.principle || "not reported"} | ${String(check.detail || "").replace(/\|/g, "\\|")} |`)
    : ["| gap | guardrails.unavailable | not reported | No guardrail checks were returned. |"];

  return [
    "# Dogma Method Guardrails",
    "",
    "## Summary",
    "",
    `- Pass: ${summary.pass || 0}`,
    `- Warning: ${summary.warning || 0}`,
    `- Gap: ${summary.gap || 0}`,
    `- Blocked: ${summary.blocked || 0}`,
    "",
    "## Guardrail Checks",
    "",
    "| Status | Code | Principle | Detail |",
    "| --- | --- | --- | --- |",
    ...rows,
    ""
  ].join("\n");
}

function renderMethodGuardrails(result) {
  if (result && typeof result.markdown === "string" && result.markdown.trim()) {
    return result.markdown.endsWith("\n") ? result.markdown : `${result.markdown}\n`;
  }
  return renderFallback(result || {});
}

module.exports = {
  renderMethodGuardrails
};
