"use strict";

const assert = require("assert");
const { proposalQuickPickItems, selectedProposalId } = require("../src/patchSelection");

const items = proposalQuickPickItems({
  proposals: [
    {
      id: "nextflow-sample-validation-1",
      title: "Add sample sheet row validation",
      kind: "nextflow.sample_sheet_validation",
      target_file: "pipeline.nf",
      rationale: "Validate rows before tuple creation."
    },
    {
      id: "metadata-sample-id-policy-1",
      title: "Add sample identifier policy",
      kind: "metadata.missing_sample_id_policy",
      target_file: "metadata.json"
    }
  ]
});

assert.strictEqual(items.length, 2);
assert.strictEqual(items[0].label, "Add sample sheet row validation");
assert.strictEqual(items[0].description, "nextflow.sample_sheet_validation • pipeline.nf");
assert.strictEqual(items[0].detail, "Validate rows before tuple creation.");
assert.strictEqual(items[1].proposalId, "metadata-sample-id-policy-1");
assert.strictEqual(selectedProposalId(items[1]), "metadata-sample-id-policy-1");
assert.strictEqual(selectedProposalId({ proposal: { id: "fallback-id" } }), "fallback-id");
assert.strictEqual(selectedProposalId(undefined), undefined);

console.log("patch selection tests passed");
