"use strict";

const assert = require("assert");
const { activeFilePatchProposals, normalizePath } = require("../src/activePatchSelection");

assert.strictEqual(normalizePath(".\\workflow\\pipeline.nf"), "workflow/pipeline.nf");
assert.strictEqual(normalizePath("./metadata.json"), "metadata.json");

const result = {
  proposals: [
    { id: "pipeline-1", target_file: "pipeline.nf" },
    { id: "metadata-1", target_file: "metadata.json" },
    { id: "nested-1", target_file: "workflow/pipeline.nf" }
  ]
};

assert.deepStrictEqual(
  activeFilePatchProposals(result, "metadata.json").map((proposal) => proposal.id),
  ["metadata-1"]
);
assert.deepStrictEqual(
  activeFilePatchProposals(result, "pipeline.nf").map((proposal) => proposal.id),
  ["pipeline-1", "nested-1"]
);
assert.deepStrictEqual(activeFilePatchProposals(result, ""), []);

console.log("active patch selection tests passed");
