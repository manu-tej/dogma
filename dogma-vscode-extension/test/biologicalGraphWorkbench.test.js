"use strict";

const assert = require("assert");
const { renderBiologicalGraphWorkbenchHtml } = require("../src/biologicalGraphWorkbench");

const graph = {
  status: "blocked",
  task_class: "differential_expression",
  summary: { nodes: 2, edges: 1 },
  nodes: [
    { id: "contrast:declared", label: "control vs treatment", kind: "contrast", status: "ready" },
    { id: "readout:primary", label: "Transcript abundance", kind: "readout", status: "blocked" }
  ],
  edges: [
    {
      id: "bioedge.condition_transcript_abundance",
      title: "control vs treatment -> transcript abundance",
      source: "control vs treatment",
      relation: "changes",
      target: "transcript abundance",
      question: "Does control vs treatment change transcript abundance?",
      status: "blocked",
      facts: {
        readout: "transcript abundance",
        method_candidates: ["m:fastqc", "m:star", "m:featurecounts", "m:deseq2"],
        coverage_gaps: ["methods_graph.audited_substrate_missing"],
        methods_graph_grounding: {
          status: "configuration_gap",
          coverage_gaps: ["methods_graph.audited_substrate_missing"]
        }
      },
      selected_edge: {
        id: "bioedge.condition_transcript_abundance",
        from: "control vs treatment",
        to: "transcript abundance",
        edge_type: "biological"
      },
      next_actions: ["Ground methods before execution."]
    }
  ]
};

const html = renderBiologicalGraphWorkbenchHtml(graph);

assert(html.includes("Dogma Local Biological Edge Guardrails"));
assert(html.includes("control vs treatment -&gt; transcript abundance") || html.includes("control vs treatment -> transcript abundance"));
assert(html.includes("Generate Evaluation Plan"));
assert(html.includes("generateEdgeEvaluationPlan"));
assert(html.includes("selectedEdge"));
assert(html.includes("methods_graph.audited_substrate_missing"));
assert(html.includes("methods_graph_grounding"));
assert(html.includes("support/refute") === false);

console.log("local biological edge guardrail workbench tests passed");
