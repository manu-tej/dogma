"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { validateFiles } = require("../src/domainValidators");
const { extractWorkspaceContext } = require("../src/workspaceContext");
const { buildAssistantPrompt, buildSyntheticTestPlan } = require("../src/assistantPrompts");

const demoRoot = path.resolve(__dirname, "../../dogma-demo-workspace");
const candidateFiles = ["sample_sheet.csv", "intervals.bed", "variants.vcf", "genes.gtf", "reads/SYN_004_R1.fastq", "metadata.json", "pipeline.nf"];
const fileMap = Object.fromEntries(
  candidateFiles.map((file) => [file, fs.readFileSync(path.join(demoRoot, file), "utf8")])
);
const issues = validateFiles(fileMap);
const context = extractWorkspaceContext(fileMap);
const prompt = buildAssistantPrompt(context, issues);

assert(prompt.includes("You are Dogma"));
assert(prompt.includes("- Sample count: 3"));
assert(prompt.includes("- Genome build: GRCh38"));
assert(prompt.includes("- Annotation files: genes.gtf (3 feature rows)"));
assert(prompt.includes("- FASTQ files: reads/SYN_004_R1.fastq (2 read records)"));
assert(prompt.includes("- Workflow processes: FASTQC"));
assert(prompt.includes("- Workflow calls: FASTQC"));
assert(prompt.includes("Nextflow sample sheet rows should be validated"));
assert(prompt.includes("Do not invent sample metadata"));

const plan = buildSyntheticTestPlan(context, issues);
assert(plan.includes("# Dogma Synthetic Test Plan"));
assert(plan.includes("duplicate sample IDs"));
assert(plan.includes("BED coordinate fixtures"));
assert(plan.includes("VCF fixtures"));
assert(plan.includes("private human sample metadata"));

console.log("assistant prompt tests passed");
