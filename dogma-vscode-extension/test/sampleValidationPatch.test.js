"use strict";

const assert = require("assert");
const { applySampleValidationPatchText } = require("../src/sampleValidationPatch");

const pipeline = [
  "nextflow.enable.dsl = 2",
  "",
  "workflow {",
  "  Channel",
  "    .fromPath(params.samples)",
  "    .splitCsv(header: true)",
  "    .map { row -> tuple(row.sample_id, [file(row.fastq_1), file(row.fastq_2)]) }",
  "    .set { sample_reads }",
  "}"
].join("\n");

const patched = applySampleValidationPatchText(pipeline);
assert.strictEqual(patched.changed, true);
assert.strictEqual(patched.reason, "patched");
assert(patched.text.includes("def validateSampleRow"));
assert(patched.text.includes(".map { row -> validateSampleRow(row) }"));

const secondPass = applySampleValidationPatchText(patched.text);
assert.strictEqual(secondPass.changed, false);
assert.strictEqual(secondPass.reason, "already-present");

const unsupported = applySampleValidationPatchText("workflow {\n  sample_reads.view()\n}");
assert.strictEqual(unsupported.changed, false);
assert.strictEqual(unsupported.reason, "pattern-not-found");

console.log("sample validation patch tests passed");
