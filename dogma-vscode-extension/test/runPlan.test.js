"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { validateFiles } = require("../src/domainValidators");
const { extractWorkspaceContext } = require("../src/workspaceContext");
const { buildSafeRunPlan, renderRunPlan } = require("../src/runPlan");

const demoRoot = path.resolve(__dirname, "../../dogma-demo-workspace");
const candidateFiles = ["sample_sheet.csv", "intervals.bed", "variants.vcf", "metadata.json", "pipeline.nf"];
const fileMap = Object.fromEntries(
  candidateFiles.map((file) => [file, fs.readFileSync(path.join(demoRoot, file), "utf8")])
);
const issues = validateFiles(fileMap);
const context = extractWorkspaceContext(fileMap);

const plan = buildSafeRunPlan(context, issues);
assert.strictEqual(plan.blocked, true);
assert.strictEqual(plan.commands.length, 1);
assert.strictEqual(plan.commands[0].command, "nextflow run pipeline.nf -stub-run");

const rendered = renderRunPlan(context, issues);
assert(rendered.includes("# Dogma Safe Run Plan"));
assert(rendered.includes("blocked until error-level findings are fixed"));
assert(rendered.includes("nextflow run pipeline.nf -stub-run"));
assert(rendered.includes("Review commands before running them."));

console.log("run plan tests passed");
