/**
 * Search clients for the single-cell and proteomics dataset repositories.
 * (GEO search has its own geoSearchService; this covers the other two tabs.)
 */

const API_BASE = import.meta.env.VITE_GEO_API_URL || "http://localhost:8000";

// --- Single-cell (GET /single-cell/search) -------------------------------
// Note: this endpoint returns raw snake_case dicts, not camelCased models.
export interface SingleCellDataset {
  accession: string;
  title: string;
  summary: string;
  organism: string;
  n_samples: number | null;
  has_h5ad: boolean;
  has_mtx: boolean;
}

export async function searchSingleCell(
  query: string,
  organism = "Homo sapiens",
  limit = 20,
): Promise<SingleCellDataset[]> {
  const params = new URLSearchParams({ query, organism, limit: String(limit) });
  const res = await fetch(`${API_BASE}/single-cell/search?${params}`);
  if (!res.ok) throw new Error(`Single-cell search failed (${res.status}).`);
  const data = await res.json();
  return (data?.datasets ?? []) as SingleCellDataset[];
}

// --- Proteomics (POST /proteomics/search) --------------------------------
export interface ProteomicsDataset {
  accession: string;
  title: string;
  description: string;
  organism?: string;
  nAssays?: number;
  instruments: string[];
  experimentTypes: string[];
  quantificationMethods: string[];
  hasQuantificationData: boolean;
  primaryDoi?: string;
  primaryPmid?: string;
  matchReasons: string[];
}

/**
 * Map a free-text query into the structured PRIDE query spec the backend expects.
 * The disease term + broad scope are the minimum required fields.
 */
export async function searchProteomics(
  query: string,
  organism = "Homo sapiens",
): Promise<ProteomicsDataset[]> {
  const res = await fetch(`${API_BASE}/proteomics/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      diseaseTerms: [query],
      therapyScope: "broad",
      studyKeywords: [],
      organism,
    }),
  });
  if (!res.ok) throw new Error(`Proteomics search failed (${res.status}).`);
  return (await res.json()) as ProteomicsDataset[];
}
