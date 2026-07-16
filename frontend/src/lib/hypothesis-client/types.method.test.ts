import { describe, expect, it } from "vitest";

import type { MethodChoice, ProposedTest } from "./types";

describe("ProposedTest.method", () => {
  it("accepts an optional MethodChoice", () => {
    const method: MethodChoice = {
      method_id: "deseq2", name: "DESeq2", score: 0.71,
      source: "structural", rationale: "fits rna_seq",
    };
    const proposed: ProposedTest = {
      edge_id: "e1", gap: "g", pipeline: "p", data_accession: "GSE1", method,
    };
    expect(proposed.method?.name).toBe("DESeq2");
  });

  it("allows method to be omitted", () => {
    const proposed: ProposedTest = {
      edge_id: "e1", gap: "g", pipeline: "p", data_accession: "GSE1",
    };
    expect(proposed.method).toBeUndefined();
  });

  it("carries optional grounding text", () => {
    const m: MethodChoice = {
      method_id: "m:salmon", name: "salmon", score: 0.8,
      source: "structural", rationale: "r", grounding: "# ctx",
    };
    expect(m.grounding).toBe("# ctx");
  });
});
