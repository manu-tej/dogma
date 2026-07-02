"use strict";

function cleanText(value, fallback = "") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") return "not set";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function datasetText(dataset) {
  if (!dataset || typeof dataset !== "object") return "not resolved";
  const accession = cleanText(dataset.accession || dataset.id || dataset.dataset_id, "unknown accession");
  const source = cleanText(dataset.source || dataset.repository, "unknown source");
  const title = cleanText(dataset.title || dataset.summary, "untitled dataset");
  return `${accession} (${source}) - ${title}`;
}

function assumptionRows(assumptions = []) {
  if (!Array.isArray(assumptions) || !assumptions.length) {
    return ["| none | unchecked | not declared |"];
  }
  return assumptions.map((assumption) => [
    `| ${cleanText(assumption.name, "assumption")}`,
    cleanText(assumption.status, "unchecked"),
    cleanText(assumption.checkable, "not declared").replace(/\|/g, "\\|")
  ].join(" | ") + " |");
}

function coverageGaps(record = {}) {
  const gaps = record.dogma_preconditions?.patch_handoff?.coverage_gaps;
  return Array.isArray(gaps) ? gaps.map((gap) => cleanText(gap)).filter(Boolean) : [];
}

function renderQurationEdgeResolve(record = {}) {
  const plan = record.plan || {};
  const claim = plan.claim || {};
  const ideal = plan.ideal_readout || {};
  const handoff = record.dogma_preconditions?.patch_handoff || {};
  const gaps = coverageGaps(record);

  return [
    "# Dogma quration Edge Resolve",
    "",
    "Dogma asked quration to run its facts-only edge readout resolve workflow. quration remains the canonical evidence and event-history surface; Dogma records this local IDE audit artifact without turning the result into a support/refute verdict.",
    "",
    "## quration Target",
    "",
    `- Graph ID: ${cleanText(record.graph_id, "unknown")}`,
    `- Graph URL: ${cleanText(record.graph_url, "not available")}`,
    `- Edge ID: ${cleanText(record.edge_id || plan.edge_id, "unknown")}`,
    `- Query: ${cleanText(record.query, "not recorded")}`,
    `- Resolved: ${cleanText(record.resolved_at, "unknown")}`,
    `- Endpoint: ${cleanText(record.endpoints?.edge_resolve, "not recorded")}`,
    "",
    "## Dogma Preconditions",
    "",
    `- Matching handoff: ${handoff.present ? "yes" : "no"}`,
    `- Handoff artifact: ${cleanText(handoff.artifact, "not recorded")}`,
    `- Handoff generated: ${cleanText(handoff.generated_at, "unknown")}`,
    `- Local patch applied: ${String(Boolean(handoff.patch_applied))}`,
    `- Dogma guardrail status: ${cleanText(handoff.guardrail_status, "unknown")}`,
    `- Confirmation: ${cleanText(record.dogma_preconditions?.confirmation, "not recorded")}`,
    `- Coverage gaps: ${gaps.length ? gaps.join(", ") : "none"}`,
    "",
    "## Claim",
    "",
    `- Source: ${cleanText(claim.source_symbol, "unknown")}`,
    `- Relation: ${cleanText(claim.relation, "unknown")}`,
    `- Target: ${cleanText(claim.target_symbol, "unknown")}`,
    `- Expected direction: ${cleanText(plan.expected_direction, "unknown")}`,
    `- Not evaluable: ${Boolean(plan.not_evaluable)}`,
    "",
    "## Resolved Readout",
    "",
    `- Claimed entity: ${cleanText(ideal.claimed_entity, "unknown")}`,
    `- Ideal modality: ${cleanText(ideal.modality, "unknown")}`,
    `- Ideal assay class: ${cleanText(ideal.ideal_assay_class, "unknown")}`,
    `- Resolved readout: ${formatValue(plan.resolved_readout)}`,
    `- Directness: ${cleanText(plan.directness, "not resolved")}`,
    `- Proxy rationale: ${cleanText(plan.proxy_rationale, "none")}`,
    "",
    "## Dataset And Method",
    "",
    `- Dataset: ${datasetText(plan.dataset)}`,
    `- Alternatives: ${Array.isArray(plan.alternatives) ? plan.alternatives.length : 0}`,
    `- Method: ${formatValue(plan.method)}`,
    "",
    "## Assumptions",
    "",
    "| Name | Status | Checkable |",
    "| --- | --- | --- |",
    ...assumptionRows(plan.assumptions),
    "",
    "## Provenance",
    "",
    `- Resolver provenance: ${formatValue(plan.resolver_provenance || {})}`,
    "",
    "## Boundary",
    "",
    "- quration owns graph edits, evidence records, resolve side effects, and event history.",
    "- Dogma owns local files, workspace context, guardrails, patch review, and IDE audit artifacts.",
    "- This artifact is factual readout resolution context, not a biological support/refute verdict.",
    ""
  ].join("\n");
}

module.exports = {
  renderQurationEdgeResolve
};
