import { describe, expect, it } from "vitest";

import { ontologyTermUrl } from "./sourceLinks";

describe("ontologyTermUrl", () => {
  it("links UniProt to the entry page", () => {
    expect(ontologyTermUrl("UniProt", "P00533")).toBe(
      "https://www.uniprot.org/uniprotkb/P00533",
    );
  });

  it("uses identifiers.org for GO/MONDO/CHEBI etc.", () => {
    expect(ontologyTermUrl("GO", "0007259")).toBe("https://identifiers.org/GO:0007259");
    expect(ontologyTermUrl("MONDO", "0005233")).toBe("https://identifiers.org/MONDO:0005233");
  });

  it("normalizes a term_id that already carries its prefix", () => {
    expect(ontologyTermUrl("GO", "GO:0007259")).toBe("https://identifiers.org/GO:0007259");
    expect(ontologyTermUrl("CHEBI", "CHEBI:15377")).toBe("https://identifiers.org/CHEBI:15377");
  });

  it("is case-insensitive on the UniProt ontology name", () => {
    expect(ontologyTermUrl("uniprot", "P00001")).toBe(
      "https://www.uniprot.org/uniprotkb/P00001",
    );
  });

  it("returns null when ontology or term_id is missing", () => {
    expect(ontologyTermUrl("", "x")).toBeNull();
    expect(ontologyTermUrl("GO", "")).toBeNull();
  });
});
