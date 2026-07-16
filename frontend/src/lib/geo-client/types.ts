/**
 * TypeScript types mirroring the Python FastAPI models for GEO search
 */

/**
 * Therapy scope for search queries
 */
export type TherapyScope = "specific" | "broad";

/**
 * Query specification for GEO dataset search
 */
export interface QuerySpec {
  /** Disease-related search terms */
  diseaseTerms: string[];
  /** Therapy class name (e.g., "checkpoint inhibitor") */
  therapyClass: string | null;
  /** Whether to search for specific therapy or broad therapy class */
  therapyScope: TherapyScope;
  /** Target genes or proteins */
  targetsOrGenes: string[];
  /** Additional study keywords */
  studyKeywords: string[];
  /** Whether clinical data is required */
  mustHaveClinical: boolean;
  /** Minimum number of samples required */
  minSamples: number | null;
}

/**
 * Experimental condition in a study
 */
export interface Condition {
  /** Name of the condition */
  name: string;
  /** Number of samples in this condition */
  n: number | null;
}

/**
 * Experimental design details for a GEO dataset
 */
export interface ExperimentalDesign {
  /** List of experimental conditions */
  conditions: Condition[] | null;
  /** Type of experimental design */
  designType: string | null;
  /** Technology/platform used */
  tech: string | null;
  /** Additional notes about the design */
  notes: string;
  /** Whether the design information is incomplete */
  isPartial: boolean;
}

/**
 * A candidate GEO dataset matching the search criteria
 */
export interface GeoDatasetCandidate {
  /** GEO Series ID (e.g., GSE12345) */
  gseId: string;
  /** Dataset title */
  title: string;
  /** Dataset summary/abstract */
  summary: string;
  /** Organism (e.g., "Homo sapiens") */
  organism?: string;
  /** Experimental design information */
  experimentalDesign: ExperimentalDesign;
  /** Number of samples in the dataset */
  nSamples: number | null;
  /** Platform(s) used */
  platforms: string[];
  /** Primary PubMed ID associated with the dataset */
  primaryPmid: string | null;
  /** Whether the dataset might contain survival data */
  maybeHasSurvivalData: boolean;
  /** Reasons why this dataset matched the query */
  matchReasons: string[];
  /** Raw metadata from GEO */
  rawMetadata: any;
  /** List of queries that matched this dataset */
  matchedQueries: string[];
}
