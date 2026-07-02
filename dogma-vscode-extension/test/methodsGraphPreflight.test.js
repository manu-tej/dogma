"use strict";

const assert = require("assert");
const { renderMethodsGraphPreflight } = require("../src/methodsGraphPreflight");

const direct = renderMethodsGraphPreflight({
  markdown: "# Dogma Methods-Graph Preflight\n\n- Status: evaluable"
});
assert(direct.endsWith("\n"));
assert(direct.includes("Methods-Graph Preflight"));

const fallback = renderMethodsGraphPreflight({
  status: "configuration_gap",
  substrate_status: "configuration_gap",
  dataset_facts: { facts: { replicates_per_group: 2 } },
  method_chain: {
    steps: [{ process: "FASTQC", location: "pipeline.nf:10", method_id: "m:fastqc", status: "ready" }]
  },
  coverage_gaps: ["methods_graph.audited_substrate_missing"]
});

assert(fallback.includes("configuration_gap"));
assert(fallback.includes("replicates_per_group"));
assert(fallback.includes("m:fastqc"));
assert(fallback.includes("methods_graph.audited_substrate_missing"));

console.log("methods graph preflight renderer tests passed");
