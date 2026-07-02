"use strict";

const assert = require("assert");
const { renderQurationEdgeWorkPackage } = require("../src/qurationEdgeWorkPackage");

const record = {
  contract_version: "dogma-quration-edge-work-package.v1",
  generated_at: "2026-06-20T00:10:00.000Z",
  edge_id: "bioedge.condition_transcript_abundance",
  quration_graph: {
    graph_id: "graph-1",
    graph_url: "http://localhost:3000/canvas/graph-1",
    query: "Does control vs treatment change transcript abundance?"
  },
  selected_edge: {
    id: "bioedge.condition_transcript_abundance",
    title: "control vs treatment changes Transcript abundance"
  },
  quration_edge_plan: {
    plan: {
      claim: {
        source_symbol: "control vs treatment",
        relation: "changes",
        target_symbol: "Transcript abundance"
      },
      ideal_readout: {
        claimed_entity: "Transcript abundance",
        modality: "transcript",
        ideal_assay_class: "RNA-seq differential expression"
      },
      dataset: null,
      method: null,
      assumptions: [
        {
          name: "matched context",
          status: "unchecked",
          checkable: "Samples match contrast"
        }
      ],
      expected_direction: "unknown",
      not_evaluable: false
    }
  },
  dogma_edge_evaluation: {
    plan: {
      status: "blocked",
      task_class: "differential_expression",
      edge: {
        question: "Does control vs treatment change transcript abundance?"
      },
      coverage_gaps: [
        "methods_graph.audited_substrate_missing",
        "quration.edge.unvalidated"
      ],
      contracts: [
        {
          stage: "Grounding",
          status: "coverage_gap",
          detail: "No audited methods graph configured."
        }
      ]
    }
  }
};

const markdown = renderQurationEdgeWorkPackage(record);
assert(markdown.includes("# Dogma quration Edge Work Package"));
assert(markdown.includes("quration remains the canonical graph"));
assert(markdown.includes("- Graph ID: graph-1"));
assert(markdown.includes("- Edge ID: bioedge.condition_transcript_abundance"));
assert(markdown.includes("- Claimed entity: Transcript abundance"));
assert(markdown.includes("- Status: blocked"));
assert(markdown.includes("- methods_graph.audited_substrate_missing"));
assert(markdown.includes("| Grounding | coverage_gap | No audited methods graph configured. |"));
assert(markdown.includes("| matched context | unchecked | Samples match contrast |"));
assert(markdown.includes("Do not assert biological support/refute verdicts"));
assert(markdown.includes(".dogma/quration-edge-plan.json"));

const empty = renderQurationEdgeWorkPackage({});
assert(empty.includes("- none"));
assert(empty.includes("| none | unchecked | not declared |"));

console.log("quration edge work package renderer tests passed");
