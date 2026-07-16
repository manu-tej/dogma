"""GEO Connector - Unified interface for GEO database access.

This module provides the GEOConnector class that implements the DataConnector
interface for accessing GEO (Gene Expression Omnibus) data.

It wraps the existing GEOFetcher class while adding:
- Expression matrix download capabilities
- MAGE-TAB/ISA-TAB export support
- Unified DataConnector interface
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from quration.config import GEOConfig, get_config
from quration.data_sources.base import DataConnector, DataSourceType, ExportFormat
from quration.data_sources.geo import GEOFetcher
from quration.data_sources.geo_matrix import GEOMatrixDownloader
from quration.models.expression import ExpressionMatrix

logger = logging.getLogger(__name__)


class GEOConnector(DataConnector):
    """GEO (Gene Expression Omnibus) data connector.

    This class implements the unified DataConnector interface for GEO,
    providing:
    - Dataset search and metadata fetching
    - Sample-level metadata
    - Expression matrix downloads
    - Export to MAGE-TAB/ISA-TAB formats

    Example:
        >>> from quration.data_sources.factory import get_data_connector
        >>> geo = get_data_connector("geo")
        >>> results = geo.search_datasets("melanoma immunotherapy")
        >>> matrix = geo.download_expression_data(results[0]['Accession'])
    """

    def __init__(self, config: Optional[GEOConfig] = None):
        """Initialize GEO connector.

        Args:
            config: GEO configuration (uses global config if not provided)
        """
        if config is None:
            config = get_config().data_sources.geo

        self.config = config

        # Initialize wrapped GEOFetcher for metadata operations
        self._fetcher = GEOFetcher(config)

        # Initialize matrix downloader
        self._matrix_downloader = GEOMatrixDownloader(config)

    @property
    def name(self) -> str:
        """Connector name."""
        return "geo"

    @property
    def source_type(self) -> DataSourceType:
        """Data source type."""
        return DataSourceType.GENOMICS

    @property
    def supported_export_formats(self) -> List[ExportFormat]:
        """Supported export formats."""
        return [
            ExportFormat.JSON,
            ExportFormat.JSONLD,
            ExportFormat.PARQUET,
            ExportFormat.MAGETAB,  # NEW
            ExportFormat.ISATAB,  # NEW
        ]

    def search_datasets(
        self, query: str, limit: int = 50, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Search for GEO datasets matching query.

        Args:
            query: Search query (natural language or structured)
            limit: Maximum number of results
            **kwargs: Additional parameters:
                - experiment_type: Filter by experiment type
                - entry_types: Filter by entry types

        Returns:
            List of dataset metadata dictionaries with keys:
                - id: Dataset ID (numeric)
                - Accession: GSE accession
                - title: Dataset title
                - summary: Dataset summary
                - ... (additional metadata fields)

        Example:
            >>> geo = GEOConnector()
            >>> results = geo.search_datasets("melanoma", limit=10)
            >>> for dataset in results:
            ...     print(dataset['Accession'], dataset['title'])
        """
        # Use GEOFetcher to search
        dataset_ids = self._fetcher.search_datasets(
            query=query,
            limit=limit,
            experiment_type=kwargs.get("experiment_type"),
            entry_types=kwargs.get("entry_types"),
        )

        # Fetch metadata for each dataset
        results = []
        for dataset_id in dataset_ids:
            try:
                metadata = self._fetcher.fetch_dataset_summary(dataset_id)
                if metadata:
                    # Add the numeric ID
                    metadata["id"] = dataset_id
                    results.append(metadata)
            except Exception as e:
                logger.warning(f"Failed to fetch metadata for {dataset_id}: {e}")
                continue

        return results

    def fetch_dataset_metadata(self, dataset_id: str) -> Dict[str, Any]:
        """Fetch comprehensive metadata for a GEO dataset.

        Args:
            dataset_id: GEO dataset identifier (GSE accession or numeric ID)

        Returns:
            Dictionary containing dataset metadata

        Example:
            >>> geo = GEOConnector()
            >>> metadata = geo.fetch_dataset_metadata("GSE123456")
            >>> print(metadata['title'])
        """
        # If dataset_id is a GSE accession, we need to search for it first
        # to get the numeric ID, then fetch the summary
        if dataset_id.upper().startswith("GSE"):
            # Search for the accession to get numeric ID
            results = self._fetcher.search_datasets(
                query=f"{dataset_id}[Accession]", limit=1
            )
            if results:
                numeric_id = results[0]
                return self._fetcher.fetch_dataset_summary(numeric_id)
            else:
                raise ValueError(f"Dataset not found: {dataset_id}")
        else:
            # Assume it's a numeric ID
            return self._fetcher.fetch_dataset_summary(dataset_id)

    def fetch_samples(
        self, dataset_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch sample-level metadata for a dataset.

        Args:
            dataset_id: GEO series accession (e.g., 'GSE123456')
            limit: Maximum number of samples to return

        Returns:
            List of sample metadata dictionaries

        Example:
            >>> geo = GEOConnector()
            >>> samples = geo.fetch_samples("GSE123456", limit=50)
            >>> print(f"Found {len(samples)} samples")
        """
        return self._fetcher.fetch_gse_samples(dataset_id, limit or 100)

    def download_expression_data(
        self, dataset_id: str, output_dir: Optional[Path] = None
    ) -> Optional[ExpressionMatrix]:
        """Download expression matrix from GEO.

        Args:
            dataset_id: GEO series accession (e.g., 'GSE123456')
            output_dir: Optional directory to save downloaded files

        Returns:
            ExpressionMatrix object or None if download fails

        Example:
            >>> geo = GEOConnector()
            >>> matrix = geo.download_expression_data("GSE123456")
            >>> if matrix:
            ...     print(f"{matrix.n_genes} genes x {matrix.n_samples} samples")
            ...     print(f"Matrix type: {matrix.matrix_type.value}")
        """
        return self._matrix_downloader.download_series_matrix(dataset_id, output_dir)

    def validate_dataset_id(self, dataset_id: str) -> bool:
        """Validate GEO dataset ID format.

        Args:
            dataset_id: Dataset identifier

        Returns:
            True if valid GSE format, False otherwise

        Example:
            >>> geo = GEOConnector()
            >>> geo.validate_dataset_id("GSE123456")  # True
            >>> geo.validate_dataset_id("invalid")    # False
        """
        import re

        # Check if it's a valid GSE accession
        if re.match(r"^GSE\d+$", dataset_id.upper()):
            return True
        # Or a numeric ID
        if dataset_id.isdigit():
            return True
        return False

    def get_dataset_url(self, dataset_id: str) -> str:
        """Get public URL for a GEO dataset.

        Args:
            dataset_id: GEO series accession (e.g., 'GSE123456')

        Returns:
            URL string

        Example:
            >>> geo = GEOConnector()
            >>> url = geo.get_dataset_url("GSE123456")
            >>> print(url)
            https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE123456
        """
        # Ensure it's a GSE accession
        if not dataset_id.upper().startswith("GSE"):
            # If numeric ID, we can't construct the URL without fetching metadata
            return ""

        return f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={dataset_id.upper()}"

    def export_to_standard_format(
        self, dataset: Any, format: ExportFormat, output_dir: Path
    ) -> Dict[str, Path]:
        """Export dataset to standard formats.

        Args:
            dataset: CuratedDataset object
            format: Export format
            output_dir: Output directory

        Returns:
            Dictionary mapping file type to file path

        Example:
            >>> geo = GEOConnector()
            >>> files = geo.export_to_standard_format(
            ...     dataset=my_dataset,
            ...     format=ExportFormat.MAGETAB,
            ...     output_dir=Path("./output")
            ... )
            >>> print("IDF file:", files['idf'])
            >>> print("SDRF file:", files['sdrf'])
        """
        if format not in self.supported_export_formats:
            raise NotImplementedError(
                f"{format.value} export not supported by GEO connector"
            )

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Handle MAGE-TAB format
        if format == ExportFormat.MAGETAB:
            from quration.storage.magetab import MAGETABFormatter

            formatter = MAGETABFormatter()
            return formatter.to_magetab(dataset, output_dir)

        # Handle ISA-TAB format
        elif format == ExportFormat.ISATAB:
            from quration.storage.isatab import ISATABFormatter

            formatter = ISATABFormatter()
            return formatter.to_isatab(dataset, output_dir)

        # Use default implementation for JSON, JSON-LD, Parquet
        else:
            return super().export_to_standard_format(dataset, format, output_dir)

    # Convenience methods for backward compatibility with GEOFetcher

    def fetch_dataset_full(self, gse_accession: str) -> Dict[str, Any]:
        """Fetch full SOFT format metadata (backward compatibility).

        Args:
            gse_accession: GSE accession

        Returns:
            Parsed SOFT metadata
        """
        return self._fetcher.fetch_dataset_full(gse_accession)

    def smart_search(
        self,
        disease_terms: List[str],
        therapy_class: Optional[str] = None,
        therapy_scope: str = "specific",
        targets_or_genes: Optional[List[str]] = None,
        study_keywords: Optional[List[str]] = None,
        must_have_clinical: bool = False,
        max_results: int = 50,
        include_survival_detection: bool = True,
        include_design_parsing: bool = False,
    ) -> List[Dict[str, Any]]:
        """LLM-assisted smart search (backward compatibility).

        This wraps the existing smart_search method from GEOFetcher.

        Args:
            disease_terms: List of disease terms
            therapy_class: Therapy class
            therapy_scope: "specific" or "broad"
            targets_or_genes: Target genes or proteins
            study_keywords: Additional keywords
            must_have_clinical: Emphasize clinical data
            max_results: Maximum results
            include_survival_detection: Detect survival data
            include_design_parsing: Parse experimental designs

        Returns:
            List of enriched dataset dictionaries
        """
        return self._fetcher.smart_search(
            disease_terms=disease_terms,
            therapy_class=therapy_class,
            therapy_scope=therapy_scope,
            targets_or_genes=targets_or_genes,
            study_keywords=study_keywords,
            must_have_clinical=must_have_clinical,
            max_results=max_results,
            include_survival_detection=include_survival_detection,
            include_design_parsing=include_design_parsing,
        )


# Backward compatibility: Keep GEOFetcher as the main class name
# but make it an alias to GEOConnector
# This ensures existing code continues to work
# GEOFetcher is still defined in geo.py, so we don't override it here
