"""
Data fetcher for downloading raw sequencing data from public repositories.

This module handles downloading FASTQ files from GEO/SRA using nf-core/fetchngs
and converting GEO accessions to SRA accessions.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import requests

from .config_generator import ConfigGenerator
from .models import ExecutionResult, PipelineType
from .nextflow_executor import NextflowExecutor

logger = logging.getLogger(__name__)


class GEOToSRAConverter:
    """Convert GEO accession IDs to SRA accession IDs using NCBI API."""

    EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, email: str, api_key: Optional[str] = None):
        """
        Initialize the converter.

        Args:
            email: Email for NCBI E-utilities (required)
            api_key: Optional NCBI API key for higher rate limits
        """
        self.email = email
        self.api_key = api_key

    def convert_geo_to_sra(self, geo_id: str) -> List[str]:
        """
        Convert a GEO accession to SRA accession IDs.

        Args:
            geo_id: GEO accession (GSE, GSM, or GPL)

        Returns:
            List of SRA accession IDs (SRR, SRX, or SRP)
        """
        logger.info(f"Converting {geo_id} to SRA IDs")

        # Determine GEO type
        if geo_id.startswith("GSE"):
            return self._convert_gse_to_sra(geo_id)
        elif geo_id.startswith("GSM"):
            return self._convert_gsm_to_sra(geo_id)
        else:
            raise ValueError(f"Unsupported GEO accession type: {geo_id}")

    def _convert_gse_to_sra(self, gse_id: str) -> List[str]:
        """Convert GSE (series) to SRA IDs."""
        # Search for the GSE in GEO database
        search_url = f"{self.EUTILS_BASE}/esearch.fcgi"
        search_params = {
            "db": "gds",
            "term": gse_id,
            "retmode": "json",
            "email": self.email,
        }
        if self.api_key:
            search_params["api_key"] = self.api_key

        response = requests.get(search_url, params=search_params, timeout=30)
        response.raise_for_status()
        search_data = response.json()

        if not search_data.get("esearchresult", {}).get("idlist"):
            logger.warning(f"No results found for {gse_id}")
            return []

        geo_uid = search_data["esearchresult"]["idlist"][0]

        # Get links to SRA
        link_url = f"{self.EUTILS_BASE}/elink.fcgi"
        link_params = {
            "dbfrom": "gds",
            "db": "sra",
            "id": geo_uid,
            "retmode": "json",
            "email": self.email,
        }
        if self.api_key:
            link_params["api_key"] = self.api_key

        response = requests.get(link_url, params=link_params, timeout=30)
        response.raise_for_status()
        link_data = response.json()

        # Extract SRA UIDs
        sra_uids = []
        for linkset in link_data.get("linksets", []):
            for linksetdb in linkset.get("linksetdbs", []):
                if linksetdb.get("dbto") == "sra":
                    sra_uids.extend(linksetdb.get("links", []))

        if not sra_uids:
            logger.warning(f"No SRA links found for {gse_id}")
            return []

        # Fetch SRA accessions
        return self._fetch_sra_accessions(sra_uids)

    def _convert_gsm_to_sra(self, gsm_id: str) -> List[str]:
        """Convert GSM (sample) to SRA IDs."""
        # Similar process as GSE but for individual sample
        search_url = f"{self.EUTILS_BASE}/esearch.fcgi"
        search_params = {
            "db": "gds",
            "term": gsm_id,
            "retmode": "json",
            "email": self.email,
        }
        if self.api_key:
            search_params["api_key"] = self.api_key

        response = requests.get(search_url, params=search_params, timeout=30)
        response.raise_for_status()
        search_data = response.json()

        if not search_data.get("esearchresult", {}).get("idlist"):
            logger.warning(f"No results found for {gsm_id}")
            return []

        geo_uid = search_data["esearchresult"]["idlist"][0]

        # Get links to SRA
        link_url = f"{self.EUTILS_BASE}/elink.fcgi"
        link_params = {
            "dbfrom": "gds",
            "db": "sra",
            "id": geo_uid,
            "retmode": "json",
            "email": self.email,
        }
        if self.api_key:
            link_params["api_key"] = self.api_key

        response = requests.get(link_url, params=link_params, timeout=30)
        response.raise_for_status()
        link_data = response.json()

        # Extract SRA UIDs
        sra_uids = []
        for linkset in link_data.get("linksets", []):
            for linksetdb in linkset.get("linksetdbs", []):
                if linksetdb.get("dbto") == "sra":
                    sra_uids.extend(linksetdb.get("links", []))

        if not sra_uids:
            logger.warning(f"No SRA links found for {gsm_id}")
            return []

        return self._fetch_sra_accessions(sra_uids)

    def _fetch_sra_accessions(self, sra_uids: List[str]) -> List[str]:
        """Fetch SRA accessions from UIDs."""
        if not sra_uids:
            return []

        fetch_url = f"{self.EUTILS_BASE}/efetch.fcgi"
        fetch_params = {
            "db": "sra",
            "id": ",".join(sra_uids),
            "retmode": "xml",
            "email": self.email,
        }
        if self.api_key:
            fetch_params["api_key"] = self.api_key

        response = requests.get(fetch_url, params=fetch_params, timeout=60)
        response.raise_for_status()

        # Parse XML to extract SRR accessions
        xml_content = response.text
        srr_pattern = r'<PRIMARY_ID>(SRR\d+)</PRIMARY_ID>'
        srr_matches = re.findall(srr_pattern, xml_content)

        # Also try SRX pattern
        srx_pattern = r'<PRIMARY_ID>(SRX\d+)</PRIMARY_ID>'
        srx_matches = re.findall(srx_pattern, xml_content)

        # Prefer SRR (run) over SRX (experiment)
        accessions = list(set(srr_matches + srx_matches))

        logger.info(f"Found {len(accessions)} SRA accessions")
        return accessions


class DataFetcher:
    """Fetch raw sequencing data using nf-core/fetchngs."""

    def __init__(
        self,
        email: str,
        api_key: Optional[str] = None,
        executor: Optional[NextflowExecutor] = None,
    ):
        """
        Initialize the data fetcher.

        Args:
            email: Email for NCBI API
            api_key: Optional NCBI API key
            executor: Optional Nextflow executor (creates one if not provided)
        """
        self.converter = GEOToSRAConverter(email=email, api_key=api_key)
        self.executor = executor or NextflowExecutor()
        self.config_generator = ConfigGenerator()

    def fetch_from_geo(
        self,
        geo_id: str,
        output_dir: Path,
        download_method: str = "ftp",
        for_pipeline: Optional[str] = "rnaseq",
        wait: bool = True,
    ) -> ExecutionResult:
        """
        Fetch data from GEO by converting to SRA and using fetchngs.

        Args:
            geo_id: GEO accession ID (GSE or GSM)
            output_dir: Output directory for downloaded files
            download_method: Download method (ftp, sratools, aspera)
            for_pipeline: Format output for specific nf-core pipeline
            wait: Whether to wait for completion

        Returns:
            ExecutionResult from fetchngs pipeline
        """
        logger.info(f"Fetching data for {geo_id}")

        # Convert GEO to SRA
        sra_ids = self.converter.convert_geo_to_sra(geo_id)

        if not sra_ids:
            raise ValueError(f"Could not find SRA accessions for {geo_id}")

        # Use fetchngs to download
        return self.fetch_from_sra(
            sra_ids=sra_ids,
            output_dir=output_dir,
            download_method=download_method,
            for_pipeline=for_pipeline,
            wait=wait,
        )

    def fetch_from_sra(
        self,
        sra_ids: List[str],
        output_dir: Path,
        download_method: str = "ftp",
        for_pipeline: Optional[str] = "rnaseq",
        wait: bool = True,
    ) -> ExecutionResult:
        """
        Fetch data from SRA using nf-core/fetchngs.

        Args:
            sra_ids: List of SRA accession IDs
            output_dir: Output directory for downloaded files
            download_method: Download method (ftp, sratools, aspera)
            for_pipeline: Format output for specific nf-core pipeline
            wait: Whether to wait for completion

        Returns:
            ExecutionResult from fetchngs pipeline
        """
        logger.info(f"Fetching {len(sra_ids)} samples from SRA")

        # Generate fetchngs config
        config = self.config_generator.generate_fetchngs_config(
            sra_ids=sra_ids,
            output_dir=output_dir,
            download_method=download_method,
            for_pipeline=for_pipeline,
        )

        # Execute fetchngs
        result = self.executor.execute_pipeline(
            config=config,
            dataset_id=sra_ids[0] if sra_ids else "unknown",
            wait=wait,
        )

        return result

    def get_fastq_directory(self, fetchngs_output: Path) -> Optional[Path]:
        """
        Get the directory containing downloaded FASTQ files from fetchngs output.

        Args:
            fetchngs_output: Output directory from fetchngs

        Returns:
            Path to FASTQ directory if found
        """
        # nf-core/fetchngs outputs to fastq/ subdirectory
        fastq_dir = fetchngs_output / "fastq"

        if fastq_dir.exists():
            return fastq_dir

        # Also check in pipeline-specific subdirectories
        for subdir in fetchngs_output.iterdir():
            if subdir.is_dir() and "fastq" in subdir.name.lower():
                return subdir

        logger.warning(f"Could not find FASTQ directory in {fetchngs_output}")
        return None

    def extract_sra_ids_from_curated_dataset(
        self, curated_dataset: Dict
    ) -> List[str]:
        """
        Extract SRA IDs from curated dataset metadata.

        Args:
            curated_dataset: Curated dataset dictionary

        Returns:
            List of SRA IDs found in metadata
        """
        sra_ids = []

        # Check dataset-level SRA ID
        dataset_id = curated_dataset.get("dataset_id", "")
        if dataset_id and not dataset_id.startswith("GSE"):
            # Try to convert if it's a GEO ID
            try:
                sra_ids.extend(self.converter.convert_geo_to_sra(dataset_id))
            except Exception as e:
                logger.warning(f"Could not convert {dataset_id} to SRA: {e}")

        # Check sample-level SRA IDs
        for sample in curated_dataset.get("samples", []):
            # Look for explicit SRA ID
            sample_sra = sample.get("sra_id")
            if sample_sra and sample_sra.startswith("SRR"):
                sra_ids.append(sample_sra)

            # Also check in characteristics
            characteristics = sample.get("characteristics", {})
            for key, value in characteristics.items():
                if isinstance(value, str) and value.startswith("SRR"):
                    sra_ids.append(value)

        return list(set(sra_ids))  # Remove duplicates
