"""Base class for all data source connectors.

This module provides the abstract base class that all data connectors must implement,
ensuring consistency across different bioinformatics databases (GEO, ENA, PDB, etc.).

This follows the same pattern as LLMProvider for extensibility and maintainability.
"""

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class DataSourceType(str, Enum):
    """Types of data sources supported by the framework."""

    GENOMICS = "genomics"  # GEO, ENA, SRA
    PROTEOMICS = "proteomics"  # PRIDE, ProteomeXchange
    STRUCTURAL = "structural"  # PDB, AlphaFold
    CHEMICAL = "chemical"  # DrugBank, ChEMBL, PubChem
    CLINICAL = "clinical"  # ClinicalTrials.gov
    METABOLOMICS = "metabolomics"  # MetaboLights
    LITERATURE = "literature"  # PubMed, Europe PMC


class ExportFormat(str, Enum):
    """Supported export formats for curated datasets."""

    JSON = "json"
    JSONLD = "jsonld"
    PARQUET = "parquet"
    MAGETAB = "magetab"  # MicroArray Gene Expression Tabular
    ISATAB = "isatab"  # Investigation/Study/Assay Tabular
    SRA = "sra"  # For ENA/SRA submissions


class DataConnector(ABC):
    """Abstract base class for data source connectors.

    All data connectors (GEO, ENA, PDB, DrugBank, etc.) must implement this interface
    to ensure consistency across the framework. This enables:

    1. Pluggability - New connectors can be added without modifying existing code
    2. Consistency - All connectors follow the same interface
    3. Type Safety - Full type annotations for better IDE support
    4. Testability - Easy to create mock connectors for testing

    Example:
        >>> from quration.data_sources.factory import get_data_connector
        >>> connector = get_data_connector("geo")
        >>> results = connector.search_datasets("melanoma immunotherapy")
        >>> matrix = connector.download_expression_data(results[0]['id'])
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Connector name (e.g., 'geo', 'ena', 'pdb').

        Returns:
            Lowercase connector identifier
        """
        pass

    @property
    @abstractmethod
    def source_type(self) -> DataSourceType:
        """Type of data source.

        Returns:
            DataSourceType enum value
        """
        pass

    @property
    @abstractmethod
    def supported_export_formats(self) -> List[ExportFormat]:
        """List of export formats supported by this connector.

        Returns:
            List of ExportFormat enum values
        """
        pass

    @abstractmethod
    def search_datasets(
        self, query: str, limit: int = 50, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Search for datasets matching query.

        Args:
            query: Search query (connector-specific format)
            limit: Maximum number of results to return
            **kwargs: Connector-specific parameters

        Returns:
            List of dataset metadata dictionaries. Each dict should contain at minimum:
                - id: Dataset identifier
                - title: Dataset title
                - summary: Brief description

        Example:
            >>> results = connector.search_datasets("breast cancer RNA-seq", limit=10)
            >>> print(results[0]['title'])
        """
        pass

    @abstractmethod
    def fetch_dataset_metadata(self, dataset_id: str) -> Dict[str, Any]:
        """Fetch comprehensive metadata for a specific dataset.

        Args:
            dataset_id: Dataset identifier (connector-specific format)

        Returns:
            Dictionary containing full dataset metadata

        Example:
            >>> metadata = connector.fetch_dataset_metadata("GSE123456")
            >>> print(metadata['organism'])
        """
        pass

    @abstractmethod
    def fetch_samples(
        self, dataset_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch sample-level metadata for a dataset.

        Args:
            dataset_id: Dataset identifier
            limit: Maximum number of samples to return (None = all)

        Returns:
            List of sample metadata dictionaries

        Example:
            >>> samples = connector.fetch_samples("GSE123456", limit=50)
            >>> print(len(samples))
        """
        pass

    @abstractmethod
    def download_expression_data(
        self, dataset_id: str, output_dir: Optional[Path] = None
    ) -> Optional[Any]:
        """Download expression/measurement data if available.

        Args:
            dataset_id: Dataset identifier
            output_dir: Optional output directory for downloaded files

        Returns:
            ExpressionMatrix object or None if not applicable for this data type

        Example:
            >>> matrix = connector.download_expression_data("GSE123456")
            >>> if matrix:
            >>>     print(f"{matrix.n_genes} genes x {matrix.n_samples} samples")
        """
        pass

    def validate_dataset_id(self, dataset_id: str) -> bool:
        """Validate that a dataset ID matches the expected format.

        Args:
            dataset_id: Dataset identifier to validate

        Returns:
            True if valid, False otherwise

        Note:
            Default implementation returns True. Override in subclasses for
            connector-specific validation.
        """
        return True

    def get_dataset_url(self, dataset_id: str) -> str:
        """Get the public URL for a dataset.

        Args:
            dataset_id: Dataset identifier

        Returns:
            URL string

        Note:
            Default implementation returns empty string. Override in subclasses.
        """
        return ""

    def export_to_standard_format(
        self, dataset: Any, format: ExportFormat, output_dir: Path
    ) -> Dict[str, Path]:
        """Export dataset to a standard format.

        Args:
            dataset: CuratedDataset object to export
            format: Export format (from ExportFormat enum)
            output_dir: Output directory for exported files

        Returns:
            Dictionary mapping file type to file path

        Raises:
            NotImplementedError: If format not supported by this connector

        Example:
            >>> files = connector.export_to_standard_format(
            ...     dataset=my_dataset,
            ...     format=ExportFormat.MAGETAB,
            ...     output_dir=Path("./output")
            ... )
            >>> print(files['idf'])  # Path to IDF file
        """
        if format not in self.supported_export_formats:
            raise NotImplementedError(
                f"{format.value} export not supported by {self.name} connector. "
                f"Supported formats: {[f.value for f in self.supported_export_formats]}"
            )

        # Import here to avoid circular dependency
        from quration.storage.formats import OutputFormatter

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Default implementations for common formats
        if format == ExportFormat.JSON:
            json_str = OutputFormatter.to_json(dataset, pretty=True)
            json_path = output_dir / f"{dataset.dataset_id}.json"
            json_path.write_text(json_str)
            return {"json": json_path}

        elif format == ExportFormat.JSONLD:
            jsonld_data = OutputFormatter.to_jsonld(dataset)
            jsonld_path = output_dir / f"{dataset.dataset_id}.jsonld"
            import json

            jsonld_path.write_text(json.dumps(jsonld_data, indent=2))
            return {"jsonld": jsonld_path}

        elif format == ExportFormat.PARQUET:
            parquet_path = output_dir / f"{dataset.dataset_id}.parquet"
            OutputFormatter.to_parquet(dataset, parquet_path)
            return {"parquet": parquet_path}

        else:
            # Subclasses must override for MAGE-TAB, ISA-TAB, etc.
            raise NotImplementedError(
                f"{format.value} export must be implemented by {self.name} connector"
            )

    def __repr__(self) -> str:
        """String representation of connector."""
        return f"{self.__class__.__name__}(name='{self.name}', type='{self.source_type.value}')"
