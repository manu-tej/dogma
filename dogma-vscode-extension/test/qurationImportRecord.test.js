"use strict";

const assert = require("assert");
const {
  buildQurationImportRecord,
  lastQurationGraphUrl,
  renderQurationImportRecord
} = require("../src/qurationImportRecord");

const record = buildQurationImportRecord({
  createdAt: "2026-06-19T22:49:00.000Z",
  qurationApiUrl: "http://localhost:8000",
  qurationCanvasUrl: "http://localhost:3000/canvas",
  result: {
    kind: "investigative",
    graph_id: "graph-123",
    graph_url: "http://localhost:3000/canvas/graph-123"
  },
  handoff: {
    contract_version: "quration-handoff.v1",
    causal_graph: {
      query: "Does control vs treatment change transcript abundance?",
      nodes: [{ id: "contrast:declared" }, { id: "readout:primary" }],
      edges: [{ id: "bioedge.condition_transcript_abundance" }]
    },
    dogma: {
      task_class: "differential_expression",
      scan_summary: { risk_level: "blocked" },
      coverage_gaps: ["methods_graph.audited_substrate_missing", "reference.annotation_missing"]
    }
  }
});

assert.strictEqual(record.contract_version, "dogma-quration-import.v1");
assert.strictEqual(record.created_at, "2026-06-19T22:49:00.000Z");
assert.strictEqual(record.quration.graph_id, "graph-123");
assert.strictEqual(record.quration.api_url, "http://localhost:8000");
assert.strictEqual(record.dogma.contract_version, "quration-handoff.v1");
assert.strictEqual(record.dogma.nodes, 2);
assert.strictEqual(record.dogma.edges, 1);
assert.strictEqual(record.dogma.task_class, "differential_expression");
assert.strictEqual(lastQurationGraphUrl(record), "http://localhost:3000/canvas/graph-123");
assert.strictEqual(lastQurationGraphUrl({}), null);

const markdown = renderQurationImportRecord(record);
assert(markdown.includes("# Dogma quration Import"));
assert(markdown.includes("Graph ID: graph-123"));
assert(markdown.includes("Does control vs treatment change transcript abundance?"));
assert(markdown.includes("methods_graph.audited_substrate_missing"));
assert(markdown.includes("Review the quration canvas as an unvalidated seed graph."));

console.log("quration import record tests passed");
