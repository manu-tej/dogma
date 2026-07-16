/**
 * Tests for GEO Search Service
 *
 * These tests verify the natural language query parsing functionality
 */

import { parseNaturalLanguageQuery } from "../geoSearchService";

describe("parseNaturalLanguageQuery", () => {
  it("should extract disease terms correctly", () => {
    const query = "melanoma patients with lung cancer";
    const result = parseNaturalLanguageQuery(query);

    expect(result.diseaseTerms).toContain("melanoma");
    expect(result.diseaseTerms).toContain("lung cancer");
  });

  it("should detect checkpoint inhibitor therapy", () => {
    const query = "melanoma treated with checkpoint inhibitor";
    const result = parseNaturalLanguageQuery(query);

    expect(result.therapyClass).toBe("checkpoint inhibitor");
    expect(result.therapyScope).toBe("broad");
  });

  it("should detect specific therapy when drug names mentioned", () => {
    const query = "melanoma treated with pembrolizumab";
    const result = parseNaturalLanguageQuery(query);

    expect(result.therapyClass).toBe("checkpoint inhibitor");
    expect(result.therapyScope).toBe("specific");
  });

  it("should extract gene targets", () => {
    const query = "melanoma PD-1 and PD-L1 expression";
    const result = parseNaturalLanguageQuery(query);

    expect(result.targetsOrGenes).toContain("PD1");
    expect(result.targetsOrGenes).toContain("PDL1");
  });

  it("should detect survival data requirement", () => {
    const query = "melanoma survival outcomes";
    const result = parseNaturalLanguageQuery(query);

    expect(result.mustHaveClinical).toBe(true);
  });

  it("should not require clinical data for basic queries", () => {
    const query = "melanoma gene expression";
    const result = parseNaturalLanguageQuery(query);

    expect(result.mustHaveClinical).toBe(false);
  });

  it("should extract minimum sample requirements", () => {
    const query = "melanoma with 50+ samples";
    const result = parseNaturalLanguageQuery(query);

    expect(result.minSamples).toBe(50);
  });

  it("should handle complex queries correctly", () => {
    const query =
      "melanoma patients treated with PD-1 checkpoint inhibitor survival data 100 samples";
    const result = parseNaturalLanguageQuery(query);

    expect(result.diseaseTerms).toContain("melanoma");
    expect(result.therapyClass).toBe("checkpoint inhibitor");
    expect(result.targetsOrGenes).toContain("PD1");
    expect(result.mustHaveClinical).toBe(true);
    expect(result.minSamples).toBe(100);
  });

  it("should handle immunotherapy queries", () => {
    const query = "lung cancer immunotherapy response";
    const result = parseNaturalLanguageQuery(query);

    expect(result.diseaseTerms).toContain("lung cancer");
    expect(result.therapyClass).toBe("immunotherapy");
  });

  it("should handle chemotherapy queries", () => {
    const query = "breast cancer cisplatin chemotherapy";
    const result = parseNaturalLanguageQuery(query);

    expect(result.diseaseTerms).toContain("breast cancer");
    expect(result.therapyClass).toBe("chemotherapy");
    expect(result.therapyScope).toBe("specific");
  });

  it("should extract study keywords", () => {
    const query = "melanoma treatment response biomarkers";
    const result = parseNaturalLanguageQuery(query);

    expect(result.studyKeywords).toContain("treatment");
    expect(result.studyKeywords).toContain("response");
    expect(result.studyKeywords).toContain("biomarkers");
  });

  it("should handle queries with no specific therapy", () => {
    const query = "melanoma gene expression data";
    const result = parseNaturalLanguageQuery(query);

    expect(result.therapyClass).toBe(null);
    expect(result.diseaseTerms).toContain("melanoma");
  });

  it("should normalize gene names", () => {
    const query = "PD-1 and CTLA-4 expression";
    const result = parseNaturalLanguageQuery(query);

    // Hyphens should be removed and uppercase
    expect(result.targetsOrGenes).toContain("PD1");
    expect(result.targetsOrGenes).toContain("CTLA4");
  });
});
