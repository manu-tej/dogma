"use strict";

function cleanText(value, fallback = "") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function formatObject(value) {
  if (value === null || value === undefined || value === "") return "not set";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

function datasetLine(dataset) {
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
    cleanText(assumption.checkable, "not declared")
  ].join(" | ") + " |");
}

function renderQurationEdgePlan(record = {}) {
  const plan = record.plan || {};
  const claim = plan.claim || {};
  const ideal = plan.ideal_readout || {};
  const resolved = plan.resolved_readout || null;
  const method = plan.method || null;
  const alternatives = Array.isArray(plan.alternatives) ? plan.alternatives : [];

  return [
    "# quration Edge Plan",
    "",
    "Dogma fetched this plan from quration's canonical graph API. It is quration's biology-derived edge plan skeleton, not a Dogma local execution verdict.",
    "",
    "## quration Graph",
    "",
    `- Graph ID: ${cleanText(record.graph_id, "unknown")}`,
    `- Graph URL: ${cleanText(record.graph_url, "not available")}`,
    `- Edge ID: ${cleanText(record.edge_id || plan.edge_id, "unknown")}`,
    `- Query: ${cleanText(record.query, "not recorded")}`,
    `- Fetched: ${cleanText(record.fetched_at, "unknown")}`,
    "",
    "## Claim",
    "",
    `- Source: ${cleanText(claim.source_symbol, "unknown")}`,
    `- Relation: ${cleanText(claim.relation, "unknown")}`,
    `- Target: ${cleanText(claim.target_symbol, "unknown")}`,
    `- Expected direction: ${cleanText(plan.expected_direction, "unknown")}`,
    `- Not evaluable: ${Boolean(plan.not_evaluable)}`,
    "",
    "## Readout",
    "",
    `- Claimed entity: ${cleanText(ideal.claimed_entity, "unknown")}`,
    `- Modality: ${cleanText(ideal.modality, "unknown")}`,
    `- Ideal assay class: ${cleanText(ideal.ideal_assay_class, "unknown")}`,
    `- Resolved readout: ${resolved ? formatObject(resolved) : "not resolved"}`,
    `- Directness: ${cleanText(plan.directness, "not resolved")}`,
    `- Proxy rationale: ${cleanText(plan.proxy_rationale, "none")}`,
    "",
    "## Dataset And Method",
    "",
    `- Dataset: ${datasetLine(plan.dataset)}`,
    `- Alternatives: ${alternatives.length}`,
    `- Method: ${method ? formatObject(method) : "not selected"}`,
    "",
    "## Assumptions",
    "",
    "| Name | Status | Checkable |",
    "| --- | --- | --- |",
    ...assumptionRows(plan.assumptions),
    "",
    "## Provenance",
    "",
    `- Endpoint: ${cleanText(record.endpoints?.edge_plan, "not recorded")}`,
    `- Resolver provenance: ${formatObject(plan.resolver_provenance || {})}`,
    "",
    "## Dogma Boundary",
    "",
    "- Use quration for graph edits, edge resolve, evidence records, and event history.",
    "- Use Dogma for local workspace context, method guardrails, redaction, patches, and execution gates.",
    "- Fetching this plan is side-effect-free; resolving a quration edge is a separate evidence-writing operation.",
    ""
  ].join("\n");
}

module.exports = {
  renderQurationEdgePlan
};
