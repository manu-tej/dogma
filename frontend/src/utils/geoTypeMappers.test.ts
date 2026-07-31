import { describe, expect, it } from "vitest";

import {
  generateGeoResponseContent,
  transformGeoDataset,
} from "./geoTypeMappers";
import type { GeoDatasetCandidate } from "../lib/geo-client/types";

/**
 * Three fabrications this file locks out, all of them user-visible:
 *
 *  1. A survival-data count whose numerator ran over every candidate while its
 *     denominator was capped at 5, so 8 hits in 20 datasets rendered as
 *     "8 out of 5 top datasets".
 *  2. The backend's `maybe_has_survival_data` heuristic surfaced as a definite
 *     "Available", which sends someone to download a series expecting clinical
 *     outcomes it may not contain.
 *  3. The study abstract fetched from GEO and then discarded, while the UI showed
 *     a template sentence under the heading "Study Description".
 */

function candidate(overrides: Partial<GeoDatasetCandidate> = {}): GeoDatasetCandidate {
  return {
    gseId: "GSE00000",
    title: "A series",
    summary: "",
    nSamples: 6,
    platforms: ["GPL16791"],
    maybeHasSurvivalData: false,
    ...overrides,
  } as GeoDatasetCandidate;
}

describe("survival-data reporting", () => {
  it("never reports more hits than datasets examined", () => {
    // The exact shape of the old bug: 8 of 20, denominator capped at 5.
    const candidates = Array.from({ length: 20 }, (_, i) =>
      candidate({ gseId: `GSE${i}`, maybeHasSurvivalData: i < 8 }),
    );

    const summary = generateGeoResponseContent(candidates, "a query");

    expect(summary).not.toContain("8 out of 5");
    const match = summary.match(/(\d+) of (\d+) datasets?/);
    expect(match, `no count found in: ${summary}`).not.toBeNull();
    const [, hits, considered] = match!;
    expect(Number(hits)).toBeLessThanOrEqual(Number(considered));
  });

  it("counts against the population it actually examined", () => {
    const candidates = Array.from({ length: 20 }, (_, i) =>
      candidate({ gseId: `GSE${i}`, maybeHasSurvivalData: i < 8 }),
    );
    expect(generateGeoResponseContent(candidates, "a query")).toContain("8 of 20 datasets");
  });

  it("hedges the claim rather than asserting availability", () => {
    const summary = generateGeoResponseContent([candidate({ maybeHasSurvivalData: true })], "q");
    expect(summary).toMatch(/may include/);
    expect(summary).not.toMatch(/\*\*Survival data available\*\*/);
  });

  it("says so plainly when nothing appears to have survival data", () => {
    const summary = generateGeoResponseContent([candidate()], "q");
    expect(summary).toMatch(/none of the datasets examined/);
  });

  it("agrees in singular and plural", () => {
    expect(generateGeoResponseContent([candidate({ maybeHasSurvivalData: true })], "q")).toContain(
      "1 of 1 dataset ",
    );
  });
});

describe("transformGeoDataset", () => {
  it("keeps the uncertainty in the field name", () => {
    const row = transformGeoDataset(candidate({ maybeHasSurvivalData: true }));
    expect(row.maybeHasSurvivalData).toBe(true);
    // The old name asserted a fact the backend never claimed.
    expect("survivalData" in row).toBe(false);
  });

  it("carries the real abstract through instead of dropping it", () => {
    const abstract = "We performed ATAC-seq on primary human hepatocytes.";
    expect(transformGeoDataset(candidate({ summary: abstract })).summary).toBe(abstract);
  });

  it("leaves the summary undefined when GEO supplied none", () => {
    // So the UI can say "not provided" rather than composing a sentence. The
    // template it used to render also asserted the assay was RNA-Seq.
    expect(transformGeoDataset(candidate({ summary: "" })).summary).toBeUndefined();
    expect(transformGeoDataset(candidate({ summary: "   " })).summary).toBeUndefined();
  });
});
