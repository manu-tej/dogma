/**
 * React Hook for GEO Dataset Search
 *
 * Provides state management and search functionality for GEO dataset queries
 */

import { useState, useCallback } from "react";
import { searchGeo } from "@/services/geoSearchService";
import type { GeoDatasetCandidate } from "@/lib/geo-client";

/**
 * State and actions for GEO search functionality
 */
interface UseGeoSearchResult {
  /** Execute a search with the given query */
  search: (query: string, maxResults?: number) => Promise<GeoDatasetCandidate[]>;
  /** Whether a search is currently in progress */
  loading: boolean;
  /** Error message if search failed, null otherwise */
  error: string | null;
  /** Array of search results, null if no search has been performed */
  results: GeoDatasetCandidate[] | null;
  /** Clear current results and reset state */
  clearResults: () => void;
  /** The last query that was executed */
  lastQuery: string | null;
}

/**
 * Custom hook for GEO dataset search
 *
 * @returns Object containing search function, loading state, error state, and results
 *
 * @example
 * function MyComponent() {
 *   const { search, loading, error, results, clearResults } = useGeoSearch();
 *
 *   const handleSearch = async () => {
 *     await search("melanoma checkpoint inhibitor survival");
 *   };
 *
 *   return (
 *     <div>
 *       <button onClick={handleSearch} disabled={loading}>
 *         Search
 *       </button>
 *       {loading && <p>Searching...</p>}
 *       {error && <p>Error: {error}</p>}
 *       {results && <p>Found {results.length} datasets</p>}
 *     </div>
 *   );
 * }
 */
export function useGeoSearch(): UseGeoSearchResult {
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<GeoDatasetCandidate[] | null>(null);
  const [lastQuery, setLastQuery] = useState<string | null>(null);

  /**
   * Execute a GEO dataset search
   */
  const search = useCallback(
    async (query: string, maxResults: number = 50): Promise<GeoDatasetCandidate[]> => {
      // Validate input
      if (!query || query.trim().length === 0) {
        setError("Search query cannot be empty");
        return [];
      }

      // Reset error state and start loading
      setError(null);
      setLoading(true);
      setLastQuery(query);

      try {
        console.log(`[useGeoSearch] Starting search for: "${query}"`);

        // Perform the search
        const searchResults = await searchGeo(query, maxResults);

        console.log(
          `[useGeoSearch] Search completed. Found ${searchResults.length} results`
        );

        // Update results state
        setResults(searchResults);

        // Return results directly for immediate use
        return searchResults;
      } catch (err) {
        console.error("[useGeoSearch] Search failed:", err);

        // Extract error message
        const errorMessage =
          err instanceof Error
            ? err.message
            : "An unexpected error occurred during search";

        setError(errorMessage);
        setResults(null);

        // Re-throw to let caller handle the error
        throw err;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  /**
   * Clear current search results and reset state
   */
  const clearResults = useCallback(() => {
    console.log("[useGeoSearch] Clearing results");
    setResults(null);
    setError(null);
    setLastQuery(null);
  }, []);

  return {
    search,
    loading,
    error,
    results,
    clearResults,
    lastQuery,
  };
}

/**
 * Hook variant that automatically searches on mount or when query changes
 *
 * @param initialQuery - Query to search for automatically
 * @param maxResults - Maximum number of results
 * @returns Same interface as useGeoSearch
 *
 * @example
 * function AutoSearchComponent() {
 *   const { loading, results, error } = useGeoSearchAuto("melanoma PD-1");
 *
 *   if (loading) return <p>Loading...</p>;
 *   if (error) return <p>Error: {error}</p>;
 *   return <DatasetList datasets={results} />;
 * }
 */
export function useGeoSearchAuto(
  initialQuery: string,
  maxResults: number = 50
): UseGeoSearchResult {
  const searchHook = useGeoSearch();

  // Auto-search on mount or when query changes
  useState(() => {
    if (initialQuery && initialQuery.trim().length > 0) {
      searchHook.search(initialQuery, maxResults);
    }
  });

  return searchHook;
}
