import { describe, it, expect } from "vitest";
import { parseGeneTable, splitByDirection } from "./interpretationService";

describe("parseGeneTable", () => {
  it("parses tab-separated rows with symbol, log2FC, and pValue", () => {
    const items = parseGeneTable("ESR1\t2.4\t0.001\nMKI67\t-1.7\t0.02");
    expect(items).toEqual([
      { geneSymbol: "ESR1", log2FoldChange: 2.4, pValue: 0.001 },
      { geneSymbol: "MKI67", log2FoldChange: -1.7, pValue: 0.02 },
    ]);
  });

  it("accepts comma and whitespace separators", () => {
    expect(parseGeneTable("EGFR,1.2")).toEqual([{ geneSymbol: "EGFR", log2FoldChange: 1.2 }]);
    expect(parseGeneTable("KRAS 0.9")).toEqual([{ geneSymbol: "KRAS", log2FoldChange: 0.9 }]);
  });

  it("skips blank lines and non-numeric (header) rows", () => {
    const items = parseGeneTable("gene\tlog2FC\n\nTP53\t-3.0\n");
    expect(items).toEqual([{ geneSymbol: "TP53", log2FoldChange: -3.0 }]);
  });

  it("skips rows without a fold change", () => {
    expect(parseGeneTable("LONELYGENE")).toEqual([]);
  });
});

describe("splitByDirection", () => {
  it("splits by the sign of the fold change and drops zeros", () => {
    const { up, down } = splitByDirection([
      { geneSymbol: "A", log2FoldChange: 1 },
      { geneSymbol: "B", log2FoldChange: -2 },
      { geneSymbol: "C", log2FoldChange: 0 },
    ]);
    expect(up.map((g) => g.geneSymbol)).toEqual(["A"]);
    expect(down.map((g) => g.geneSymbol)).toEqual(["B"]);
  });
});
