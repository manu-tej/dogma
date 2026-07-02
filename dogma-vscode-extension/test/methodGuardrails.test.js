"use strict";

const assert = require("assert");
const { renderMethodGuardrails } = require("../src/methodGuardrails");

const direct = renderMethodGuardrails({
  markdown: "# Dogma Method Guardrails\n\n- Pass: 1"
});
assert(direct.endsWith("\n"));
assert(direct.includes("Dogma Method Guardrails"));

const fallback = renderMethodGuardrails({
  summary: { pass: 2, warning: 1, gap: 3, blocked: 1 },
  checks: [
    {
      status: "pass",
      code: "quration.factual_ledger_not_verdict",
      principle: "quration: evidence ledgers are facts",
      detail: "No verdicts are stored."
    },
    {
      status: "gap",
      code: "method.container.FASTQC",
      principle: "methods-graph: concrete executor",
      detail: "FASTQC does not declare a container."
    }
  ]
});

assert(fallback.includes("Pass: 2"));
assert(fallback.includes("quration.factual_ledger_not_verdict"));
assert(fallback.includes("method.container.FASTQC"));
assert(fallback.includes("methods-graph: concrete executor"));

console.log("method guardrails renderer tests passed");
