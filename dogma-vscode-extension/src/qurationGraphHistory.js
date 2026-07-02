"use strict";

function escapePipe(value) {
  return String(value ?? "").replace(/\|/g, "\\|").replace(/\s+/g, " ").trim();
}

function graphRows(graphs = []) {
  if (!graphs.length) {
    return ["| none | unknown | 0 | 0 | unknown | not available |"];
  }
  return graphs.map((graph) => {
    const label = graph.id ? `${graph.rank || ""}. ${graph.query || graph.id}` : graph.query || "Untitled quration graph";
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
      "- Use `Dogma: Open quration Graph UI` or the graph URL above for review in quration.",
      "- Keep graph edits in quration; use Dogma to inspect local files, guardrails, and workflow patches.",
      "- Use `Dogma: Import Workspace To quration` when the local workspace should seed a new graph."
    ]
    : [
      "- Use `Dogma: Import Workspace To quration` to create a quration graph from the current workspace.",
      "- Use `Dogma: Open quration Graph UI` to author or inspect graphs directly in quration."
    ];

  return [
    "# Dogma quration Graph History",
    "",
    "Dogma reads quration graph history as an IDE client. quration remains the canonical graph canvas and event-history surface.",
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
    `- quration API: ${settings.quration_api_url || "not configured"}`,
    `- quration canvas: ${settings.quration_canvas_url || "not configured"}`,
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
