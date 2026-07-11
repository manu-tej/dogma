"use strict";

const assert = require("assert");
const { renderQurationGraphHistory } = require("../src/qurationGraphHistory");

const markdown = renderQurationGraphHistory({
  status: "ready",
  fetched_at: "2026-06-19T23:40:00.000Z",
  count: 2,
  graphs: [
    {
      rank: 1,
      id: "graph-1",
      query: "Does EGFR inhibition alter pMEK?",
      status: "active",
      created_at: "2026-06-19T20:00:00Z",
      updated_at: "2026-06-19T21:00:00Z",
      n_nodes: 9,
      n_edges: 10,
      graph_url: "http://localhost:3000/canvas/graph-1"
    },
    {
      rank: 2,
      id: "graph-2",
      query: "Control | treatment transcript abundance",
      status: "active",
      created_at: "2026-06-19T19:00:00Z",
      updated_at: "2026-06-19T19:30:00Z",
      n_nodes: 6,
      n_edges: 1,
      graph_url: "http://localhost:3000/canvas/graph-2"
    }
  ],
  settings: {
    quration_api_url: "http://localhost:8000",
    quration_canvas_url: "http://localhost:3000/canvas",
    graph_contract: "quration-hypothesis-api.v1"
  }
});

assert(markdown.includes("# Dogma quration Graph History"));
assert(markdown.includes("quration remains the canonical graph canvas"));
assert(markdown.includes("- Graphs: 2"));
assert(markdown.includes("http://localhost:3000/canvas/graph-1"));
assert(markdown.includes("Control \\| treatment transcript abundance"));
assert(markdown.includes("Keep graph edits in quration"));

const empty = renderQurationGraphHistory({ status: "ready", count: 0, graphs: [] });
assert(empty.includes("| none | unknown | 0 | 0 | unknown | not available |"));
assert(empty.includes("Import Workspace To quration"));

console.log("quration graph history renderer tests passed");
