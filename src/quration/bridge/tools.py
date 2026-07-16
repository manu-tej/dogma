from typing import Any, Dict, List
from quration.bridge.protocols import Tool
from quration.data_sources.geo import GEOFetcher

class GeoSearchTool:
    """Tool for searching GEO datasets using Quration's GEOFetcher."""
    name = "search_geo_datasets"
    description = "Search for Gene Expression Omnibus (GEO) datasets using natural language queries. Returns metadata and accessions."

    def __init__(self, fetcher: GEOFetcher = None):
        self.fetcher = fetcher or GEOFetcher()

    def execute(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Execute a search for datasets.

        Args:
            query: The search query string.
            limit: Max number of results (default 5).
        """
        print(f"[Tool: GeoSearchTool] Searching for: '{query}' (limit={limit})")
        # Use fetch_datasets_from_query for full metadata
        results = self.fetcher.fetch_datasets_from_query(query, limit=limit)

        # Simplify output for LLM consumption to save tokens
        simplified_results = []
        for r in results:
            summary = r.get("summary", {})
            simplified_results.append({
                "id": r.get("accession"),
                "title": summary.get("title"),
                "organism": summary.get("taxon"),
                "summary": summary.get("summary"),
                "platform": summary.get("gpl_title"),  # Provide platform info if available
                "sample_count": summary.get("n_samples")
            })

        return simplified_results

class GeoSamplesTool:
    """Tool to fetch samples for a specific GSE accession."""
    name = "fetch_geo_samples"
    description = "Fetch sample metadata for a specific GEO Series (GSE) accession."

    def __init__(self, fetcher: GEOFetcher = None):
        self.fetcher = fetcher or GEOFetcher()

    def execute(self, gse_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        print(f"[Tool: GeoSamplesTool] Fetching samples for: {gse_id}")
        return self.fetcher.fetch_gse_samples(gse_id, limit=limit)
