"use strict";

const assert = require("assert");
const { renderExecutionResult, renderServiceRunPlan } = require("../src/serviceRunPlan");

const plan = {
  status: "blocked",
  root: "/workspace/demo",
  execution_allowed: false,
  error_count: 3,
  warning_count: 8,
  commands: [
    {
      id: "nextflow-1",
      engine: "nextflow",
      mode: "stub-run",
      command: "nextflow run pipeline.nf -stub-run",
      execution_allowed: false,
      blocked_reason: "Error-level findings remain."
    }
  ],
  safety_notes: ["Only dry-run and stub-run commands are generated."],
  provenance: ["Capture command and working directory."]
};

const renderedPlan = renderServiceRunPlan(plan);
assert(renderedPlan.includes("# Dogma Local Service Run Plan"));
assert(renderedPlan.includes("Status: blocked"));
assert(renderedPlan.includes("`nextflow run pipeline.nf -stub-run`"));
assert(renderedPlan.includes("Error-level findings remain."));

const renderedResult = renderExecutionResult({
  status: "preview",
  executed: false,
  command: { command: "nextflow run pipeline.nf -stub-run" },
  message: "Command was not executed.",
  stdout: "out",
  stderr: "err"
});
assert(renderedResult.includes("# Dogma Local Service Execution Result"));
assert(renderedResult.includes("Executed: false"));
assert(renderedResult.includes("```text\nout\n```"));
assert(renderedResult.includes("```text\nerr\n```"));

console.log("service run plan tests passed");
