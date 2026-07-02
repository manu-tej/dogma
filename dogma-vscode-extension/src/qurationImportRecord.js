"use strict";

function handoffSummary(handoff = {}) {
  const graph = handoff.causal_graph || {};
  const dogma = handoff.dogma || {};
  return {
    contract_version: handoff.contract_version || "unknown",
    query: graph.query || "Dogma workspace graph",
    nodes: Array.isArray(graph.nodes) ? graph.nodes.length : 0,
    edges: Array.isArray(graph.edges) ? graph.edges.length : 0,
    task_class: dogma.task_class || null,
    risk_level: dogma.scan_summary?.risk_level || dogma.biological_graph_status || null,
    coverage_gaps: Array.isArray(dogma.coverage_gaps) ? dogma.coverage_gaps : []
  };
}

function buildQurationImportRecord({ result = {}, handoff = {}, qurationApiUrl, qurationCanvasUrl, createdAt } = {}) {
  const summary = handoffSummary(handoff);
  return {
    contract_version: "dogma-quration-import.v1",
    created_at: createdAt || new Date().toISOString(),
    quration: {
      graph_id: result.graph_id || null,
      graph_url: result.graph_url || null,
      kind: result.kind || null,
      api_url: qurationApiUrl || null,
      canvas_url: qurationCanvasUrl || null
    },
    dogma: summary,
    artifacts: {
      handoff_json: ".dogma/quration-handoff.json",
      import_json: ".dogma/quration-import.json",
      import_markdown: ".dogma/quration-import.md"
    },
    next_actions: [
      "Review the quration canvas as an unvalidated seed graph.",
      "Use quration edge/node chat for graph refinement.",
      "Use Dogma methods-graph preflight and evidence ledgers before treating any edge as evaluated."
    ]
  };
}

function lastQurationGraphUrl(record = {}) {
  const url = String(record.quration?.graph_url || "").trim();
  return url || null;
}

function markdownList(items = [], fallback = "none") {
  if (!items.length) return `- ${fallback}`;
  return items.map((item) => `- ${item}`).join("\n");
}

function renderQurationImportRecord(record = {}) {
  const quration = record.quration || {};
  const dogma = record.dogma || {};
  return [
    "# Dogma quration Import",
    "",
    `- Created: ${record.created_at || "unknown"}`,
    `- Graph ID: ${quration.graph_id || "not returned"}`,
    `- Graph URL: ${quration.graph_url || "not returned"}`,
    `- quration API: ${quration.api_url || "not configured"}`,
    `- quration canvas: ${quration.canvas_url || "not configured"}`,
    "",
    "## Imported Workspace Graph",
    "",
    `- Query: ${dogma.query || "Dogma workspace graph"}`,
    `- Nodes: ${dogma.nodes ?? 0}`,
    `- Edges: ${dogma.edges ?? 0}`,
    `- Task class: ${dogma.task_class || "not classified"}`,
    `- Dogma risk level: ${dogma.risk_level || "not reported"}`,
    "",
    "## Coverage Gaps",
    "",
    markdownList(dogma.coverage_gaps || []),
    "",
    "## Next Actions",
    "",
    markdownList(record.next_actions || []),
    ""
  ].join("\n");
}

module.exports = {
  buildQurationImportRecord,
  lastQurationGraphUrl,
  renderQurationImportRecord
};
