"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { extractNextflowGraph } = require("../src/workflowGraph");
const { buildGraphWorkbenchModel, renderGraphWorkbenchHtml } = require("../src/graphWorkbench");

const pipeline = fs.readFileSync(path.resolve(__dirname, "../../dogma-demo-workspace/pipeline.nf"), "utf8");
const graph = extractNextflowGraph("pipeline.nf", pipeline);

const blocked = buildGraphWorkbenchModel(
  [graph],
  { reference: { genome_build: "GRCh38", annotation: "GENCODE v44" }, workflowProcesses: ["FASTQC", "ALIGN_STAR"] },
  [{ severity: "error", file: "sample_sheet.csv", line: 2, message: "Duplicate sample ID." }]
);

assert.strictEqual(blocked.summary.status, "blocked");
assert.strictEqual(blocked.graphs[0].edges.length, 1);
assert.strictEqual(blocked.graphs[0].edges[0].status, "blocked");
assert.strictEqual(blocked.graphs[0].edges[0].facts.fromMethod, "m:fastqc (sequencing quality control)");
assert.strictEqual(blocked.graphs[0].edges[0].facts.toMethod, "m:star (splice-aware RNA-seq alignment)");
assert(blocked.graphs[0].edges[0].nextActions.some((item) => item.includes("Resolve error-level")));

const gap = buildGraphWorkbenchModel([graph], {}, []);
assert.strictEqual(gap.summary.status, "ready");
assert.strictEqual(gap.graphs[0].edges[0].status, "gap");
assert.deepStrictEqual(gap.graphs[0].edges[0].facts.missingContainers, ["FASTQC", "ALIGN_STAR"]);

const html = renderGraphWorkbenchHtml(gap);
assert(html.includes("Dogma Local Workflow Guardrails"));
assert(html.includes("FASTQC -&gt; ALIGN_STAR") || html.includes("FASTQC -> ALIGN_STAR"));
assert(html.includes("support/refute verdicts"));
assert(html.includes("container missing"));
assert(html.includes("data-edge"));
assert(html.includes("Generate Edge Evaluation Plan"));
assert(html.includes("generateEdgeEvaluationPlan"));
assert(html.includes("edgeEvaluationPlanStatus"));

console.log("local workflow guardrail workbench tests passed");
