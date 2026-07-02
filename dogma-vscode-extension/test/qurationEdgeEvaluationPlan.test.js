"use strict";

const assert = require("assert");
const {
  buildQurationSelectedEdge,
  pickQurationEdge,
  proposedTestText,
  qurationEdgeClaim,
  renderQurationEdgeEvaluationPlan
} = require("../src/qurationEdgeEvaluationPlan");

const context = {
  graph_id: "graph-1",
  graph_url: "http://localhost:3000/canvas/graph-1",
  query: "Does control vs treatment change transcript abundance?",
  edge_dossiers: [
    {
      id: "bioedge.condition_transcript_abundance",
      source_id: "contrast:declared",
      target_id: "readout:primary",
      source_label: "control vs treatment",
      target_label: "Transcript abundance",
      relation: "changes",
      state: "untested",
      validation_status: "unvalidated",
      proposal_source: "llm",
      proposed_test: {
        expected: "Does control vs treatment change transcript abundance under the declared RNA-seq design?"
      }
    }
  ]
};

const edge = pickQurationEdge(context);
assert.strictEqual(edge.id, "bioedge.condition_transcript_abundance");
assert.strictEqual(qurationEdgeClaim(edge), "control vs treatment changes Transcript abundance");
assert.strictEqual(proposedTestText(edge), "Does control vs treatment change transcript abundance under the declared RNA-seq design?");

const selectedEdge = buildQurationSelectedEdge(context);
assert.strictEqual(selectedEdge.id, "bioedge.condition_transcript_abundance");
assert.strictEqual(selectedEdge.from, "control vs treatment");
assert.strictEqual(selectedEdge.to, "Transcript abundance");
assert.strictEqual(selectedEdge.title, "control vs treatment changes Transcript abundance");
assert.strictEqual(selectedEdge.source, "quration");
assert.strictEqual(selectedEdge.edge_type, "biological");
assert.strictEqual(selectedEdge.status, "untested/unvalidated");
assert.strictEqual(selectedEdge.facts.readout, "Transcript abundance");
assert.strictEqual(selectedEdge.facts.contrast, "control vs treatment");
assert(selectedEdge.facts.coverageGaps.includes("quration.edge.untested"));
assert(selectedEdge.facts.coverageGaps.includes("quration.edge.unvalidated"));
assert.strictEqual(selectedEdge.facts.methodsGraphGrounding.qurationGraphId, "graph-1");
assert(selectedEdge.next_actions.some((action) => action.includes("quration")));

const fromGraphEdges = buildQurationSelectedEdge({
  graph_id: "graph-2",
  graph: {
    nodes: [
      { id: "a", label: "A" },
      { id: "b", label: "B" }
    ],
    edges: [
      {
        id: "edge-2",
        source_id: "a",
        target_id: "b",
        relation: "changes",
        display_status: "unvalidated"
      }
    ]
  }
});
assert.strictEqual(fromGraphEdges.title, "A changes B");

assert.throws(
  () => buildQurationSelectedEdge({ edge_dossiers: [] }),
  /No quration edges/
);

const markdown = renderQurationEdgeEvaluationPlan({
  status: "coverage_gap",
  edge: {
    id: selectedEdge.id,
    question: selectedEdge.question
  },
  selected_edge: selectedEdge,
  coverage_gaps: ["quration.edge.unvalidated"],
  contracts: []
}, context, selectedEdge);

assert(markdown.includes("# Dogma quration Edge Evaluation Plan"));
assert(markdown.includes("quration remains the canonical web UI"));
assert(markdown.includes("- Graph ID: graph-1"));
assert(markdown.includes("- Edge ID: bioedge.condition_transcript_abundance"));
assert(markdown.includes("## Dogma Local Plan"));
assert(markdown.includes("Selected Biological Edge"));
assert(markdown.includes("quration.edge.unvalidated"));

console.log("quration edge evaluation plan tests passed");
