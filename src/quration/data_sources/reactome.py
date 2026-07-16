"""
Reactome Content Service API client for pathway information.

This module provides a client for accessing Reactome pathway data including
pathway details, enrichment analysis, and pathway hierarchy.

API Documentation: https://reactome.org/ContentService/
"""

import logging
import time
from typing import Any

import requests
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class ReactomePathway(BaseModel):
    """Reactome pathway information."""

    stable_id: str = Field(description="Reactome stable ID (e.g., 'R-HSA-109582')")
    name: str = Field(default="", description="Pathway name")
    species: str = Field(default="", description="Species name")
    summary: str = Field(default="", description="Pathway summary/description")
    diagram_available: bool = Field(default=False, description="Whether diagram is available")
    has_ewas: bool = Field(default=False, description="Has EWASs (Ensembl pathways)")


class EnrichmentResult(BaseModel):
    """Pathway enrichment result from Reactome analysis."""

    pathway_id: str = Field(description="Reactome pathway ID")
    pathway_name: str = Field(default="", description="Pathway name")
    entities_found: int = Field(default=0, description="Number of submitted entities found")
    entities_total: int = Field(default=0, description="Total entities in pathway")
    entities_ratio: float = Field(default=0.0, description="Ratio of found/total")
    p_value: float = Field(default=1.0, description="P-value")
    fdr: float = Field(default=1.0, description="False discovery rate")
    species: str = Field(default="", description="Species")


class ReactomeClient:
    """Client for Reactome Content Service API.

    Provides methods for pathway lookup, enrichment analysis, and pathway hierarchy.

    Example:
        ```python
        client = ReactomeClient()
        pathway = client.get_pathway("R-HSA-109582")
        results = client.analyze_genes(["TP53", "BRCA1", "EGFR"])
        ```
    """

    BASE_URL = "https://reactome.org/ContentService"
    ANALYSIS_URL = "https://reactome.org/AnalysisService"

    # Species mapping
    SPECIES_MAP = {
        "human": "Homo sapiens",
        "homo sapiens": "Homo sapiens",
        "mouse": "Mus musculus",
        "mus musculus": "Mus musculus",
        "rat": "Rattus norvegicus",
        "rattus norvegicus": "Rattus norvegicus",
    }

    def __init__(self, rate_limit: int = 10):
        """Initialize Reactome client.

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

    def _get_species_name(self, species: str) -> str:
        """Convert species name to Reactome format.

        Args:
            species: Species name or common name

        Returns:
            Reactome species name
        """
        return self.SPECIES_MAP.get(species.lower(), species)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _make_request(
        self,
        url: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        data: Any = None,
        headers: dict[str, str] | None = None,
    ) -> requests.Response:
        """Make rate-limited request to Reactome API.

        Args:
            url: Full URL
            method: HTTP method
            params: Query parameters
            data: Request body
            headers: HTTP headers

        Returns:
            Response object
        """
        self._rate_limit()

        default_headers = {"Accept": "application/json"}
        if headers:
            default_headers.update(headers)

        if method == "GET":
            response = requests.get(
                url, params=params, headers=default_headers, timeout=30
            )
        elif method == "POST":
            response = requests.post(
                url, params=params, data=data, headers=default_headers, timeout=60
            )
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response

    def get_pathway(self, pathway_id: str) -> ReactomePathway | None:
        """Get pathway information.

        Args:
            pathway_id: Reactome stable ID (e.g., 'R-HSA-109582')

        Returns:
            ReactomePathway or None if not found
        """
        try:
            url = f"{self.BASE_URL}/data/query/{pathway_id}"
            response = self._make_request(url)
            data = response.json()

            return ReactomePathway(
                stable_id=data.get("stId", pathway_id),
                name=data.get("displayName", ""),
                species=data.get("speciesName", ""),
                summary=data.get("summation", [{}])[0].get("text", "")
                if data.get("summation")
                else "",
                diagram_available=data.get("hasDiagram", False),
                has_ewas=data.get("hasEHLD", False),
            )

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception as e:
            logger.error(f"Failed to get pathway {pathway_id}: {e}")
            return None

    def search_pathways(
        self, query: str, species: str = "human", limit: int = 20
    ) -> list[ReactomePathway]:
        """Search for pathways.

        Args:
            query: Search query
            species: Species name
            limit: Maximum results

        Returns:
            List of ReactomePathway
        """
        species_name = self._get_species_name(species)

        try:
            url = f"{self.BASE_URL}/search/query"
            params = {
                "query": query,
                "species": species_name,
                "types": "Pathway",
                "cluster": "true",
            }

            response = self._make_request(url, params=params)
            data = response.json()

            pathways = []
            results = data.get("results", [])

            for result in results[:limit]:
                entries = result.get("entries", [])
                for entry in entries:
                    if entry.get("exactType") == "Pathway":
                        pathways.append(
                            ReactomePathway(
                                stable_id=entry.get("stId", ""),
                                name=entry.get("name", ""),
                                species=species_name,
                            )
                        )
                        if len(pathways) >= limit:
                            break
                if len(pathways) >= limit:
                    break

            return pathways

        except Exception as e:
            logger.error(f"Pathway search failed: {e}")
            return []

    def analyze_genes(
        self,
        genes: list[str],
        species: str = "human",
        include_interactors: bool = False,
    ) -> list[EnrichmentResult]:
        """Perform pathway enrichment analysis on a gene list.

        Args:
            genes: List of gene symbols
            species: Species name
            include_interactors: Include protein interactors

        Returns:
            List of EnrichmentResult sorted by p-value
        """
        if not genes:
            return []

        species_name = self._get_species_name(species)

        try:
            # Submit gene list for analysis
            url = f"{self.ANALYSIS_URL}/identifiers/"
            params = {
                "interactors": str(include_interactors).lower(),
                "species": species_name,
                "sortBy": "ENTITIES_PVALUE",
                "order": "ASC",
                "resource": "TOTAL",
            }

            # Format gene list - one per line
            gene_data = "\n".join(genes)

            headers = {"Content-Type": "text/plain"}
            response = self._make_request(
                url, method="POST", params=params, data=gene_data, headers=headers
            )

            data = response.json()

            results = []
            for pathway in data.get("pathways", []):
                entities = pathway.get("entities", {})
                results.append(
                    EnrichmentResult(
                        pathway_id=pathway.get("stId", ""),
                        pathway_name=pathway.get("name", ""),
                        entities_found=entities.get("found", 0),
                        entities_total=entities.get("total", 0),
                        entities_ratio=entities.get("ratio", 0.0),
                        p_value=entities.get("pValue", 1.0),
                        fdr=entities.get("fdr", 1.0),
                        species=species_name,
                    )
                )

            return results

        except Exception as e:
            logger.error(f"Enrichment analysis failed: {e}")
            return []

    def get_pathway_hierarchy(
        self, pathway_id: str
    ) -> dict[str, Any]:
        """Get pathway hierarchy (ancestors and children).

        Args:
            pathway_id: Reactome stable ID

        Returns:
            Dict with hierarchy information
        """
        try:
            # Get ancestors
            ancestors_url = f"{self.BASE_URL}/data/pathway/{pathway_id}/containedEvents"
            ancestors_response = self._make_request(ancestors_url)
            contained = ancestors_response.json() if ancestors_response.text else []

            # Get the pathway itself for context
            pathway = self.get_pathway(pathway_id)

            return {
                "pathway_id": pathway_id,
                "pathway_name": pathway.name if pathway else "",
                "contained_events": [
                    {
                        "id": event.get("stId", ""),
                        "name": event.get("displayName", ""),
                        "type": event.get("schemaClass", ""),
                    }
                    for event in contained[:50]  # Limit results
                ],
            }

        except Exception as e:
            logger.error(f"Failed to get hierarchy for {pathway_id}: {e}")
            return {"pathway_id": pathway_id, "error": str(e)}

    def get_pathway_diagram_url(self, pathway_id: str) -> str:
        """Get URL for pathway diagram.

        Args:
            pathway_id: Reactome stable ID

        Returns:
            URL to pathway diagram
        """
        return f"https://reactome.org/PathwayBrowser/#/{pathway_id}"

    def get_genes_in_pathway(
        self, pathway_id: str, species: str = "human"
    ) -> list[str]:
        """Get genes participating in a pathway.

        Args:
            pathway_id: Reactome stable ID
            species: Species name

        Returns:
            List of gene symbols
        """
        try:
            url = f"{self.BASE_URL}/data/participants/{pathway_id}"
            response = self._make_request(url)
            data = response.json()

            genes = set()
            for participant in data:
                # Extract gene names from reference entities
                if "refEntities" in participant:
                    for ref in participant["refEntities"]:
                        if ref.get("databaseName") == "UniProt":
                            gene_names = ref.get("geneName", [])
                            if isinstance(gene_names, list):
                                genes.update(gene_names)
                            elif gene_names:
                                genes.add(gene_names)

            return list(genes)

        except Exception as e:
            logger.error(f"Failed to get genes for pathway {pathway_id}: {e}")
            return []
