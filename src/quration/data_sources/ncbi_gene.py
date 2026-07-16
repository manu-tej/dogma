"""
NCBI Gene E-utilities client for gene information.

This module provides a client for retrieving gene information from NCBI Gene
using E-utilities.

API Documentation: https://www.ncbi.nlm.nih.gov/books/NBK25499/
"""

import logging
import time
import xml.etree.ElementTree as ET
from typing import Any

import requests
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from quration.config import get_config

logger = logging.getLogger(__name__)


class GeneInfo(BaseModel):
    """NCBI Gene information."""

    gene_id: int = Field(description="NCBI Gene ID")
    symbol: str = Field(default="", description="Gene symbol")
    name: str = Field(default="", description="Full gene name")
    description: str = Field(default="", description="Gene description/summary")
    organism: str = Field(default="", description="Organism")
    tax_id: int | None = Field(default=None, description="Taxonomy ID")
    aliases: list[str] = Field(default_factory=list, description="Gene aliases")
    chromosome: str = Field(default="", description="Chromosome location")
    map_location: str = Field(default="", description="Cytogenetic location")
    gene_type: str = Field(default="", description="Gene type")
    summary: str = Field(default="", description="Gene summary from RefSeq")


class NCBIGeneClient:
    """Client for NCBI Gene E-utilities API.

    Provides methods for searching genes and retrieving gene information.

    Example:
        ```python
        client = NCBIGeneClient()
        gene = client.get_gene_info("TP53", organism="human")
        summary = client.get_gene_summary(7157)
        ```
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    # Taxonomy IDs for common organisms
    TAXONOMY_IDS = {
        "human": 9606,
        "homo sapiens": 9606,
        "mouse": 10090,
        "mus musculus": 10090,
        "rat": 10116,
        "rattus norvegicus": 10116,
    }

    def __init__(self, rate_limit: int | None = None):
        """Initialize NCBI Gene client.

        Args:
            rate_limit: Requests per second (default: from config)
        """
        config = get_config().data_sources.geo  # Reuse GEO config for NCBI settings
        self.tool = config.tool
        self.email = config.email
        self.api_key = config.api_key

        # Rate limiting: 3/sec without API key, 10/sec with
        if rate_limit is None:
            rate_limit = config.get_effective_rate_limit()

        self.rate_limit = rate_limit
        self._last_request_time = 0.0
        self._min_interval = 1.0 / rate_limit

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _get_tax_id(self, organism: str) -> int:
        """Get taxonomy ID for organism.

        Args:
            organism: Organism name

        Returns:
            Taxonomy ID
        """
        return self.TAXONOMY_IDS.get(organism.lower(), 9606)  # Default to human

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _make_request(
        self, endpoint: str, params: dict[str, Any]
    ) -> requests.Response:
        """Make rate-limited request to E-utilities.

        Args:
            endpoint: E-utilities endpoint
            params: Query parameters

        Returns:
            Response object
        """
        self._rate_limit()

        # Add required NCBI parameters
        params["tool"] = self.tool
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        return response

    def get_gene_info(
        self, gene_symbol: str, organism: str = "human"
    ) -> GeneInfo | None:
        """Get gene information by symbol.

        Args:
            gene_symbol: Gene symbol
            organism: Organism name

        Returns:
            GeneInfo or None
        """
        tax_id = self._get_tax_id(organism)

        try:
            # Search for gene ID
            search_params = {
                "db": "gene",
                "term": f"{gene_symbol}[Gene Name] AND {tax_id}[Taxonomy ID]",
                "retmax": 1,
                "retmode": "xml",
            }

            search_response = self._make_request("esearch.fcgi", search_params)
            search_root = ET.fromstring(search_response.content)

            id_list = search_root.find("IdList")
            if id_list is None:
                return None

            ids = [id_elem.text for id_elem in id_list.findall("Id") if id_elem.text]
            if not ids:
                return None

            gene_id = int(ids[0])

            # Fetch gene details
            return self._fetch_gene(gene_id)

        except Exception as e:
            logger.error(f"Failed to get gene info for {gene_symbol}: {e}")
            return None

    def get_gene_by_id(self, gene_id: int) -> GeneInfo | None:
        """Get gene information by NCBI Gene ID.

        Args:
            gene_id: NCBI Gene ID

        Returns:
            GeneInfo or None
        """
        return self._fetch_gene(gene_id)

    def get_gene_summary(self, gene_id: int) -> str:
        """Get gene summary text.

        Args:
            gene_id: NCBI Gene ID

        Returns:
            Gene summary string
        """
        gene = self._fetch_gene(gene_id)
        return gene.summary if gene else ""

    def get_gene_aliases(self, gene_symbol: str, organism: str = "human") -> list[str]:
        """Get gene aliases.

        Args:
            gene_symbol: Gene symbol
            organism: Organism name

        Returns:
            List of aliases
        """
        gene = self.get_gene_info(gene_symbol, organism)
        return gene.aliases if gene else []

    def search_genes(
        self, query: str, organism: str = "human", max_results: int = 10
    ) -> list[GeneInfo]:
        """Search for genes.

        Args:
            query: Search query
            organism: Organism name
            max_results: Maximum results

        Returns:
            List of GeneInfo
        """
        tax_id = self._get_tax_id(organism)

        try:
            search_params = {
                "db": "gene",
                "term": f"({query}) AND {tax_id}[Taxonomy ID]",
                "retmax": max_results,
                "retmode": "xml",
            }

            search_response = self._make_request("esearch.fcgi", search_params)
            search_root = ET.fromstring(search_response.content)

            id_list = search_root.find("IdList")
            if id_list is None:
                return []

            ids = [id_elem.text for id_elem in id_list.findall("Id") if id_elem.text]
            if not ids:
                return []

            # Fetch gene details
            genes = []
            for gene_id in ids:
                gene = self._fetch_gene(int(gene_id))
                if gene:
                    genes.append(gene)

            return genes

        except Exception as e:
            logger.error(f"Gene search failed: {e}")
            return []

    def _fetch_gene(self, gene_id: int) -> GeneInfo | None:
        """Fetch gene details.

        Args:
            gene_id: NCBI Gene ID

        Returns:
            GeneInfo or None
        """
        try:
            # Use docsum for quick summary
            fetch_params = {
                "db": "gene",
                "id": str(gene_id),
                "retmode": "xml",
                "rettype": "docsum",
            }

            response = self._make_request("esummary.fcgi", fetch_params)
            root = ET.fromstring(response.content)

            # Find DocumentSummary
            doc_sum = root.find(".//DocumentSummary")
            if doc_sum is None:
                return None

            # Extract fields
            symbol = ""
            name = ""
            description = ""
            organism = ""
            tax_id = None
            aliases = []
            chromosome = ""
            map_location = ""
            gene_type = ""
            summary = ""

            for child in doc_sum:
                tag = child.tag
                text = child.text or ""

                if tag == "Name":
                    symbol = text
                elif tag == "Description":
                    name = text
                elif tag == "Summary":
                    summary = text
                elif tag == "Organism":
                    org_data = {c.tag: c.text for c in child}
                    organism = org_data.get("ScientificName", "")
                    try:
                        tax_id = int(org_data.get("TaxID", 0))
                    except (ValueError, TypeError):
                        pass
                elif tag == "OtherAliases":
                    aliases = [a.strip() for a in text.split(",") if a.strip()]
                elif tag == "Chromosome":
                    chromosome = text
                elif tag == "MapLocation":
                    map_location = text
                elif tag == "GeneType":
                    gene_type = text

            return GeneInfo(
                gene_id=gene_id,
                symbol=symbol,
                name=name,
                description=description or name,
                organism=organism,
                tax_id=tax_id,
                aliases=aliases,
                chromosome=chromosome,
                map_location=map_location,
                gene_type=gene_type,
                summary=summary,
            )

        except Exception as e:
            logger.error(f"Failed to fetch gene {gene_id}: {e}")
            return None

    def batch_lookup(
        self, gene_symbols: list[str], organism: str = "human"
    ) -> dict[str, GeneInfo | None]:
        """Batch lookup gene info.

        Args:
            gene_symbols: List of gene symbols
            organism: Organism name

        Returns:
            Dict mapping symbols to GeneInfo
        """
        results = {}
        for symbol in gene_symbols:
            results[symbol] = self.get_gene_info(symbol, organism)
        return results
