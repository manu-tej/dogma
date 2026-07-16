/**
 * GEO Search Client Library
 *
 * TypeScript client for interacting with the GEO search FastAPI backend
 */

// Export all types
export type {
  TherapyScope,
  QuerySpec,
  Condition,
  ExperimentalDesign,
  GeoDatasetCandidate,
} from "./types";

// Export client
export { GeoSearchClient } from "./client";
export type { GeoSearchClientOptions } from "./client";
