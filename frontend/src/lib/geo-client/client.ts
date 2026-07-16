import { QuerySpec, GeoDatasetCandidate } from "./types";

/**
 * Configuration options for the GeoSearchClient
 */
export interface GeoSearchClientOptions {
  /** Base URL of the FastAPI backend (e.g., "http://localhost:8000") */
  baseUrl: string;
}

/**
 * Client for interacting with the GEO search FastAPI backend
 */
export class GeoSearchClient {
  private baseUrl: string;

  /**
   * Creates a new GeoSearchClient instance
   * @param options - Configuration options
   */
  constructor(options: GeoSearchClientOptions) {
    // Remove trailing slash from baseUrl
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
  }

  /**
   * Search for GEO datasets matching the given query specification
   * @param spec - Query specification defining search criteria
   * @param maxResults - Maximum number of results to return (default: 50)
   * @returns Promise resolving to an array of matching GEO dataset candidates
   * @throws Error if the API request fails
   */
  async searchGeo(
    spec: QuerySpec,
    maxResults: number = 50
  ): Promise<GeoDatasetCandidate[]> {
    const resp = await fetch(
      `${this.baseUrl}/geo/search?max_results=${maxResults}`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(spec),
      }
    );

    if (!resp.ok) {
      const errorText = await resp.text().catch(() => "Unknown error");
      throw new Error(
        `GEO search failed with status ${resp.status}: ${errorText}`
      );
    }

    const data = await resp.json();
    return data as GeoDatasetCandidate[];
  }

  /**
   * Get the health status of the backend API
   * @returns Promise resolving to the health check response
   */
  async healthCheck(): Promise<{ status: string }> {
    const resp = await fetch(`${this.baseUrl}/health`);

    if (!resp.ok) {
      throw new Error(`Health check failed with status ${resp.status}`);
    }

    return await resp.json();
  }
}
