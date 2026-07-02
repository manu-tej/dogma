"use strict";

const assert = require("assert");
const { renderMethodsGraphSubstrate } = require("../src/methodsGraphSubstrate");

const direct = renderMethodsGraphSubstrate({
  markdown: "# Dogma Methods-Graph Substrate\n\n- Status: ready"
});
assert(direct.endsWith("\n"));
assert(direct.includes("Methods-Graph Substrate"));

const fallback = renderMethodsGraphSubstrate({
  status: "configuration_gap",
  authoritative_surface: [
    { name: "audited_kuzu_graph", status: "gap", detail: "Need ingest.lock.json." },
    { name: "planner_expand", status: "advisory_only", detail: "Not runnable." }
  ]
});

assert(fallback.includes("configuration_gap"));
assert(fallback.includes("audited_kuzu_graph"));
assert(fallback.includes("planner_expand"));

console.log("methods graph substrate renderer tests passed");
