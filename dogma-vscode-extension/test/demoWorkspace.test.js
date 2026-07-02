"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { validateFiles } = require("../src/domainValidators");

const demoRoot = path.resolve(__dirname, "../../dogma-demo-workspace");
const candidateFiles = ["sample_sheet.csv", "intervals.bed", "variants.vcf", "genes.gtf", "reads/SYN_004_R1.fastq", "metadata.json", "pipeline.nf"];
const fileMap = Object.fromEntries(
  candidateFiles.map((file) => [file, fs.readFileSync(path.join(demoRoot, file), "utf8")])
);

const issues = validateFiles(fileMap);

assert(issues.some((item) => item.file === "sample_sheet.csv" && item.message.includes("Duplicate")));
assert(issues.some((item) => item.file === "sample_sheet.csv" && item.message.includes("fastq_1 and fastq_2")));
assert(issues.some((item) => item.file === "intervals.bed" && item.message.includes("0-based")));
assert(issues.some((item) => item.file === "intervals.bed" && item.message.includes("Mixed chromosome")));
assert(issues.some((item) => item.file === "variants.vcf" && item.message.includes("##reference")));
assert(issues.some((item) => item.file === "variants.vcf" && item.message.includes("FILTER=LowQual")));
assert(issues.some((item) => item.file === "metadata.json" && item.message.includes("reference.annotation")));
assert(issues.some((item) => item.file === "metadata.json" && item.message.includes("sample identifier policy")));
assert(issues.some((item) => item.file === "pipeline.nf" && item.message.includes("sample sheet rows")));

console.log(`demo workspace test passed: ${issues.length} issues detected`);
