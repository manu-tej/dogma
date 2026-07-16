import type { GeoDatasetCandidate } from "@/lib/geo-client";
import { generateGeoResponseContent, mapGeoDatasetToAnalysis } from "./geoTypeMappers";

interface ReasoningStep {
  id: string;
  type: "query_generation" | "ncbi_search" | "metadata_fetch" | "filtering" | "results";
  title: string;
  description: string;
  status: "pending" | "running" | "complete";
}

interface BioResponse {
  content: string;
  analysis?: {
    type: string;
    data: unknown;
  };
}

export function generateReasoningSteps(_query: string): ReasoningStep[] {
  return [
    {
      id: "1",
      type: "query_generation",
      title: "Generating Search Queries",
      description: "Creating NCBI search queries from the request",
      status: "pending",
    },
    {
      id: "2",
      type: "ncbi_search",
      title: "Searching NCBI GEO",
      description: "Querying GEO with the generated search terms",
      status: "pending",
    },
    {
      id: "3",
      type: "metadata_fetch",
      title: "Fetching Dataset Details",
      description: "Retrieving metadata for returned accessions",
      status: "pending",
    },
    {
      id: "4",
      type: "filtering",
      title: "Filtering & Ranking",
      description: "Applying the requested filters and ranking criteria",
      status: "pending",
    },
    {
      id: "5",
      type: "results",
      title: "Search Complete",
      description: "Preparing the verified search response",
      status: "pending",
    },
  ];
}

/** Return whether a request should be sent to the live GEO search API. */
export function isGeoQuery(query: string): boolean {
  const lowerQuery = query.toLowerCase();
  const geoKeywords = [
    "dataset",
    "datasets",
    "geo",
    "gse",
    "study",
    "studies",
    "find",
    "search",
    "look for",
    "looking for",
    "rna-seq",
    "rnaseq",
    "rna seq",
    "sequencing",
    "expression",
    "transcriptome",
    "microarray",
  ];
  const biologicalContext = [
    "cancer",
    "tumor",
    "carcinoma",
    "melanoma",
    "leukemia",
    "disease",
    "syndrome",
    "disorder",
    "patients",
    "samples",
    "tissue",
    "clinical",
    "survival",
  ];

  return (
    geoKeywords.some((keyword) => lowerQuery.includes(keyword)) ||
    biologicalContext.some((keyword) => lowerQuery.includes(keyword))
  );
}

/**
 * Render only results returned by the live backend. An empty or absent result
 * set is represented explicitly; this function never invents accessions,
 * sample counts, clinical attributes, or analysis output.
 */
export function generateBioResponse(
  query: string,
  _dataset: string | null,
  geoResults?: GeoDatasetCandidate[] | null,
): BioResponse {
  if (geoResults && geoResults.length > 0) {
    return {
      content: generateGeoResponseContent(geoResults, query),
      analysis: {
        type: "Verified GEO Search Results",
        data: mapGeoDatasetToAnalysis(geoResults),
      },
    };
  }

  if (Array.isArray(geoResults)) {
    return {
      content:
        "No verified GEO datasets were returned for this query. Dogma does not " +
        "substitute synthetic accessions or sample statistics when a live search is empty.",
    };
  }

  return {
    content:
      "Dogma does not have a verified dataset response for this request. Run a GEO " +
      "dataset search or use the causal graph workspace; no synthetic results were generated.",
  };
}
