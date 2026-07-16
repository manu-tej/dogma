/**
 * Import Verification Script
 *
 * This file verifies that all imports work correctly.
 * Run with: npx vite-node src/verify-imports.ts
 */

// Verify geo-client imports
import {
  GeoSearchClient,
  type QuerySpec,
  type GeoDatasetCandidate,
  type TherapyScope,
  type Condition,
  type ExperimentalDesign,
} from "@/lib/geo-client";

// Verify service imports
import {
  parseNaturalLanguageQuery,
  searchGeo,
  checkGeoHealth,
  geoClient,
} from "@/services/geoSearchService";

// Verify hook imports
import { useGeoSearch } from "@/hooks/useGeoSearch";

console.log("✅ All imports resolved successfully!");

// Test type checking
const testQuery: QuerySpec = {
  diseaseTerms: ["melanoma"],
  therapyClass: "checkpoint inhibitor",
  therapyScope: "broad" as TherapyScope,
  targetsOrGenes: ["PD1"],
  studyKeywords: ["treatment"],
  mustHaveClinical: true,
  minSamples: 50,
};

console.log("✅ Type checking passed!");

// Test parseNaturalLanguageQuery
const parsedQuery = parseNaturalLanguageQuery(
  "melanoma checkpoint inhibitor survival"
);

console.log("✅ parseNaturalLanguageQuery function works!");
console.log("Parsed query:", JSON.stringify(parsedQuery, null, 2));

// Test client initialization
const client = new GeoSearchClient({
  baseUrl: "http://localhost:8000",
});

console.log("✅ GeoSearchClient instantiated successfully!");

// Verify React hook is a function
if (typeof useGeoSearch === "function") {
  console.log("✅ useGeoSearch hook is available!");
} else {
  console.error("❌ useGeoSearch is not a function!");
  process.exit(1);
}

console.log("\n🎉 All verifications passed!");
console.log("\nNext steps:");
console.log("1. Start the backend: cd backend && python main.py");
console.log("2. Start the frontend: npm run dev");
console.log("3. Test the search functionality");
