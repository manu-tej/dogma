import { describe, it, expect } from "vitest";
import { evidenceFacts, factsSummaryLine } from "./evidence-facts";
import type { EvidenceEntry } from "../hypothesis-client/types";

const mk = (direction: string, accession = "GSE1"): EvidenceEntry =>
  ({
    edge_id: "e1",
    direction,
    weight: 1,
    magnitude: null,
    rationale: null,
    provenance: { kind: "pipeline_run", run_id: "r", data_accession: accession },
  }) as unknown as EvidenceEntry;

describe("evidenceFacts", () => {
  it("counts records by factual consistency, never a verdict", () => {
    const f = evidenceFacts([mk("supports"), mk("refutes"), mk("inconclusive")]);
    expect(f.nRecords).toBe(3);
    expect(f.nConsistent).toBe(1);
    expect(f.nInconsistent).toBe(1);
    expect(f.nInconclusive).toBe(1);
  });

  it("flags methods-graph grounding by accession", () => {
    expect(evidenceFacts([mk("inconclusive", "methods-graph")]).hasMethodsGrounding).toBe(true);
    expect(evidenceFacts([mk("supports")]).hasMethodsGrounding).toBe(false);
  });

  it("summary line is plain facts, no verdict words", () => {
    const line = factsSummaryLine(evidenceFacts([mk("supports"), mk("refutes")]));
    expect(line).toContain("2 analyses");
    expect(line).toContain("1 inconsistent");
    expect(line).not.toMatch(/supported|refuted|proven/i);
  });

  it("empty ledger reads as no analyses", () => {
    expect(factsSummaryLine(evidenceFacts([]))).toBe("No analyses recorded");
  });

  it("singular for one record", () => {
    expect(factsSummaryLine(evidenceFacts([mk("supports")]))).toContain("1 analysis");
  });
});
