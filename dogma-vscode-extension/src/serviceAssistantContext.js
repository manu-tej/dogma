"use strict";

function list(items) {
  return items && items.length ? items.join(", ") : "not detected";
}

function renderFallback(result) {
  const summary = result.summary || {};
  const context = result.context || {};
  const samples = context.samples || {};
  const reference = context.reference || {};
  const redaction = result.redaction || {};
  const trust = result.trust || {};
  const issues = result.issues || [];
  const issueRows = issues.length
    ? issues.map((item) => `| ${item.severity || "info"} | ${item.code || "dogma.finding"} | ${item.file || "workspace"}:${item.line || 1} | ${String(item.message || "").replace(/\|/g, "\\|")} |`)
    : ["| pass | none | workspace | No Dogma findings are currently reported. |"];

  return [
    "# Dogma Assistant Context Bundle",
    "",
    "## Privacy Boundary",
    "",
    `- Human data detected: ${String(Boolean(trust.human_data))}`,
    `- Trust status: ${trust.status || "unknown"}`,
    `- Sample IDs redacted: ${String(Boolean(redaction.sample_ids_redacted))}`,
    `- Redaction reason: ${redaction.reason || "not reported"}`,
    "",
    "## Workspace Summary",
    "",
    `- Risk level: ${summary.risk_level || "unknown"}`,
    `- Errors: ${summary.errors || 0}`,
    `- Warnings: ${summary.warnings || 0}`,
    `- Assay: ${context.assay || "not detected"}`,
    `- Organism: ${context.organism || "not detected"}`,
    `- Sample sheet: ${context.sample_file || "not detected"}`,
    `- Samples: ${samples.count || 0}`,
    `- Sample IDs: ${list(samples.ids)}`,
    `- Conditions: ${list(samples.conditions)}`,
    `- Genome build: ${reference.genome_build || "not detected"}`,
    `- Annotation: ${reference.annotation || "not detected"}`,
    "",
    "## Findings",
    "",
    "| Severity | Code | Location | Message |",
    "| --- | --- | --- | --- |",
    ...issueRows,
    ""
  ].join("\n");
}

function renderServiceAssistantContext(result) {
  if (result && typeof result.markdown === "string" && result.markdown.trim()) {
    return result.markdown.endsWith("\n") ? result.markdown : `${result.markdown}\n`;
  }
  return renderFallback(result || {});
}

module.exports = {
  renderServiceAssistantContext
};
