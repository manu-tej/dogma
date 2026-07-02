"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { extractNextflowGraph } = require("../src/workflowGraph");
const { renderMermaidForGraph, renderWorkflowGraphReport } = require("../src/workflowGraphReport");

const pipeline = fs.readFileSync(path.resolve(__dirname, "../../dogma-demo-workspace/pipeline.nf"), "utf8");
const graph = extractNextflowGraph("pipeline.nf", pipeline);

const mermaid = renderMermaidForGraph(graph);
assert(mermaid.startsWith("flowchart LR"));
assert(mermaid.includes("FASTQC"));
assert(mermaid.includes("ALIGN_STAR"));
assert(mermaid.includes("-->"));

const report = renderWorkflowGraphReport([graph]);
assert(report.includes("# Dogma Workflow Graph"));
assert(report.includes("```mermaid"));
assert(report.includes("| FASTQC | pipeline.nf |"));
assert(report.includes("| sample_reads | pipeline.nf |"));
assert(report.includes("| FASTQC | ALIGN_STAR | inferred call order |"));

const empty = renderWorkflowGraphReport([]);
assert(empty.includes("No Nextflow workflow graph was detected"));

console.log("workflow graph report tests passed");
