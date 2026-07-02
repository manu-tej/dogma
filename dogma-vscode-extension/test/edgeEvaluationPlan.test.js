"use strict";

const assert = require("assert");
const { renderEdgeEvaluationPlan } = require("../src/edgeEvaluationPlan");

const direct = renderEdgeEvaluationPlan({
  markdown: "# Dogma Edge Evaluation Plan\n\n- Stores support/refute verdicts: false"
});
assert(direct.endsWith("\n"));
assert(direct.includes("Edge Evaluation Plan"));

const fallback = renderEdgeEvaluationPlan({
  status: "coverage_gap",
  edge: {
    id: "edge.condition_transcript_abundance",
    question: "Does treatment change transcript abundance?"
  },
  selected_edge: {
    id: "pipeline.nf:FASTQC->ALIGN_STAR:1",
    from: "FASTQC",
    to: "ALIGN_STAR",
    title: "FASTQC -> ALIGN_STAR",
    status: "gap"
  },
  contracts: [
    { stage: "Readout", status: "ready", detail: "Resolve measurable readout." },
    { stage: "Grounding", status: "coverage_gap", detail: "No audited methods graph." }
  ],
  coverage_gaps: ["methods_graph.audited_substrate_missing"]
});

assert(fallback.includes("condition_transcript_abundance"));
assert(fallback.includes("Selected Workbench Edge"));
assert(fallback.includes("FASTQC -> ALIGN_STAR"));
assert(fallback.includes("| Readout | ready |"));
assert(fallback.includes("methods_graph.audited_substrate_missing"));
assert(fallback.includes("Stores support/refute verdicts: false"));

console.log("edge evaluation plan renderer tests passed");
