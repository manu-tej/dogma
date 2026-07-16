/**
 * Example Component Using GEO Search Hook
 *
 * Demonstrates how to use the useGeoSearch hook in a React component
 */

import React, { useState } from "react";
import { useGeoSearch } from "@/hooks/useGeoSearch";
import type { GeoDatasetCandidate } from "@/lib/geo-client";

/**
 * Example component showing GEO search functionality
 */
export function GeoSearchExample() {
  const [query, setQuery] = useState("");
  const { search, loading, error, results, clearResults, lastQuery } =
    useGeoSearch();

  const handleSearch = async () => {
    if (query.trim()) {
      await search(query, 20); // Search with max 20 results
    }
  };

  const handleClear = () => {
    setQuery("");
    clearResults();
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">GEO Dataset Search</h1>

      {/* Search Input */}
      <div className="mb-6">
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={(e) => e.key === "Enter" && handleSearch()}
            placeholder="e.g., melanoma checkpoint inhibitor survival"
            className="flex-1 px-4 py-2 border rounded-lg"
            disabled={loading}
          />
          <button
            onClick={handleSearch}
            disabled={loading || !query.trim()}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400"
          >
            {loading ? "Searching..." : "Search"}
          </button>
          <button
            onClick={handleClear}
            disabled={loading}
            className="px-6 py-2 bg-gray-200 rounded-lg hover:bg-gray-300"
          >
            Clear
          </button>
        </div>

        {/* Example Queries */}
        <div className="mt-3 text-sm text-gray-600">
          <p className="font-semibold mb-2">Example queries:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>melanoma checkpoint inhibitor survival</li>
            <li>lung cancer PD-1 immunotherapy response</li>
            <li>breast cancer chemotherapy with 50+ samples</li>
            <li>colorectal cancer CTLA-4 expression</li>
          </ul>
        </div>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p className="mt-2 text-gray-600">Searching GEO datasets...</p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <h3 className="text-red-800 font-semibold">Error</h3>
          <p className="text-red-600">{error}</p>
        </div>
      )}

      {/* Results */}
      {results && !loading && (
        <div>
          <div className="mb-4">
            <h2 className="text-xl font-semibold">
              Found {results.length} dataset{results.length !== 1 ? "s" : ""}
            </h2>
            {lastQuery && (
              <p className="text-gray-600 text-sm">
                Query: "{lastQuery}"
              </p>
            )}
          </div>

          {results.length === 0 ? (
            <div className="text-center py-8 text-gray-600">
              <p>No datasets found matching your query.</p>
              <p className="text-sm mt-2">Try adjusting your search terms.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {results.map((dataset) => (
                <DatasetCard key={dataset.gseId} dataset={dataset} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Card component for displaying a single dataset result
 */
function DatasetCard({ dataset }: { dataset: GeoDatasetCandidate }) {
  return (
    <div className="border rounded-lg p-4 hover:shadow-lg transition-shadow">
      {/* Header */}
      <div className="flex justify-between items-start mb-2">
        <div>
          <h3 className="text-lg font-semibold text-blue-600">
            {dataset.gseId}
          </h3>
          <p className="text-sm text-gray-500">
            {dataset.nSamples
              ? `${dataset.nSamples} samples`
              : "Sample count unknown"}
            {dataset.platforms.length > 0 &&
              ` • ${dataset.platforms.join(", ")}`}
          </p>
        </div>

        {dataset.maybeHasSurvivalData && (
          <span className="bg-green-100 text-green-800 text-xs px-2 py-1 rounded">
            Has Survival Data
          </span>
        )}
      </div>

      {/* Title */}
      <h4 className="font-medium mb-2">{dataset.title}</h4>

      {/* Summary */}
      <p className="text-sm text-gray-700 mb-3 line-clamp-3">
        {dataset.summary}
      </p>

      {/* Experimental Design */}
      {dataset.experimentalDesign.conditions &&
        dataset.experimentalDesign.conditions.length > 0 && (
          <div className="mb-3">
            <p className="text-sm font-semibold text-gray-700 mb-1">
              Experimental Conditions:
            </p>
            <div className="flex flex-wrap gap-2">
              {dataset.experimentalDesign.conditions.map((condition, idx) => (
                <span
                  key={idx}
                  className="text-xs bg-gray-100 px-2 py-1 rounded"
                >
                  {condition.name}
                  {condition.n && ` (n=${condition.n})`}
                </span>
              ))}
            </div>
          </div>
        )}

      {/* Match Reasons */}
      {dataset.matchReasons.length > 0 && (
        <div className="mb-3">
          <p className="text-sm font-semibold text-gray-700 mb-1">
            Why this matched:
          </p>
          <ul className="text-sm text-gray-600 list-disc list-inside">
            {dataset.matchReasons.map((reason, idx) => (
              <li key={idx}>{reason}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Footer */}
      <div className="flex gap-2 mt-3 pt-3 border-t">
        <a
          href={`https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=${dataset.gseId}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-blue-600 hover:underline"
        >
          View on GEO
        </a>
        {dataset.primaryPmid && (
          <a
            href={`https://pubmed.ncbi.nlm.nih.gov/${dataset.primaryPmid}/`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-blue-600 hover:underline"
          >
            View Publication
          </a>
        )}
      </div>
    </div>
  );
}

/**
 * Simplified example showing just the hook usage
 */
export function SimpleGeoSearchExample() {
  const { search, loading, error, results } = useGeoSearch();

  const handleQuickSearch = async () => {
    await search("melanoma checkpoint inhibitor survival", 10);
  };

  return (
    <div className="p-4">
      <button
        onClick={handleQuickSearch}
        disabled={loading}
        className="px-4 py-2 bg-blue-600 text-white rounded"
      >
        {loading ? "Searching..." : "Quick Search"}
      </button>

      {error && <p className="text-red-600 mt-2">Error: {error}</p>}

      {results && (
        <div className="mt-4">
          <p className="font-semibold">Found {results.length} datasets</p>
          <ul className="mt-2 space-y-2">
            {results.map((dataset) => (
              <li key={dataset.gseId} className="border p-2 rounded">
                <strong>{dataset.gseId}</strong>: {dataset.title}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
