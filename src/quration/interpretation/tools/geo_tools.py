"""
GEO (Gene Expression Omnibus) tools for LLM interpretation.

These tools wrap the existing GEOFetcher to provide LLM-callable interfaces
for searching and retrieving GEO dataset metadata.
"""

import logging
from typing import Any

from quration.config import get_config
from quration.data_sources.geo import GEOFetcher
from quration.interpretation.tools.base import (
    BioinformaticsTool,
    ToolDefinition,
    ToolError,
)

logger = logging.getLogger(__name__)


class SearchGEODatasetsTool(BioinformaticsTool):
    """Tool for searching GEO datasets."""

    def __init__(self, fetcher: GEOFetcher | None = None):
        """Initialize the tool.

        Args:
            fetcher: GEOFetcher instance, creates one if not provided
        """
        self._fetcher = fetcher or GEOFetcher()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_geo_datasets",
            description=(
                "Search NCBI GEO (Gene Expression Omnibus) for datasets matching a query. "
                "Use this to find relevant gene expression, ChIP-seq, or other NGS datasets. "
                "Returns a list of GSE accession numbers with summaries."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query - can be natural language or structured. "
                            "Examples: 'lung cancer RNA-seq', 'BRCA1 breast cancer', "
                            "'single cell ATAC-seq mouse brain'"
                        ),
                    },
                    "organism": {
                        "type": "string",
                        "description": "Filter by organism (e.g., 'Homo sapiens', 'Mus musculus')",
                        "default": None,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                "required": ["query"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "datasets": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "accession": {"type": "string"},
                                "title": {"type": "string"},
                                "summary": {"type": "string"},
                                "organism": {"type": "string"},
                                "sample_count": {"type": "integer"},
                            },
                        },
                    },
                    "total_found": {"type": "integer"},
                },
            },
            category="geo",
            rate_limit=3,
            cacheable=True,
            cache_ttl_seconds=3600,
            examples=[
                {
                    "input": {"query": "lung cancer RNA-seq treatment response"},
                    "output": {
                        "datasets": [
                            {
                                "accession": "GSE123456",
                                "title": "RNA-seq of lung cancer cells...",
                                "summary": "...",
                            }
                        ],
                        "total_found": 42,
                    },
                }
            ],
        )

    async def execute(
        self,
        query: str,
        organism: str | None = None,
        max_results: int = 10,
    ) -> dict[str, Any]:
        """Search GEO datasets.

        Args:
            query: Search query
            organism: Optional organism filter
            max_results: Maximum results to return

        Returns:
            dict with datasets and total_found
        """
        try:
            # Add organism to query if specified
            search_query = query
            if organism:
                search_query = f"{query} AND {organism}[Organism]"

            # Search for dataset IDs
            dataset_ids = self._fetcher.search_datasets(search_query, limit=max_results)

            if not dataset_ids:
                return {"datasets": [], "total_found": 0}

            # Fetch summaries for each dataset
            datasets = []
            for dataset_id in dataset_ids:
                try:
                    summary = self._fetcher.fetch_dataset_summary(dataset_id)
                    if summary:
                        datasets.append(
                            {
                                "accession": summary.get("Accession", ""),
                                "title": summary.get("title", ""),
                                "summary": summary.get("summary", ""),
                                "organism": summary.get("taxon", ""),
                                "sample_count": int(summary.get("n_samples", 0)),
                                "platform": summary.get("GPL", ""),
                                "dataset_type": summary.get("gdsType", ""),
                            }
                        )
                except Exception as e:
                    logger.warning(f"Error fetching summary for {dataset_id}: {e}")
                    continue

            return {"datasets": datasets, "total_found": len(datasets)}

        except Exception as e:
            raise ToolError(f"GEO search failed: {e}") from e


class GetGEOMetadataTool(BioinformaticsTool):
    """Tool for fetching detailed GEO dataset metadata."""

    def __init__(self, fetcher: GEOFetcher | None = None):
        """Initialize the tool.

        Args:
            fetcher: GEOFetcher instance, creates one if not provided
        """
        self._fetcher = fetcher or GEOFetcher()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_geo_metadata",
            description=(
                "Get detailed metadata for a specific GEO dataset by its accession number. "
                "Returns comprehensive information including experimental design, "
                "sample characteristics, and protocols."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "gse_accession": {
                        "type": "string",
                        "description": "GEO Series accession number (e.g., 'GSE123456')",
                        "pattern": "^GSE[0-9]+$",
                    },
                },
                "required": ["gse_accession"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "accession": {"type": "string"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "overall_design": {"type": "string"},
                    "organism": {"type": "string"},
                    "sample_count": {"type": "integer"},
                    "platform": {"type": "string"},
                    "pubmed_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
            category="geo",
            rate_limit=3,
            cacheable=True,
            cache_ttl_seconds=3600,
        )

    async def execute(self, gse_accession: str) -> dict[str, Any]:
        """Fetch detailed metadata for a GEO dataset.

        Args:
            gse_accession: GSE accession number

        Returns:
            dict with dataset metadata
        """
        try:
            # Fetch full SOFT format metadata
            full_metadata = self._fetcher.fetch_dataset_full(gse_accession)

            series = full_metadata.get("series", {})
            samples = full_metadata.get("samples", [])

            # Extract PubMed IDs
            pubmed_ids = series.get("Series_pubmed_id", [])
            if isinstance(pubmed_ids, str):
                pubmed_ids = [pubmed_ids]

            return {
                "accession": gse_accession,
                "title": series.get("Series_title", ""),
                "summary": series.get("Series_summary", ""),
                "overall_design": series.get("Series_overall_design", ""),
                "organism": series.get("Series_organism", ""),
                "sample_count": len(samples),
                "platform": series.get("Series_platform_id", ""),
                "pubmed_ids": pubmed_ids,
                "experiment_type": series.get("Series_type", ""),
                "submission_date": series.get("Series_submission_date", ""),
                "last_update": series.get("Series_last_update_date", ""),
                "contributor": series.get("Series_contributor", ""),
            }

        except Exception as e:
            raise ToolError(f"Failed to fetch metadata for {gse_accession}: {e}") from e


class GetGEOSamplesTool(BioinformaticsTool):
    """Tool for fetching sample information from a GEO dataset."""

    def __init__(self, fetcher: GEOFetcher | None = None):
        """Initialize the tool.

        Args:
            fetcher: GEOFetcher instance, creates one if not provided
        """
        self._fetcher = fetcher or GEOFetcher()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_geo_samples",
            description=(
                "Get sample information and characteristics for a GEO dataset. "
                "Returns sample IDs, titles, and experimental characteristics "
                "like tissue, cell type, treatment, etc."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "gse_accession": {
                        "type": "string",
                        "description": "GEO Series accession number (e.g., 'GSE123456')",
                        "pattern": "^GSE[0-9]+$",
                    },
                    "max_samples": {
                        "type": "integer",
                        "description": "Maximum number of samples to return",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 200,
                    },
                },
                "required": ["gse_accession"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "samples": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "gsm_id": {"type": "string"},
                                "title": {"type": "string"},
                                "characteristics": {"type": "object"},
                            },
                        },
                    },
                    "total_samples": {"type": "integer"},
                },
            },
            category="geo",
            rate_limit=3,
            cacheable=True,
            cache_ttl_seconds=3600,
        )

    async def execute(
        self, gse_accession: str, max_samples: int = 50
    ) -> dict[str, Any]:
        """Fetch sample information for a GEO dataset.

        Args:
            gse_accession: GSE accession number
            max_samples: Maximum samples to return

        Returns:
            dict with samples and characteristics
        """
        try:
            # First try to get samples from full metadata
            full_metadata = self._fetcher.fetch_dataset_full(gse_accession)
            samples_data = full_metadata.get("samples", [])

            # If no samples in SOFT, fetch via GSM search
            if not samples_data:
                samples_data = self._fetcher.fetch_gse_samples(
                    gse_accession, limit=max_samples
                )

            samples = []
            for sample in samples_data[:max_samples]:
                # Handle both SOFT format and GSM search format
                if "Sample_geo_accession" in sample:
                    # SOFT format
                    gsm_id = sample.get("Sample_geo_accession", "")
                    title = sample.get("Sample_title", "")
                    characteristics = self._fetcher.extract_sample_characteristics(sample)
                else:
                    # GSM search format
                    gsm_id = sample.get("gsm_id", "")
                    title = sample.get("title", "")
                    characteristics = sample.get("summary", {})

                samples.append(
                    {
                        "gsm_id": gsm_id,
                        "title": title,
                        "characteristics": characteristics,
                    }
                )

            return {
                "samples": samples,
                "total_samples": len(samples),
            }

        except Exception as e:
            raise ToolError(
                f"Failed to fetch samples for {gse_accession}: {e}"
            ) from e


# Factory function to create all GEO tools
def create_geo_tools(fetcher: GEOFetcher | None = None) -> list[BioinformaticsTool]:
    """Create all GEO tools with a shared fetcher.

    Args:
        fetcher: Optional GEOFetcher instance to share

    Returns:
        list of BioinformaticsTool instances
    """
    if fetcher is None:
        fetcher = GEOFetcher()

    return [
        SearchGEODatasetsTool(fetcher),
        GetGEOMetadataTool(fetcher),
        GetGEOSamplesTool(fetcher),
    ]
