"""
UniProt REST API client for protein information retrieval.

This module provides a client for accessing UniProt protein data including
gene-to-protein mapping, protein functions, and batch lookups.

API Documentation: https://www.uniprot.org/help/api
"""

import logging
import time
from typing import Any

import requests
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from quration.config import get_config

logger = logging.getLogger(__name__)


class ProteinInfo(BaseModel):
    """Protein information from UniProt."""

    uniprot_id: str = Field(description="UniProt accession ID")
    entry_name: str = Field(default="", description="UniProt entry name")
    protein_name: str = Field(default="", description="Recommended protein name")
    gene_names: list[str] = Field(default_factory=list, description="Gene names")
    organism: str = Field(default="", description="Organism scientific name")
    organism_id: int | None = Field(default=None, description="NCBI taxonomy ID")
    function: str = Field(default="", description="Protein function description")
    subcellular_location: list[str] = Field(
        default_factory=list, description="Subcellular locations"
    )
    go_terms: list[dict[str, str]] = Field(
        default_factory=list, description="GO annotations"
    )
    keywords: list[str] = Field(default_factory=list, description="UniProt keywords")
    sequence_length: int | None = Field(default=None, description="Sequence length")
    mass: int | None = Field(default=None, description="Molecular mass in Da")


class UniProtClient:
    """Client for UniProt REST API.

    Provides methods for searching proteins, looking up gene information,
    and batch operations.

    Example:
        ```python
        client = UniProtClient()
        protein = await client.get_protein("P53_HUMAN")
        info = await client.get_gene_protein_info("TP53", organism="human")
        ```
    """

    BASE_URL = "https://rest.uniprot.org"

    def __init__(self, rate_limit: int = 10):
        """Initialize UniProt client.

        Args:
            rate_limit: Maximum requests per second (default: 10)
        """
        self.rate_limit = rate_limit
        self._last_request_time = 0.0
        self._min_interval = 1.0 / rate_limit

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _make_request(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> requests.Response:
        """Make rate-limited request to UniProt API.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            Response object
        """
        self._rate_limit()

        url = f"{self.BASE_URL}/{endpoint}"
        headers = {"Accept": "application/json"}

        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        return response

    def get_protein(self, uniprot_id: str) -> ProteinInfo | None:
        """Get protein information by UniProt ID.

        Args:
            uniprot_id: UniProt accession (e.g., 'P04637') or entry name (e.g., 'P53_HUMAN')

        Returns:
            ProteinInfo or None if not found
        """
        try:
            response = self._make_request(f"uniprotkb/{uniprot_id}")
            data = response.json()

            return self._parse_protein_entry(data)

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def search(
        self,
        query: str,
        organism: str | None = None,
        limit: int = 10,
    ) -> list[ProteinInfo]:
        """Search UniProt for proteins.

        Args:
            query: Search query (gene name, protein name, keyword, etc.)
            organism: Filter by organism (e.g., 'human', 'Homo sapiens', '9606')
            limit: Maximum results

        Returns:
            List of ProteinInfo objects
        """
        # Build query
        search_query = query
        if organism:
            # Handle common names
            organism_map = {
                "human": "Homo sapiens",
                "mouse": "Mus musculus",
                "rat": "Rattus norvegicus",
                "yeast": "Saccharomyces cerevisiae",
            }
            org_name = organism_map.get(organism.lower(), organism)
            search_query = f"({query}) AND (organism_name:{org_name})"

        params = {
            "query": search_query,
            "format": "json",
            "size": limit,
        }

        try:
            response = self._make_request("uniprotkb/search", params)
            data = response.json()

            results = []
            for entry in data.get("results", []):
                protein = self._parse_protein_entry(entry)
                if protein:
                    results.append(protein)

            return results

        except Exception as e:
            logger.error(f"UniProt search failed: {e}")
            return []

    def get_gene_protein_info(
        self, gene_symbol: str, organism: str = "human"
    ) -> ProteinInfo | None:
        """Get protein info for a gene symbol.

        Args:
            gene_symbol: Gene symbol (e.g., 'TP53', 'BRCA1')
            organism: Organism name (default: 'human')

        Returns:
            ProteinInfo or None if not found
        """
        # Search for the gene in the specified organism
        # Use gene_exact for precise matching
        organism_map = {
            "human": "Homo sapiens",
            "mouse": "Mus musculus",
            "rat": "Rattus norvegicus",
        }
        org_name = organism_map.get(organism.lower(), organism)

        query = f"(gene_exact:{gene_symbol}) AND (organism_name:{org_name}) AND (reviewed:true)"

        params = {
            "query": query,
            "format": "json",
            "size": 1,
        }

        try:
            response = self._make_request("uniprotkb/search", params)
            data = response.json()

            results = data.get("results", [])
            if results:
                return self._parse_protein_entry(results[0])

            # Try without reviewed filter if no results
            query = f"(gene_exact:{gene_symbol}) AND (organism_name:{org_name})"
            params["query"] = query
            response = self._make_request("uniprotkb/search", params)
            data = response.json()

            results = data.get("results", [])
            if results:
                return self._parse_protein_entry(results[0])

            return None

        except Exception as e:
            logger.error(f"Failed to get protein info for {gene_symbol}: {e}")
            return None

    def batch_lookup(
        self, gene_symbols: list[str], organism: str = "human"
    ) -> dict[str, ProteinInfo | None]:
        """Batch lookup protein info for multiple gene symbols.

        Args:
            gene_symbols: List of gene symbols
            organism: Organism name

        Returns:
            Dict mapping gene symbols to ProteinInfo (or None if not found)
        """
        results = {}

        # UniProt doesn't have a true batch API, so we do sequential lookups
        # with rate limiting
        for gene in gene_symbols:
            results[gene] = self.get_gene_protein_info(gene, organism)

        return results

    def get_function(self, uniprot_id: str) -> dict[str, Any]:
        """Get function annotation for a protein.

        Args:
            uniprot_id: UniProt accession

        Returns:
            Dict with function information
        """
        protein = self.get_protein(uniprot_id)
        if not protein:
            return {"error": f"Protein {uniprot_id} not found"}

        return {
            "uniprot_id": protein.uniprot_id,
            "protein_name": protein.protein_name,
            "function": protein.function,
            "subcellular_location": protein.subcellular_location,
            "go_terms": protein.go_terms,
            "keywords": protein.keywords,
        }

    def _parse_protein_entry(self, entry: dict[str, Any]) -> ProteinInfo | None:
        """Parse a UniProt JSON entry into ProteinInfo.

        Args:
            entry: UniProt JSON entry

        Returns:
            ProteinInfo or None if parsing fails
        """
        try:
            # Extract UniProt ID
            uniprot_id = entry.get("primaryAccession", "")

            # Extract entry name
            entry_name = entry.get("uniProtkbId", "")

            # Extract protein name
            protein_name = ""
            protein_desc = entry.get("proteinDescription", {})
            rec_name = protein_desc.get("recommendedName", {})
            if rec_name:
                full_name = rec_name.get("fullName", {})
                protein_name = full_name.get("value", "")

            # Extract gene names
            gene_names = []
            for gene in entry.get("genes", []):
                if "geneName" in gene:
                    gene_names.append(gene["geneName"].get("value", ""))
                for syn in gene.get("synonyms", []):
                    gene_names.append(syn.get("value", ""))

            # Extract organism
            organism = ""
            organism_id = None
            org_data = entry.get("organism", {})
            organism = org_data.get("scientificName", "")
            organism_id = org_data.get("taxonId")

            # Extract function from comments
            function = ""
            subcellular_location = []
            for comment in entry.get("comments", []):
                comment_type = comment.get("commentType", "")
                if comment_type == "FUNCTION":
                    texts = comment.get("texts", [])
                    if texts:
                        function = texts[0].get("value", "")
                elif comment_type == "SUBCELLULAR LOCATION":
                    locs = comment.get("subcellularLocations", [])
                    for loc in locs:
                        location = loc.get("location", {})
                        if location:
                            subcellular_location.append(location.get("value", ""))

            # Extract GO terms
            go_terms = []
            for xref in entry.get("uniProtKBCrossReferences", []):
                if xref.get("database") == "GO":
                    go_id = xref.get("id", "")
                    props = {p["key"]: p["value"] for p in xref.get("properties", [])}
                    go_terms.append(
                        {
                            "id": go_id,
                            "term": props.get("GoTerm", ""),
                            "evidence": props.get("GoEvidenceType", ""),
                        }
                    )

            # Extract keywords
            keywords = [kw.get("name", "") for kw in entry.get("keywords", [])]

            # Extract sequence info
            sequence = entry.get("sequence", {})
            sequence_length = sequence.get("length")
            mass = sequence.get("molWeight")

            return ProteinInfo(
                uniprot_id=uniprot_id,
                entry_name=entry_name,
                protein_name=protein_name,
                gene_names=gene_names,
                organism=organism,
                organism_id=organism_id,
                function=function,
                subcellular_location=subcellular_location,
                go_terms=go_terms,
                keywords=keywords,
                sequence_length=sequence_length,
                mass=mass,
            )

        except Exception as e:
            logger.error(f"Failed to parse UniProt entry: {e}")
            return None
