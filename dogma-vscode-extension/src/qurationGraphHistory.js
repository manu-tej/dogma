"use strict";

function escapePipe(value) {
  return String(value ?? "").replace(/\|/g, "\\|").replace(/\s+/g, " ").trim();
}

function graphRows(graphs = []) {
  if (!graphs.length) {
    return ["| none | unknown | 0 | 0 | unknown | not available |"];
  }
  return graphs.map((graph) => {
    const label = graph.id ? `${graph.rank || ""}. ${graph.query || graph.id}` : graph.query || "Untitled Dogma graph";
    return [
      `| ${escapePipe(label)}`,
      escapePipe(graph.status || "unknown"),
      Number(graph.n_nodes || 0),
      Number(graph.n_edges || 0),
      escapePipe(graph.updated_at || graph.created_at || "unknown"),
      escapePipe(graph.graph_url || "not available")
    ].join(" | ") + " |";
  });
}

function renderQurationGraphHistory(record = {}) {
  const graphs = Array.isArray(record.graphs) ? record.graphs : [];
  const settings = record.settings || {};
  const newest = graphs[0];
  const actions = graphs.length
    ? [
      "- Use `Dogma: Open Browser Graph UI` or the graph URL above for review in Dogma's browser workspace.",
      "- Keep graph edits in Dogma's browser workspace; use the IDE surface to inspect local files, guardrails, and workflow patches.",
      "- Use `Dogma: Import Workspace To Browser Graph` when the local workspace should seed a new Dogma graph."
    ]
    : [
      "- Use `Dogma: Import Workspace To Browser Graph` to create a Dogma graph from the current workspace.",
      "- Use `Dogma: Open Browser Graph UI` to author or inspect graphs in Dogma's browser workspace."
    ];

  return [
    "# Dogma Browser Graph History",
    "",
    "Dogma reads graph history through its quration compatibility API. Dogma's browser workspace remains the canonical graph canvas and event-history surface.",
    "",
    `- Status: ${record.status || "unknown"}`,
    `- Fetched: ${record.fetched_at || "unknown"}`,
    `- Graphs: ${record.count ?? graphs.length}`,
    `- Newest graph: ${newest?.graph_url || "none"}`,
    "",
    "## Graphs",
    "",
    "| Graph | Status | Nodes | Edges | Updated | URL |",
    "| --- | --- | ---: | ---: | --- | --- |",
    ...graphRows(graphs),
    "",
    "## Settings",
    "",
    `- Dogma graph API (quration compatibility setting): ${settings.quration_api_url || "not configured"}`,
    `- Dogma canvas (quration compatibility setting): ${settings.quration_canvas_url || "not configured"}`,
    `- Graph contract: ${settings.graph_contract || "not configured"}`,
    "",
    "## Next Actions",
    "",
    ...actions,
    ""
  ].join("\n");
}

module.exports = {
  renderQurationGraphHistory
};
