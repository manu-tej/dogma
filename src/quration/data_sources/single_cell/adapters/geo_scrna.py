"""GEO single-cell RNA-seq data adapter."""

from typing import Any

from quration.data_sources.geo import GEOFetcher


class GEOSingleCellFetcher(GEOFetcher):
    """Fetches single-cell RNA-seq datasets from GEO."""

    def search_single_cell_datasets(
        self,
        query: str,
        organism: str | None = None,
        limit: int = 20,
    ) -> list[str]:
        """Search for single-cell RNA-seq datasets in GEO.

        Args:
            query: Search query terms
            organism: Filter by organism (e.g., "Homo sapiens")
            limit: Maximum number of results

        Returns:
            List of GEO dataset IDs
        """
        # Add single-cell specific terms to query
        sc_query = f'{query} AND ("single cell" OR scRNA-seq OR "single-cell RNA")'

        # Add organism filter if specified
        if organism:
            sc_query += f' AND {organism}[Organism]'

        # Use parent class search method
        return self.search_datasets(sc_query, limit=limit, entry_types=["gse"])

    def get_supplementary_file_urls(self, gse_accession: str) -> dict[str, list[str]]:
        """Get URLs for supplementary files.

        Args:
            gse_accession: GSE accession (e.g., 'GSE123456')

        Returns:
            Dictionary mapping file type to list of URLs
        """
        # Fetch full metadata to get supplementary file info
        metadata = self.fetch_dataset_full(gse_accession)

        urls = {"h5ad": [], "mtx": [], "csv": [], "other": []}

        # Extract supplementary file info from series metadata
        series = metadata.get("series", {})

        # Look for supplementary file fields
        supp_file_keys = [
            "Series_supplementary_file",
            "supplementary_file",
            "Series_relation",
        ]

        for key in supp_file_keys:
            if key in series:
                files = series[key]
                if isinstance(files, str):
                    files = [files]

                for file_url in files:
                    file_url = str(file_url)

                    # Categorize by file type
                    if ".h5ad" in file_url.lower():
                        urls["h5ad"].append(file_url)
                    elif ".mtx" in file_url.lower() or "matrix.gz" in file_url.lower():
                        urls["mtx"].append(file_url)
                    elif ".csv" in file_url.lower() or ".tsv" in file_url.lower():
                        urls["csv"].append(file_url)
                    elif file_url.startswith("http"):
                        urls["other"].append(file_url)

        return urls

    def search_single_cell_by_therapeutic_area(
        self,
        disease: str,
        tissue: str | None = None,
        organism: str = "Homo sapiens",
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Search for single-cell datasets by therapeutic area.

        Args:
            disease: Disease term (e.g., "breast cancer", "COVID-19")
            tissue: Optional tissue filter (e.g., "lung", "blood")
            organism: Organism filter
            limit: Maximum number of results

        Returns:
            List of dictionaries with dataset information
        """
        # Build query
        query = disease
        if tissue:
            query += f" {tissue}"

        # Search for dataset IDs
        dataset_ids = self.search_single_cell_datasets(
            query=query, organism=organism, limit=limit
        )

        # Fetch summary information for each dataset
        results = []
        for dataset_id in dataset_ids:
            try:
                summary = self.fetch_dataset_summary(dataset_id)

                if "Accession" in summary:
                    gse_accession = summary["Accession"]

                    # Get supplementary file URLs
                    supp_files = self.get_supplementary_file_urls(gse_accession)

                    dataset_info = {
                        "id": dataset_id,
                        "accession": gse_accession,
                        "title": summary.get("title", ""),
                        "summary": summary.get("summary", ""),
                        "organism": summary.get("taxon", organism),
                        "n_samples": summary.get("n_samples"),
                        "supplementary_files": supp_files,
                        "has_h5ad": len(supp_files["h5ad"]) > 0,
                        "has_mtx": len(supp_files["mtx"]) > 0,
                    }

                    results.append(dataset_info)

            except Exception as e:
                print(f"Error fetching dataset {dataset_id}: {e}")
                continue

        return results
