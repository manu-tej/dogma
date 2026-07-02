"use strict";

const assert = require("assert");
const { validateFiles } = require("../src/domainValidators");

const files = {
  "sample_sheet.csv": [
    "sample_id,condition,replicate,fastq_1,fastq_2,strandedness",
    "S1,control,1,S1_R1.fastq.gz,S1_R2.fastq.gz,reverse",
    "S1,control,2,S1b_R1.fastq.gz,S1b_R2.fastq.gz,forward",
    "S3,treat,1,S3_R1.fastq.gz,,reverse"
  ].join("\n"),
  "intervals.bed": [
    "chr1\t10\t20\tok",
    "1\t30\t25\tbad"
  ].join("\n"),
  "variants.vcf": [
    "##fileformat=VCFv4.3",
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO",
    "chr1\t0\tbadpos\tA\tT\t99\tPASS\tDP=40",
    "chr2\t42\tlowqual\tG\tA\t20\tLowQual\tDP=12"
  ].join("\n"),
  "annotations.gtf": [
    "chr1\tDogma\tgene\t100\t90\t.\t+\t.\tgene_id \"bad\";",
    "1\tDogma\texon\t100\t120\tbad\tbad\tbad\t."
  ].join("\n"),
  "reads.fastq": [
    "bad_header",
    "ACGTX",
    "-",
    "IIII"
  ].join("\n"),
  "metadata.json": JSON.stringify({ reference: { genome_build: "GRCh38" }, privacy: { contains_human_data: true } }),
  "pipeline.nf": [
    "nextflow.enable.dsl = 2",
    "workflow {",
    "  Channel.fromPath(params.samples).splitCsv(header: true)",
    "    .map { row -> tuple(row.sample_id, [file(row.fastq_1), file(row.fastq_2)]) }",
    "}"
  ].join("\n")
};

const issues = validateFiles(files);
const messages = issues.map((item) => item.message);

assert(issues.some((item) => item.file === "sample_sheet.csv" && item.severity === "error" && item.message.includes("Duplicate")));
assert(issues.some((item) => item.file === "sample_sheet.csv" && item.message.includes("fastq_1 and fastq_2")));
assert(issues.some((item) => item.file === "intervals.bed" && item.message.includes("0-based")));
assert(issues.some((item) => item.file === "intervals.bed" && item.message.includes("Mixed chromosome")));
assert(issues.some((item) => item.file === "variants.vcf" && item.message.includes("##reference")));
assert(issues.some((item) => item.file === "variants.vcf" && item.message.includes("1-based")));
assert(issues.some((item) => item.file === "variants.vcf" && item.message.includes("FILTER=LowQual")));
assert(issues.some((item) => item.file === "annotations.gtf" && item.message.includes("1-based closed")));
assert(issues.some((item) => item.file === "annotations.gtf" && item.message.includes("Mixed chromosome")));
assert(issues.some((item) => item.file === "annotations.gtf" && item.message.includes("score should be numeric")));
assert(issues.some((item) => item.file === "reads.fastq" && item.message.includes("header must start")));
assert(issues.some((item) => item.file === "reads.fastq" && item.message.includes("non-ACGTN")));
assert(issues.some((item) => item.file === "reads.fastq" && item.message.includes("quality lengths")));
assert(issues.some((item) => item.file === "metadata.json" && item.message.includes("reference.annotation")));
assert(issues.some((item) => item.file === "metadata.json" && item.message.includes("sample identifier policy")));
assert(issues.some((item) => item.file === "pipeline.nf" && item.message.includes("sample sheet rows")));

assert(messages.length >= 10);
console.log(`domain validator tests passed: ${issues.length} issues detected`);
