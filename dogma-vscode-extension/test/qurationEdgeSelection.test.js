"use strict";

const assert = require("assert");
const {
  buildQurationEdgeQuickPickItems,
  buildQurationEdgeSelectionRecord,
  renderQurationEdgeSelection
} = require("../src/qurationEdgeSelection");

const context = {
  graph_id: "graph-1",
  graph_url: "http://localhost:3000/canvas/graph-1",
  query: "Which edge should Dogma work on?",
  edge_dossiers: [
    {
      id: "edge-a",
      source_id: "condition:a",
      target_id: "readout:x",
      source_label: "condition A",
      target_label: "readout X",
      relation: "changes",
      state: "untested",
      validation_status: "unvalidated",
      proposal_source: "llm",
      proposed_test: {
        expected: "Compare condition A against baseline."
      }
    },
    {
      id: "edge-b",
      source_id: "condition:b",
      target_id: "readout:y",
      source_label: "condition B",
      target_label: "readout Y",
      relation: "decreases",
      state: "examined",
      validation_status: "ambiguous",
      proposal_source: "dataset",
      proposed_test: {
        pipeline: "nf-core/rnaseq",
        data_accession: "GSE000000"
      }
    }
  ]
};

const items = buildQurationEdgeQuickPickItems(context);
assert.strictEqual(items.length, 2);
assert.strictEqual(items[0].label, "condition A changes readout X");
assert.strictEqual(items[0].description, "edge-a");
assert(items[0].detail.includes("state: untested"));
assert(items[0].detail.includes("validation: unvalidated"));
assert(items[0].detail.includes("Compare condition A against baseline."));
assert.strictEqual(items[1].label, "condition B decreases readout Y");
assert(items[1].detail.includes("nf-core/rnaseq"));
assert.strictEqual(items[1].edgeId, "edge-b");
assert.strictEqual(items[1].edge.id, "edge-b");

const record = buildQurationEdgeSelectionRecord({
  context,
  edge: context.edge_dossiers[1],
  selectedAt: "2026-06-20T01:00:00.000Z",
  selectionSource: "quick_pick"
});

assert.strictEqual(record.contract_version, "dogma-quration-edge-selection.v1");
assert.strictEqual(record.quration_graph.graph_id, "graph-1");
assert.strictEqual(record.selected_edge.id, "edge-b");
assert.strictEqual(record.selected_edge.claim, "condition B decreases readout Y");
assert.strictEqual(record.selected_edge.validation_status, "ambiguous");
assert.strictEqual(record.selected_edge.proposed_test, "nf-core/rnaseq");
assert.strictEqual(record.ide_policy.canonical_graph_surface, "quration");

const markdown = renderQurationEdgeSelection(record);
assert(markdown.includes("# Dogma quration Edge Selection"));
assert(markdown.includes("quration remains the canonical graph web UI"));
assert(markdown.includes("- Graph ID: graph-1"));
assert(markdown.includes("- Edge ID: edge-b"));
assert(markdown.includes("- Claim: condition B decreases readout Y"));
assert(markdown.includes("- Validation: ambiguous"));
assert(markdown.includes("- Proposed test: nf-core/rnaseq"));
assert(markdown.includes("- Selection source: quick_pick"));
assert(markdown.includes("Dogma VS Code/Cursor extension"));
assert(markdown.includes("Use Dogma quration edge commands"));

const emptyItems = buildQurationEdgeQuickPickItems({ graph: { nodes: [], edges: [] } });
assert.deepStrictEqual(emptyItems, []);

console.log("quration edge selection tests passed");
