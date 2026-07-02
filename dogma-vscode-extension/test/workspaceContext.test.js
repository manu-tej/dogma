"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { validateFiles } = require("../src/domainValidators");
const { extractWorkspaceContext, renderContextReport } = require("../src/workspaceContext");

const demoRoot = path.resolve(__dirname, "../../dogma-demo-workspace");
const candidateFiles = ["sample_sheet.csv", "intervals.bed", "variants.vcf", "genes.gtf", "reads/SYN_004_R1.fastq", "metadata.json", "pipeline.nf"];
const fileMap = Object.fromEntries(
  candidateFiles.map((file) => [file, fs.readFileSync(path.join(demoRoot, file), "utf8")])
);
const issues = validateFiles(fileMap);
const context = extractWorkspaceContext(fileMap);

assert.strictEqual(context.sampleFile, "sample_sheet.csv");
assert.strictEqual(context.metadataFile, "metadata.json");
assert.strictEqual(context.samples.count, 3);
assert.deepStrictEqual(context.samples.conditions, ["control", "treatment"]);
assert.deepStrictEqual(context.samples.strandedness, ["forward", "reverse"]);
assert.strictEqual(context.reference.genome_build, "GRCh38");
assert.strictEqual(context.counts.intervals, 3);
assert.strictEqual(context.counts.variants, 3);
assert.strictEqual(context.counts.annotations, 3);
assert.strictEqual(context.counts.fastqReads, 2);
assert.deepStrictEqual(context.annotationFiles, ["genes.gtf"]);
assert.deepStrictEqual(context.fastqFiles, ["reads/SYN_004_R1.fastq"]);
assert.deepStrictEqual(context.workflowFiles, ["pipeline.nf"]);
assert.deepStrictEqual(context.workflowProcesses.map((item) => item.replace(/:\d+\)/, ":line)")), [
  "FASTQC (pipeline.nf:line)",
  "ALIGN_STAR (pipeline.nf:line)"
]);
assert.deepStrictEqual(context.workflowCalls.map((item) => item.replace(/:\d+\)/, ":line)")), [
  "FASTQC (pipeline.nf:line)",
  "ALIGN_STAR (pipeline.nf:line)"
]);

const report = renderContextReport(context, issues);
assert(report.includes("# Dogma Context Report"));
assert(report.includes("- Samples: 3"));
assert(report.includes("- Genome build: GRCh38"));
assert(report.includes("- Annotation files: genes.gtf (3 feature rows)"));
assert(report.includes("- FASTQ files: reads/SYN_004_R1.fastq (2 read records)"));
assert(report.includes("- Workflow processes: FASTQC"));
assert(report.includes("FASTQC->ALIGN_STAR"));
assert(report.includes("| warning | pipeline.nf:1 | Nextflow sample sheet rows should be validated before file tuple creation. |"));

console.log("workspace context tests passed");
