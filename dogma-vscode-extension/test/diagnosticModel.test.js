"use strict";

const assert = require("assert");
const { diagnosticEntries, isCandidatePath, lineRange, SEVERITY } = require("../src/diagnosticModel");

const text = ["alpha", "beta", "gamma"].join("\n");
assert.deepStrictEqual(lineRange(text, 2), {
  startLine: 1,
  startCharacter: 0,
  endLine: 1,
  endCharacter: 4
});
assert.deepStrictEqual(lineRange(text, 99), {
  startLine: 2,
  startCharacter: 0,
  endLine: 2,
  endCharacter: 5
});

assert.strictEqual(isCandidatePath("/repo/sample_sheet.csv"), true);
assert.strictEqual(isCandidatePath("/repo/sample_sheet.csv.gz"), true);
assert.strictEqual(isCandidatePath("/repo/workflow/main.nf"), true);
assert.strictEqual(isCandidatePath("/repo/workflow/Snakefile"), true);
assert.strictEqual(isCandidatePath("/repo/workflow/rules/qc.smk"), true);
assert.strictEqual(isCandidatePath("/repo/variants.vcf.gz"), true);
assert.strictEqual(isCandidatePath("/repo/genes.gtf"), true);
assert.strictEqual(isCandidatePath("/repo/annotations.gff3.gz"), true);
assert.strictEqual(isCandidatePath("/repo/reads.fastq"), true);
assert.strictEqual(isCandidatePath("/repo/reads.fq.gz"), true);
assert.strictEqual(isCandidatePath("/repo/reference/genome.fa.fai"), true);
assert.strictEqual(isCandidatePath("/repo/multiqc_data/multiqc_general_stats.txt"), true);
assert.strictEqual(isCandidatePath("/repo/notes.txt"), false);

const entries = diagnosticEntries(
  { "sample_sheet.csv": "sample_id\nS1" },
  [{ severity: "error", file: "sample_sheet.csv", line: 2, message: "bad sample", code: "sample_sheet.bad_sample" }]
);
const sampleEntries = entries.get("sample_sheet.csv");
assert.strictEqual(sampleEntries.length, 1);
assert.strictEqual(sampleEntries[0].severity, SEVERITY.error);
assert.strictEqual(sampleEntries[0].code, "sample_sheet.bad_sample");
assert.strictEqual(sampleEntries[0].source, "Dogma");
assert.strictEqual(sampleEntries[0].range.startLine, 1);

console.log("diagnostic model tests passed");
