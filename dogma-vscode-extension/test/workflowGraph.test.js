"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { extractNextflowGraph } = require("../src/workflowGraph");

const pipeline = fs.readFileSync(path.resolve(__dirname, "../../dogma-demo-workspace/pipeline.nf"), "utf8");
const graph = extractNextflowGraph("pipeline.nf", pipeline);

assert.deepStrictEqual(graph.processes.map((item) => item.name), ["FASTQC", "ALIGN_STAR"]);
assert.deepStrictEqual(graph.calls.map((item) => item.process), ["FASTQC", "ALIGN_STAR"]);
assert.deepStrictEqual(graph.channels.map((item) => item.name), ["sample_reads"]);
assert.deepStrictEqual(graph.edges, [{ from: "FASTQC", to: "ALIGN_STAR" }]);
assert(graph.processes[0].line > 1);
assert(graph.calls[0].line > graph.processes[0].line);

console.log("workflow graph tests passed");
