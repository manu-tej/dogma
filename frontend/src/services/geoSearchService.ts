/**
 * GEO Search Service
 *
 * Service layer for GEO dataset search functionality.
 * Provides natural language query parsing and search capabilities.
 */

import { API_BASE_URL } from "@/lib/apiBaseUrl";
import { GeoSearchClient } from "@/lib/geo-client";
import type { QuerySpec, GeoDatasetCandidate } from "@/lib/geo-client";

// Initialize the GEO search client
const geoClient = new GeoSearchClient({
  baseUrl: API_BASE_URL,
});

/**
 * Common cancer types and disease terms for NLP extraction
 */
const DISEASE_PATTERNS = [
  // Cancer types
  /\b(melanoma|lung cancer|breast cancer|prostate cancer|colorectal cancer|pancreatic cancer)\b/gi,
  /\b(renal cell carcinoma|hepatocellular carcinoma|ovarian cancer|bladder cancer)\b/gi,
  /\b(glioblastoma|lymphoma|leukemia|myeloma|sarcoma)\b/gi,
  /\b(nsclc|sclc|tnbc|hcc|rcc|gbm)\b/gi, // Abbreviations
  // General disease terms
  /\b(cancer|carcinoma|tumor|malignancy|neoplasm)\b/gi,
  /\b(disease|disorder|syndrome|condition)\b/gi,
];

/**
 * Therapy-related keywords and patterns
 */
const THERAPY_PATTERNS = {
  checkpoint_inhibitor: [
    /\b(checkpoint inhibitor|immune checkpoint|ici)\b/gi,
    /\b(pd-?1|pd-?l1|ctla-?4)\b/gi,
    /\b(nivolumab|pembrolizumab|atezolizumab|ipilimumab)\b/gi,
  ],
  immunotherapy: [
    /\b(immunotherapy|immune therapy|cancer vaccine)\b/gi,
    /\b(car-?t|cell therapy|adoptive transfer)\b/gi,
  ],
  chemotherapy: [
    /\b(chemotherapy|chemo|cytotoxic)\b/gi,
    /\b(cisplatin|carboplatin|paclitaxel|docetaxel|doxorubicin)\b/gi,
  ],
  targeted_therapy: [
    /\b(targeted therapy|kinase inhibitor|monoclonal antibody)\b/gi,
    /\b(egfr inhibitor|her2 inhibitor|braf inhibitor)\b/gi,
  ],
  radiation: [
    /\b(radiation|radiotherapy|radio therapy)\b/gi,
  ],
};

/**
 * Gene and target patterns
 */
const GENE_PATTERNS = [
  /\b(pd-?1|pdcd1|cd279)\b/gi,
  /\b(pd-?l1|cd274)\b/gi,
  /\b(ctla-?4|cd152)\b/gi,
  /\b(egfr|her2|erbb2|braf|kras|nras)\b/gi,
  /\b(tp53|p53|brca1|brca2|pten)\b/gi,
  /\b(vegf|vegfr|fgfr|met|alk|ros1)\b/gi,
];

/**
 * Extract disease terms from natural language query
 */
function extractDiseaseTerms(query: string): string[] {
  const terms = new Set<string>();

  for (const pattern of DISEASE_PATTERNS) {
    const matches = query.matchAll(pattern);
    for (const match of matches) {
      terms.add(match[0].toLowerCase());
    }
  }

  return Array.from(terms);
}

/**
 * Extract therapy class and scope from query
 */
function extractTherapyInfo(query: string): {
  therapyClass: string | null;
  therapyScope: "specific" | "broad";
} {
  const queryLower = query.toLowerCase();

  // Check each therapy category
  for (const [therapyName, patterns] of Object.entries(THERAPY_PATTERNS)) {
    for (const pattern of patterns) {
      if (pattern.test(query)) {
        // Determine if specific drug names are mentioned (specific scope)
        const hasSpecificDrug = /\b(nivolumab|pembrolizumab|atezolizumab|ipilimumab|cisplatin|carboplatin|paclitaxel)\b/i.test(
          query
        );

        return {
          therapyClass: therapyName.replace("_", " "),
          therapyScope: hasSpecificDrug ? "specific" : "broad",
        };
      }
    }
  }

  return {
    therapyClass: null,
    therapyScope: "broad",
  };
}

/**
 * Extract gene names and targets from query
 */
function extractGenes(query: string): string[] {
  const genes = new Set<string>();

  for (const pattern of GENE_PATTERNS) {
    const matches = query.matchAll(pattern);
    for (const match of matches) {
      genes.add(match[0].toUpperCase().replace(/-/g, ""));
    }
  }

  return Array.from(genes);
}

/**
 * Extract study keywords from query (excluding already-extracted terms)
 */
function extractStudyKeywords(
  query: string,
  diseaseTerms: string[],
  genes: string[]
): string[] {
  const keywords = new Set<string>();

  // Split query into words
  const words = query.toLowerCase().split(/\s+/);

  // Filter out common words and already extracted terms
  const stopWords = new Set([
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "is",
    "was",
    "are",
    "were",
    "been",
    "be",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "can",
  ]);

  const alreadyExtracted = new Set([
    ...diseaseTerms.map((t) => t.toLowerCase()),
    ...genes.map((g) => g.toLowerCase()),
  ]);

  for (const word of words) {
    if (
      word.length > 3 &&
      !stopWords.has(word) &&
      !alreadyExtracted.has(word)
    ) {
      keywords.add(word);
    }
  }

  return Array.from(keywords);
}

/**
 * Parse a natural language query into a structured QuerySpec
 *
 * @param query - Natural language search query
 * @returns Structured QuerySpec object
 *
 * @example
 * parseNaturalLanguageQuery("melanoma patients treated with PD-1 checkpoint inhibitor survival data")
 * // Returns:
 * // {
 * //   diseaseTerms: ["melanoma"],
 * //   therapyClass: "checkpoint inhibitor",
 * //   therapyScope: "broad",
 * //   targetsOrGenes: ["PD1"],
 * //   studyKeywords: ["patients", "treated"],
 * //   mustHaveClinical: true,
 * //   minSamples: null
 * // }
 */
export function parseNaturalLanguageQuery(query: string): QuerySpec {
  // Extract different components
  const diseaseTerms = extractDiseaseTerms(query);
  const { therapyClass, therapyScope } = extractTherapyInfo(query);
  const targetsOrGenes = extractGenes(query);
  const studyKeywords = extractStudyKeywords(query, diseaseTerms, targetsOrGenes);

  // Detect if clinical/survival data is required
  const mustHaveClinical =
    /\b(survival|clinical|outcome|prognosis|mortality|response|efficacy)\b/i.test(
      query
    );

  // Detect minimum sample requirements
  let minSamples: number | null = null;
  const sampleMatch = query.match(/(\d+)\s*(?:\+)?\s*(?:samples|patients)/i);
  if (sampleMatch) {
    minSamples = parseInt(sampleMatch[1], 10);
  }

  return {
    diseaseTerms,
    therapyClass,
    therapyScope,
    targetsOrGenes,
    studyKeywords,
    mustHaveClinical,
    minSamples,
  };
}

/**
 * Search for GEO datasets using a natural language query
 *
 * @param query - Natural language search query
 * @param maxResults - Maximum number of results to return (default: 50)
 * @returns Promise resolving to array of matching GEO dataset candidates
 * @throws Error if the search fails
 *
 * @example
 * const results = await searchGeo("melanoma checkpoint inhibitor survival", 10);
 */
export async function searchGeo(
  query: string,
  maxResults: number = 50
): Promise<GeoDatasetCandidate[]> {
  try {
    console.log("[GeoSearchService] Parsing query:", query);

    // Parse the natural language query into a QuerySpec
    const querySpec = parseNaturalLanguageQuery(query);

    console.log("[GeoSearchService] Parsed QuerySpec:", querySpec);

    // Perform the search
    const results = await geoClient.searchGeo(querySpec, maxResults);

    console.log(
      `[GeoSearchService] Found ${results.length} matching datasets`
    );

    return results;
  } catch (error) {
    console.error("[GeoSearchService] Search failed:", error);

    // Wrap error with more context
    if (error instanceof Error) {
      throw new Error(`GEO search failed: ${error.message}`);
    }

    throw new Error("GEO search failed with an unknown error");
  }
}

/**
 * Check the health of the GEO search backend
 *
 * @returns Promise resolving to health status
 * @throws Error if health check fails
 */
export async function checkGeoHealth(): Promise<{ status: string }> {
  try {
    return await geoClient.healthCheck();
  } catch (error) {
    console.error("[GeoSearchService] Health check failed:", error);
    throw error;
  }
}

/**
 * Progress event from SSE stream
 */
export interface ProgressEvent {
  step: string;
  status: "pending" | "running" | "complete" | "error";
  message: string;
  progress?: number;
  total?: number;
  data?: any;
  timestamp: number;
}

/**
 * Callback for progress updates
 */
export type ProgressCallback = (event: ProgressEvent) => void;

/**
 * Search for GEO datasets with real-time progress updates via SSE
 *
 * @param query - Natural language search query OR pre-parsed QuerySpec
 * @param onProgress - Callback function for progress updates
 * @param conversationId - Optional conversation ID for context storage
 * @param maxResults - Maximum number of results to return (default: 50)
 * @returns Promise resolving to array of matching GEO dataset candidates
 * @throws Error if the search fails
 *
 * @example
 * // With natural language query
 * await searchGeoStreaming(
 *   "melanoma checkpoint inhibitor",
 *   (event) => console.log(`${event.step}: ${event.message}`),
 *   "conv-123"
 * );
 *
 * // With pre-parsed QuerySpec (e.g., with preferences applied)
 * const querySpec = parseNaturalLanguageQuery("melanoma");
 * const mergedQuery = mergePreferencesWithQuery(querySpec, preferences);
 * await searchGeoStreaming(mergedQuery, onProgress, "conv-123");
 */
export async function searchGeoStreaming(
  query: string | QuerySpec,
  onProgress: ProgressCallback,
  conversationId?: string,
  maxResults: number = 50,
  retryCount: number = 0
): Promise<GeoDatasetCandidate[]> {
  console.log("[GeoSearchService] Starting SSE search for:", query, `(attempt ${retryCount + 1}/3)`);

  // Parse the natural language query into a QuerySpec (if not already parsed)
  const querySpec = typeof query === 'string'
    ? parseNaturalLanguageQuery(query)
    : query;

  console.log("[GeoSearchService] Parsed QuerySpec:", querySpec);

  // Build URL with query parameters
  const url = new URL(`${API_BASE_URL}/geo/search/stream`);
  url.searchParams.append("max_results", maxResults.toString());
  if (conversationId) {
    url.searchParams.append("conversation_id", conversationId);
  }

  const TIMEOUT_MS = 60000; // 60 second timeout
  const MAX_RETRIES = 2;

  return new Promise((resolve, reject) => {
    let results: GeoDatasetCandidate[] = [];
    let timeoutId: NodeJS.Timeout | null = null;
    let abortController = new AbortController();

    // Set timeout
    timeoutId = setTimeout(() => {
      console.warn("[GeoSearchService] SSE stream timed out after 60 seconds");
      abortController.abort();

      // Retry if we haven't exceeded max retries
      if (retryCount < MAX_RETRIES) {
        console.log(`[GeoSearchService] Retrying... (${retryCount + 1}/${MAX_RETRIES})`);
        onProgress({
          step: 'retry',
          status: 'running',
          message: `Connection timed out. Retrying... (${retryCount + 1}/${MAX_RETRIES})`,
        });

        // Retry with exponential backoff
        setTimeout(() => {
          searchGeoStreaming(query, onProgress, conversationId, maxResults, retryCount + 1)
            .then(resolve)
            .catch(reject);
        }, 1000 * (retryCount + 1)); // 1s, 2s backoff
      } else {
        reject(new Error("Search timed out after multiple retries. Please try again or refine your query."));
      }
    }, TIMEOUT_MS);

    try {
      // Create EventSource for SSE
      // Note: EventSource doesn't support POST, so we'll use fetch with SSE parsing
      fetch(url.toString(), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify(querySpec),
        signal: abortController.signal,
      })
        .then(async (response) => {
          if (!response.ok) {
            throw new Error(`SSE request failed with status ${response.status}`);
          }

          if (!response.body) {
            throw new Error("Response body is null");
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";

          while (true) {
            const { done, value } = await reader.read();

            if (done) {
              console.log("[GeoSearchService] SSE stream ended");
              break;
            }

            // Decode chunk and add to buffer
            buffer += decoder.decode(value, { stream: true });

            // Process complete messages (separated by double newline)
            const messages = buffer.split("\n\n");
            buffer = messages.pop() || ""; // Keep incomplete message in buffer

            for (const message of messages) {
              if (!message.trim() || !message.startsWith("data: ")) {
                continue;
              }

              try {
                const jsonStr = message.substring(6); // Remove "data: " prefix
                const event: ProgressEvent = JSON.parse(jsonStr);

                console.log("[GeoSearchService] Progress event:", event.step, event.status);

                // Call progress callback
                onProgress(event);

                // Check if this is the final event with results
                if (event.step === "complete" && event.data?.results) {
                  results = event.data.results as GeoDatasetCandidate[];
                  console.log(`[GeoSearchService] Received ${results.length} results from SSE`);
                }

                // Check for errors
                if (event.status === "error") {
                  reject(new Error(event.message));
                  return;
                }
              } catch (parseError) {
                console.warn("[GeoSearchService] Failed to parse SSE message:", message, parseError);
              }
            }
          }

          // Search complete - clear timeout
          if (timeoutId) {
            clearTimeout(timeoutId);
          }
          console.log("[GeoSearchService] Search completed successfully");
          resolve(results);
        })
        .catch((error) => {
          // Clear timeout on error
          if (timeoutId) {
            clearTimeout(timeoutId);
          }

          // Check if it's an abort error (timeout)
          if (error.name === 'AbortError') {
            console.log("[GeoSearchService] Request aborted (timeout)");
            // Timeout handling is done in the timeout callback above
            return;
          }

          console.error("[GeoSearchService] SSE stream error:", error);

          // Retry on network errors if we haven't exceeded max retries
          if (retryCount < MAX_RETRIES && (error.message.includes('fetch') || error.message.includes('network'))) {
            console.log(`[GeoSearchService] Network error, retrying... (${retryCount + 1}/${MAX_RETRIES})`);
            onProgress({
              step: 'retry',
              status: 'running',
              message: `Connection error. Retrying... (${retryCount + 1}/${MAX_RETRIES})`,
            });

            setTimeout(() => {
              searchGeoStreaming(query, onProgress, conversationId, maxResults, retryCount + 1)
                .then(resolve)
                .catch(reject);
            }, 1000 * (retryCount + 1));
          } else {
            reject(error);
          }
        });
    } catch (error) {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      console.error("[GeoSearchService] Failed to start SSE stream:", error);
      reject(error);
    }
  });
}

// Export the client instance for advanced usage
export { geoClient };
