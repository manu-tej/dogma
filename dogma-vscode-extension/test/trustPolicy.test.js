"use strict";

const assert = require("assert");
const { renderTrustStatus, renderTrustWriteResult } = require("../src/trustPolicy");

const result = {
  root: "/workspace/demo",
  summary: { risk_level: "blocked", errors: 3, warnings: 8, genome_build: "GRCh38" },
  trust: {
    status: "untrusted",
    trusted: false,
    human_data: true,
    policy_present: false,
    policy_path: "/workspace/demo/.dogma/trust.json",
    blockers: ["Human data is detected."],
    required_for: ["local workflow dry-run/stub-run execution"]
  }
};

const status = renderTrustStatus(result);
assert(status.includes("# Dogma Workspace Trust"));
assert(status.includes("Status: untrusted"));
assert(status.includes("Human data detected: true"));
assert(status.includes("Human data is detected."));

const written = renderTrustWriteResult({
  ...result,
  write: { status: "written", policy_path: "/workspace/demo/.dogma/trust.json" },
  trust: { ...result.trust, status: "trusted", trusted: true, policy_present: true, policy: { trusted: true } }
});
assert(written.includes("# Dogma Trust Policy Write Result"));
assert(written.includes("Write status: written"));
assert(written.includes('"trusted": true'));

console.log("trust policy renderer tests passed");
