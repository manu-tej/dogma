"use strict";

const assert = require("assert");
const { renderEvidenceLedger } = require("../src/evidenceLedger");

const direct = renderEvidenceLedger({
  markdown: "# Dogma Evidence Ledger\n\n- Stores support/refute verdicts: false"
});
assert(direct.endsWith("\n"));
assert(direct.includes("Dogma Evidence Ledger"));

const fallback = renderEvidenceLedger({
  summary: { total: 3, blocked: 1, warning: 1, gap: 1, pass: 0, preview: 0, info: 0 },
  entries: [
    {
      status: "pass",
      type: "guardrail_check",
      id: "guardrail-1",
      title: "quration.factual_ledger_not_verdict",
      source: "guardrails"
    },
    {
      status: "gap",
      type: "guardrail_check",
      id: "guardrail-2",
      title: "method.container.FASTQC",
      source: "guardrails"
    }
  ]
});

assert(fallback.includes("Total entries: 3"));
assert(fallback.includes("quration.factual_ledger_not_verdict"));
assert(fallback.includes("method.container.FASTQC"));
assert(fallback.includes("not a biological verdict system"));

console.log("evidence ledger renderer tests passed");
