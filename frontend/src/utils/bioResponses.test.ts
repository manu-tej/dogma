import { describe, expect, it } from "vitest";

import { generateBioResponse } from "./bioResponses";

describe("generateBioResponse", () => {
  it("does not fabricate records when a live search returns no results", () => {
    const response = generateBioResponse("find breast cancer datasets", null, []);

    expect(response.analysis).toBeUndefined();
    expect(response.content).toContain("No verified GEO datasets");
    expect(response.content).toContain("does not substitute synthetic");
    expect(response.content).not.toMatch(/GSE\d+/);
  });

  it("does not fabricate a response for a request that did not run a search", () => {
    const response = generateBioResponse("tell me more", null, null);

    expect(response.analysis).toBeUndefined();
    expect(response.content).toContain("no synthetic results were generated");
    expect(response.content).not.toMatch(/GSE\d+/);
  });
});
