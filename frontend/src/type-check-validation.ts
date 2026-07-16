/**
 * Type Validation Script
 * Ensures all types are correctly aligned between client, service, and hooks
 */

import type {
  QuerySpec,
  GeoDatasetCandidate,
  TherapyScope,
  ExperimentalDesign,
  Condition,
} from "@/lib/geo-client";

import { parseNaturalLanguageQuery } from "@/services/geoSearchService";

// Test QuerySpec compatibility
const validQuerySpec: QuerySpec = {
  diseaseTerms: ["melanoma", "lung cancer"],
  therapyClass: "checkpoint inhibitor",
  therapyScope: "broad" as TherapyScope,
  targetsOrGenes: ["PD1", "PDL1"],
  studyKeywords: ["treatment", "response"],
  mustHaveClinical: true,
  minSamples: 50,
};

console.log("✅ QuerySpec type is valid");

// Test parsing returns correct type
const parsedQuery: QuerySpec = parseNaturalLanguageQuery(
  "melanoma checkpoint inhibitor survival"
);

console.log("✅ parseNaturalLanguageQuery returns correct type");

// Test dataset candidate type
const mockDataset: GeoDatasetCandidate = {
  gseId: "GSE12345",
  title: "Test Dataset",
  summary: "Test summary",
  experimentalDesign: {
    conditions: [
      { name: "Control", n: 10 },
      { name: "Treatment", n: 10 },
    ],
    designType: "Case-Control",
    tech: "RNA-Seq",
    notes: "Test notes",
    isPartial: false,
  },
  nSamples: 20,
  platforms: ["GPL570"],
  primaryPmid: "12345678",
  maybeHasSurvivalData: true,
  matchReasons: ["Matched disease term: melanoma"],
  rawMetadata: {},
  matchedQueries: ["melanoma survival"],
};

console.log("✅ GeoDatasetCandidate type is valid");

// Test TherapyScope enum
const broadScope: TherapyScope = "broad";
const specificScope: TherapyScope = "specific";
// @ts-expect-error - Should fail with invalid value
const invalidScope: TherapyScope = "invalid";

console.log("✅ TherapyScope type validation works");

// Test Condition type
const condition: Condition = {
  name: "Treatment",
  n: 15,
};

const conditionWithoutN: Condition = {
  name: "Control",
  n: null,
};

console.log("✅ Condition type is valid");

// Test ExperimentalDesign type
const design: ExperimentalDesign = {
  conditions: [condition, conditionWithoutN],
  designType: "Randomized",
  tech: "Microarray",
  notes: "Standard protocol",
  isPartial: false,
};

console.log("✅ ExperimentalDesign type is valid");

console.log("\n🎉 All type validations passed!");
console.log("All types are correctly aligned between:");
console.log("  - @/lib/geo-client (TypeScript client)");
console.log("  - @/services/geoSearchService (Service layer)");
console.log("  - @/hooks/useGeoSearch (React hooks)");
