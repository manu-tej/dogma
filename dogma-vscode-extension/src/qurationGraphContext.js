"use strict";

function escapePipe(value) {
  return String(value ?? "").replace(/\|/g, "\\|").replace(/\s+/g, " ").trim();
}

function countLines(counts = {}) {
  const entries = Object.entries(counts);
  if (!entries.length) return ["- none"];
  return entries
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `- ${key}: ${value}`);
}

function edgeRows(edges = []) {
  if (!edges.length) {
    return ["| none | unknown | unknown | unknown | unknown | none |"];
  }
  return edges.map((edge) => {
    const claim = `${edge.source_label || edge.source_id || "unknown"} ${edge.relation || "relates to"} ${edge.target_label || edge.target_id || "unknown"}`;
    const proposed = edge.proposed_test?.pipeline || edge.proposed_test?.data_accession || edge.proposed_test?.expected || "none";
    return [
      `| ${escapePipe(edge.id || "unknown")}`,
      escapePipe(claim),
      escapePipe(edge.state || "unknown"),
      escapePipe(edge.validation_status || "unknown"),
      escapePipe(edge.proposal_source || "unknown"),
      escapePipe(proposed)
    ].join(" | ") + " |";
  });
}

function renderQurationGraphContext(context = {}) {
  const summary = context.summary || {};
  const edges = Array.isArray(context.edge_dossiers) ? context.edge_dossiers : [];
  const settings = context.settings || {};

  return [
    "# Dogma quration Graph Context",
    "",
    "Dogma pulled this graph from quration for local IDE context. quration remains the canonical canvas, graph edit, evidence, and event-history surface.",
    "",
    `- Status: ${context.status || "unknown"}`,
    `- Fetched: ${context.fetched_at || "unknown"}`,
    `- Graph ID: ${context.graph_id || "unknown"}`,
    `- Graph URL: ${context.graph_url || "not available"}`,
    `- Query: ${context.query || "Untitled quration graph"}`,
    `- Nodes: ${summary.nodes ?? 0}`,
    `- Edges: ${summary.edges ?? 0}`,
    `- Pending edges: ${summary.pending_edges ?? 0}`,
    "",
    "## Node Types",
    "",
    ...countLines(summary.node_types),
    "",
    "## Edge States",
    "",
    ...countLines(summary.edge_states),
    "",
    "## Validation Statuses",
    "",
    ...countLines(summary.validation_statuses),
    "",
    "## Edge Dossiers",
    "",
    "| Edge | Claim | State | Validation | Source | Proposed test |",
    "| --- | --- | --- | --- | --- | --- |",
    ...edgeRows(edges),
    "",
    "## Settings",
    "",
    `- quration API: ${settings.quration_api_url || "not configured"}`,
    `- quration canvas: ${settings.quration_canvas_url || "not configured"}`,
    `- Graph contract: ${settings.graph_contract || "not configured"}`,
    "",
    "## Next Actions",
    "",
    "- Use quration for graph edits, edge/node chat, evidence records, and event history.",
    "- Use Dogma for local files, diagnostics, method guardrails, patch review, and workflow execution gates.",
    "- Generate Dogma edge evaluation plans or methods-graph preflight before treating local workflow work as grounded.",
    ""
  ].join("\n");
}

module.exports = {
  renderQurationGraphContext
};
