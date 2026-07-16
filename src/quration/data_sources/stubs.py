"""Stub connectors for demo purposes.

These are placeholder implementations of future connectors (ENA, PDB, DrugBank)
to demonstrate the extensibility of the unified framework.

For the conference demo, these show the vision for multi-omics integration.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from quration.data_sources.base import DataConnector, DataSourceType, ExportFormat


class ENAConnector(DataConnector):
    """European Nucleotide Archive connector (stub for demo).

    Future implementation will provide:
    - Sequencing run metadata
    - FASTQ file downloads
    - SRA format export
    """

    @property
    def name(self) -> str:
        return "ena"

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.GENOMICS

    @property
    def supported_export_formats(self) -> List[ExportFormat]:
        return [
            ExportFormat.JSON,
            ExportFormat.JSONLD,
            ExportFormat.PARQUET,
            ExportFormat.SRA,  # ENA/SRA specific format
        ]

    def search_datasets(
        self, query: str, limit: int = 50, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Search ENA (stub implementation).

        Args:
            query: Search query
            limit: Maximum results
            **kwargs: Additional parameters

        Returns:
            Empty list (stub)
        """
        print(f"[DEMO] ENA Connector: Would search for '{query}' (limit: {limit})")
        print("[DEMO] This connector is coming soon - currently a demo placeholder")
        return []

    def fetch_dataset_metadata(self, dataset_id: str) -> Dict[str, Any]:
        """Fetch ENA dataset metadata (stub).

        Args:
            dataset_id: ENA dataset identifier

        Returns:
            Empty dict (stub)
        """
        print(f"[DEMO] ENA Connector: Would fetch metadata for '{dataset_id}'")
        return {}

    def fetch_samples(
        self, dataset_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch ENA samples (stub).

        Args:
            dataset_id: Dataset identifier
            limit: Maximum samples

        Returns:
            Empty list (stub)
        """
        print(f"[DEMO] ENA Connector: Would fetch samples for '{dataset_id}'")
        return []

    def download_expression_data(
        self, dataset_id: str, output_dir: Optional[Path] = None
    ) -> Optional[Any]:
        """Download FASTQ files (stub).

        Args:
            dataset_id: Dataset identifier
            output_dir: Output directory

        Returns:
            None (stub)
        """
        print(f"[DEMO] ENA Connector: Would download FASTQ files for '{dataset_id}'")
        return None


class PDBConnector(DataConnector):
    """Protein Data Bank connector (stub for demo).

    Future implementation will provide:
    - Protein structure metadata
    - PDB/mmCIF file downloads
    - Structural annotations
    """

    @property
    def name(self) -> str:
        return "pdb"

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.STRUCTURAL

    @property
    def supported_export_formats(self) -> List[ExportFormat]:
        return [
            ExportFormat.JSON,
            ExportFormat.JSONLD,
            ExportFormat.PARQUET,
        ]

    def search_datasets(
        self, query: str, limit: int = 50, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Search PDB (stub implementation).

        Args:
            query: Search query (protein name, PDB ID, etc.)
            limit: Maximum results
            **kwargs: Additional parameters

        Returns:
            Empty list (stub)
        """
        print(f"[DEMO] PDB Connector: Would search for protein structures matching '{query}' (limit: {limit})")
        print("[DEMO] This connector is coming soon - currently a demo placeholder")
        return []

    def fetch_dataset_metadata(self, dataset_id: str) -> Dict[str, Any]:
        """Fetch PDB structure metadata (stub).

        Args:
            dataset_id: PDB ID (e.g., '1ABC')

        Returns:
            Empty dict (stub)
        """
        print(f"[DEMO] PDB Connector: Would fetch structure metadata for '{dataset_id}'")
        return {}

    def fetch_samples(
        self, dataset_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch chains/entities (stub).

        Args:
            dataset_id: PDB ID
            limit: Maximum chains

        Returns:
            Empty list (stub)
        """
        print(f"[DEMO] PDB Connector: Would fetch chains/entities for '{dataset_id}'")
        return []

    def download_expression_data(
        self, dataset_id: str, output_dir: Optional[Path] = None
    ) -> Optional[Any]:
        """Download structure files (stub).

        Args:
            dataset_id: PDB ID
            output_dir: Output directory

        Returns:
            None (stub)
        """
        print(f"[DEMO] PDB Connector: Would download structure files for '{dataset_id}'")
        return None


class DrugBankConnector(DataConnector):
    """DrugBank connector (stub for demo).

    Future implementation will provide:
    - Drug information
    - Drug-target interactions
    - Pharmacological data
    """

    @property
    def name(self) -> str:
        return "drugbank"

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.CHEMICAL

    @property
    def supported_export_formats(self) -> List[ExportFormat]:
        return [
            ExportFormat.JSON,
            ExportFormat.JSONLD,
            ExportFormat.PARQUET,
        ]

    def search_datasets(
        self, query: str, limit: int = 50, **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Search DrugBank (stub implementation).

        Args:
            query: Drug name, indication, target, etc.
            limit: Maximum results
            **kwargs: Additional parameters

        Returns:
            Empty list (stub)
        """
        print(f"[DEMO] DrugBank Connector: Would search for drugs matching '{query}' (limit: {limit})")
        print("[DEMO] This connector is coming soon - currently a demo placeholder")
        return []

    def fetch_dataset_metadata(self, dataset_id: str) -> Dict[str, Any]:
        """Fetch drug information (stub).

        Args:
            dataset_id: DrugBank ID (e.g., 'DB00001')

        Returns:
            Empty dict (stub)
        """
        print(f"[DEMO] DrugBank Connector: Would fetch drug info for '{dataset_id}'")
        return {}

    def fetch_samples(
        self, dataset_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch drug-target interactions (stub).

        Args:
            dataset_id: DrugBank ID
            limit: Maximum interactions

        Returns:
            Empty list (stub)
        """
        print(f"[DEMO] DrugBank Connector: Would fetch drug-target interactions for '{dataset_id}'")
        return []

    def download_expression_data(
        self, dataset_id: str, output_dir: Optional[Path] = None
    ) -> Optional[Any]:
        """Not applicable for chemical data (stub).

        Args:
            dataset_id: DrugBank ID
            output_dir: Output directory

        Returns:
            None
        """
        print(f"[DEMO] DrugBank Connector: Expression data not applicable for drug '{dataset_id}'")
        return None
