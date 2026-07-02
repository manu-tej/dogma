"use strict";

function cleanText(value, fallback = "") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function bulletList(items = [], fallback = "none") {
  if (!Array.isArray(items) || !items.length) return [`- ${fallback}`];
  return items.map((item) => `- ${cleanText(item, "unknown")}`);
}

function contractRows(contracts = []) {
  if (!Array.isArray(contracts) || !contracts.length) {
    return ["| none | unknown | not returned |"];
  }
  return contracts.map((contract) => [
    `| ${cleanText(contract.stage, "stage")}`,
    cleanText(contract.status, "unknown"),
    cleanText(contract.detail, "not returned").replace(/\|/g, "\\|")
  ].join(" | ") + " |");
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

function renderQurationEdgeWorkPackage(record = {}) {
  const quration = record.quration_edge_plan?.plan || {};
  const dogma = record.dogma_edge_evaluation?.plan || {};
  const selected = record.selected_edge || record.dogma_edge_evaluation?.selected_edge || {};
  const claim = quration.claim || {};
  const readout = quration.ideal_readout || {};
  const qurationGraph = record.quration_graph || {};
  const gaps = dogma.coverage_gaps || [];

  return [
    "# Dogma quration Edge Work Package",
    "",
    "This package is the IDE-side unit of work for one quration edge. quration remains the canonical graph, edge resolve, evidence, and event-history surface; Dogma supplies local workspace context, method guardrails, redaction, patching, and execution gates.",
    "",
    "## Scope",
    "",
    `- Graph ID: ${cleanText(qurationGraph.graph_id, "unknown")}`,
    `- Graph URL: ${cleanText(qurationGraph.graph_url, "not available")}`,
    `- Query: ${cleanText(qurationGraph.query, "not recorded")}`,
    `- Edge ID: ${cleanText(selected.id || record.edge_id, "unknown")}`,
    `- Claim: ${cleanText(selected.title, `${cleanText(claim.source_symbol, "unknown")} ${cleanText(claim.relation, "relates to")} ${cleanText(claim.target_symbol, "unknown")}`)}`,
    `- Generated: ${cleanText(record.generated_at, "unknown")}`,
    "",
    "## quration Canonical Edge Plan",
    "",
    `- Claimed entity: ${cleanText(readout.claimed_entity, "unknown")}`,
    `- Modality: ${cleanText(readout.modality, "unknown")}`,
    `- Ideal assay class: ${cleanText(readout.ideal_assay_class, "unknown")}`,
    `- Dataset resolved: ${quration.dataset ? "yes" : "no"}`,
    `- Method selected: ${quration.method ? "yes" : "no"}`,
    `- Not evaluable: ${Boolean(quration.not_evaluable)}`,
    `- Expected direction: ${cleanText(quration.expected_direction, "unknown")}`,
    "",
    "## Dogma Local Guardrails",
    "",
    `- Status: ${cleanText(dogma.status, "unknown")}`,
    `- Task class: ${cleanText(dogma.task_class, "unknown")}`,
    `- Service edge question: ${cleanText(dogma.edge?.question, "not returned")}`,
    "",
    "### Coverage Gaps",
    "",
    ...bulletList(gaps),
    "",
    "### Contracts",
    "",
    "| Stage | Status | Detail |",
    "| --- | --- | --- |",
    ...contractRows(dogma.contracts),
    "",
    "## quration Assumptions",
    "",
    "| Name | Status | Checkable |",
    "| --- | --- | --- |",
    ...assumptionRows(quration.assumptions),
    "",
    "## Agent Instructions",
    "",
    "- Do not assert biological support/refute verdicts from this package.",
    "- Use quration for graph edits, edge resolve, evidence records, and event history.",
    "- Use Dogma for local file inspection, workflow edits, patch proposals, tests, and execution gates.",
    "- Treat every coverage gap as blocking real execution until it is resolved or explicitly accepted as a gap.",
    "- If proposing code changes, keep them scoped to workspace files and preserve privacy/redaction constraints.",
    "",
    "## Source Artifacts",
    "",
    "- `.dogma/quration-edge-plan.json` and `.dogma/quration-edge-plan.md`: quration canonical edge plan skeleton.",
    "- `.dogma/quration-edge-evaluation-plan.json` and `.dogma/quration-edge-evaluation-plan.md`: Dogma local guardrail plan.",
    ""
  ].join("\n");
}

module.exports = {
  renderQurationEdgeWorkPackage
};
