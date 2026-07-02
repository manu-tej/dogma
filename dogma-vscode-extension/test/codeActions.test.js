"use strict";

const assert = require("assert");
const {
  SAMPLE_VALIDATION_MESSAGE,
  actionKindForDiagnostic,
  codeActionDescriptors,
  servicePatchDescriptor
} = require("../src/codeActions");

assert.strictEqual(
  actionKindForDiagnostic({ source: "Dogma", message: SAMPLE_VALIDATION_MESSAGE }),
  "sampleValidationPatch"
);
assert.strictEqual(
  actionKindForDiagnostic({ source: "eslint", message: SAMPLE_VALIDATION_MESSAGE }),
  null
);
assert.strictEqual(
  actionKindForDiagnostic({ source: "Dogma", message: "Different finding" }),
  null
);
assert.strictEqual(
  actionKindForDiagnostic({ source: "Dogma", code: "metadata.missing_sample_id_policy", message: "Metadata is missing policy." }),
  "servicePatchProposal"
);

const actions = codeActionDescriptors([
  { source: "Dogma", message: SAMPLE_VALIDATION_MESSAGE },
  { source: "Dogma", message: SAMPLE_VALIDATION_MESSAGE },
  { source: "Dogma", code: "metadata.missing_sample_id_policy", message: "Metadata is missing policy." },
  { source: "Dogma", code: "metadata.missing_sample_id_policy", message: "Metadata is missing policy." },
  { source: "Dogma", message: "Different finding" }
]);

assert.deepStrictEqual(actions, [
  {
    kind: "sampleValidationPatch",
    title: "Dogma: insert sample-sheet validation helper",
    command: "dogma.applySampleValidationPatch",
    isPreferred: true
  },
  {
    kind: "servicePatch.preview",
    title: "Dogma: preview local service patch for sample identifier policy",
    command: "dogma.previewServicePatchProposal",
    proposalId: "metadata-sample-id-policy-1",
    isPreferred: true
  },
  {
    kind: "servicePatch.apply",
    title: "Dogma: apply local service patch for sample identifier policy",
    command: "dogma.applyServicePatchProposal",
    proposalId: "metadata-sample-id-policy-1",
    isPreferred: false
  }
]);

assert.deepStrictEqual(
  servicePatchDescriptor({ code: "nextflow.sample_sheet_validation" }, "preview"),
  {
    kind: "servicePatch.preview",
    title: "Dogma: preview local service patch for sample-sheet validation",
    command: "dogma.previewServicePatchProposal",
    proposalId: "nextflow-sample-validation-1",
    isPreferred: true
  }
);

console.log("code action tests passed");
