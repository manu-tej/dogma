"use strict";

const assert = require("assert");
const {
  patchDiffDocumentContents,
  patchDiffTitle,
  safePatchUriPart
} = require("../src/patchDiffPreview");

const proposal = {
  id: "nextflow sample validation",
  target_file: "workflow/pipeline.nf",
  before: "before\n",
  after: "after\n"
};

assert.strictEqual(safePatchUriPart(proposal.id), "nextflow-sample-validation");
assert.strictEqual(safePatchUriPart(proposal.target_file), "workflow-pipeline.nf");
assert.strictEqual(patchDiffTitle(proposal), "Dogma Patch Preview: workflow/pipeline.nf");
assert.deepStrictEqual(patchDiffDocumentContents(proposal), { before: "before\n", after: "after\n" });
assert.deepStrictEqual(patchDiffDocumentContents({}), { before: "", after: "" });

console.log("patch diff preview tests passed");
