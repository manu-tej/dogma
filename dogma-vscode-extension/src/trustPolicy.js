"use strict";

function list(items) {
  return items && items.length ? items.map((item) => `- ${item}`).join("\n") : "- none";
}

function renderTrustStatus(result) {
  const trust = result.trust || {};
  const summary = result.summary || {};
  return [
    "# Dogma Workspace Trust",
    "",
    `Root: ${result.root || "not reported"}`,
    `Status: ${trust.status || "unknown"}`,
    `Trusted: ${String(Boolean(trust.trusted))}`,
    `Human data detected: ${String(Boolean(trust.human_data))}`,
    `Policy present: ${String(Boolean(trust.policy_present))}`,
    `Policy path: ${trust.policy_path || "not reported"}`,
    "",
    "## Scan Summary",
    "",
    `- Risk level: ${summary.risk_level || "not reported"}`,
    `- Errors: ${summary.errors || 0}`,
    `- Warnings: ${summary.warnings || 0}`,
    `- Genome build: ${summary.genome_build || "not reported"}`,
    "",
    "## Blockers",
    "",
    list(trust.blockers || []),
    "",
    "## Required For",
    "",
    list(trust.required_for || []),
    "",
    "## Policy",
    "",
    "```json",
    trust.policy ? JSON.stringify(trust.policy, null, 2) : "null",
    "```",
    ""
  ].join("\n");
}

function renderTrustWriteResult(result) {
  return [
    "# Dogma Trust Policy Write Result",
    "",
    `Root: ${result.root || "not reported"}`,
    `Write status: ${result.write?.status || "unknown"}`,
    `Policy path: ${result.write?.policy_path || result.trust?.policy_path || "not reported"}`,
    "",
    renderTrustStatus(result)
  ].join("\n");
}

module.exports = {
  renderTrustStatus,
  renderTrustWriteResult
};
