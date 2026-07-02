"use strict";

function escapeTableCell(value) {
  return String(value ?? "").replace(/\|/g, "\\|");
}

function renderFallback(result) {
  const summary = result.summary || {};
  const entries = result.entries || [];
  const rows = entries.length
    ? entries.map((item) => {
        const facts = item.facts || {};
        const code = facts.code || facts.proposal_id || facts.command_id || "";
        return `| ${item.status || "info"} | ${item.type || "entry"} | ${item.id || "unknown"} | ${escapeTableCell(code)} | ${escapeTableCell(item.title || "")} | ${item.source || "service"} |`;
      })
    : ["| gap | ledger | evidence-ledger.unavailable |  | No evidence ledger entries were returned. | local-service |"];

  return [
    "# Dogma Evidence Ledger",
    "",
    "This is a factual ledger of workspace observations, guardrails, proposals, and execution gates. It is not a biological verdict system.",
    "",
    "## Summary",
    "",
    `- Total entries: ${summary.total || 0}`,
    `- Blocked: ${summary.blocked || 0}`,
    `- Warning: ${summary.warning || 0}`,
    `- Gap: ${summary.gap || 0}`,
    `- Pass: ${summary.pass || 0}`,
    `- Preview: ${summary.preview || 0}`,
    `- Info: ${summary.info || 0}`,
    "",
    "## Entries",
    "",
    "| Status | Type | ID | Code | Title | Source |",
    "| --- | --- | --- | --- | --- | --- |",
    ...rows,
    ""
  ].join("\n");
}

function renderEvidenceLedger(result) {
  if (result && typeof result.markdown === "string" && result.markdown.trim()) {
    return result.markdown.endsWith("\n") ? result.markdown : `${result.markdown}\n`;
  }
  return renderFallback(result || {});
}

module.exports = {
  renderEvidenceLedger
};
