"use strict";

const assert = require("assert");
const { renderQurationGraphContext } = require("../src/qurationGraphContext");

const markdown = renderQurationGraphContext({
  status: "ready",
  fetched_at: "2026-06-19T23:42:00.000Z",
  graph_id: "graph-1",
  graph_url: "http://localhost:3000/canvas/graph-1",
  query: "Does AXL inhibition alter pAKT?",
  summary: {
    nodes: 2,
    edges: 1,
    pending_edges: 0,
    node_types: { target: 1, phenotype: 1 },
    edge_states: { untested: 1 },
    validation_statuses: { unvalidated: 1 }
  },
  edge_dossiers: [
    {
      id: "edge-1",
      source_label: "AXL",
      target_label: "pAKT",
      relation: "changes",
      state: "untested",
      validation_status: "unvalidated",
      proposal_source: "llm",
      proposed_test: { expected: "Measure pAKT after AXL inhibition" }
    }
  ],
  settings: {
    quration_api_url: "http://localhost:8000",
    quration_canvas_url: "http://localhost:3000/canvas",
    graph_contract: "quration-hypothesis-api.v1"
  }
});

assert(markdown.includes("# Dogma quration Graph Context"));
assert(markdown.includes("quration remains the canonical canvas"));
assert(markdown.includes("- Graph ID: graph-1"));
assert(markdown.includes("- target: 1"));
assert(markdown.includes("- unvalidated: 1"));
assert(markdown.includes("| edge-1 | AXL changes pAKT | untested | unvalidated | llm | Measure pAKT after AXL inhibition |"));
assert(markdown.includes("Use Dogma for local files"));

const empty = renderQurationGraphContext({
  status: "ready",
  summary: { nodes: 0, edges: 0, node_types: {}, edge_states: {}, validation_statuses: {} },
  edge_dossiers: []
});
assert(empty.includes("| none | unknown | unknown | unknown | unknown | none |"));

console.log("quration graph context renderer tests passed");
