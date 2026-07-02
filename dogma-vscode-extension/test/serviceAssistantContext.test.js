"use strict";

const assert = require("assert");
const { renderServiceAssistantContext } = require("../src/serviceAssistantContext");

const direct = renderServiceAssistantContext({
  markdown: "# Dogma Assistant Context Bundle\n\n- Sample IDs redacted: true"
});
assert(direct.endsWith("\n"));
assert(direct.includes("Sample IDs redacted: true"));

const fallback = renderServiceAssistantContext({
  summary: { risk_level: "blocked", errors: 1, warnings: 2 },
  trust: { status: "untrusted", human_data: true },
  redaction: {
    sample_ids_redacted: true,
    reason: "Human data was detected."
  },
  context: {
    assay: "bulk RNA-seq",
    organism: "human",
    sample_file: "sample_sheet.csv",
    samples: {
      count: 2,
      ids: ["<sample:1>", "<sample:2>"],
      conditions: ["control"]
    },
    reference: {
      genome_build: "GRCh38",
      annotation: "GENCODE v44"
    }
  },
  issues: [
    {
      severity: "error",
      code: "sample_sheet.duplicate_sample_id",
      file: "sample_sheet.csv",
      line: 3,
      message: "Duplicate sample_id '<sample:1>'."
    }
  ]
});

assert(fallback.includes("# Dogma Assistant Context Bundle"));
assert(fallback.includes("Sample IDs redacted: true"));
assert(fallback.includes("Sample IDs: <sample:1>, <sample:2>"));
assert(fallback.includes("Genome build: GRCh38"));
assert(fallback.includes("sample_sheet.duplicate_sample_id"));

console.log("service assistant context renderer tests passed");
