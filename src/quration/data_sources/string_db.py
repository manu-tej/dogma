"""
STRING database API client for protein-protein interactions.

This module provides a client for accessing STRING-db protein interaction
data including interaction networks, enrichment analysis, and network images.

API Documentation: https://string-db.org/cgi/help?subpage=api
"""

import logging
import time
from typing import Any

import requests
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class ProteinInteraction(BaseModel):
    """Protein-protein interaction from STRING."""

    protein_a: str = Field(description="First protein identifier")
    protein_b: str = Field(description="Second protein identifier")
    gene_a: str = Field(default="", description="Gene name for protein A")
    gene_b: str = Field(default="", description="Gene name for protein B")
    combined_score: int = Field(description="Combined confidence score (0-1000)")
    nscore: float = Field(default=0.0, description="Neighborhood score")
    fscore: float = Field(default=0.0, description="Fusion score")
    pscore: float = Field(default=0.0, description="Phylogenetic profile score")
    ascore: float = Field(default=0.0, description="Co-expression score")
    escore: float = Field(default=0.0, description="Experimental score")
    dscore: float = Field(default=0.0, description="Database score")
    tscore: float = Field(default=0.0, description="Text-mining score")


class InteractionPartner(BaseModel):
    """Interaction partner for a protein."""

    protein_id: str = Field(description="STRING protein ID")
    gene_name: str = Field(default="", description="Gene name")
    annotation: str = Field(default="", description="Protein annotation")
    score: int = Field(default=0, description="Interaction score (0-1000)")


class FunctionalEnrichment(BaseModel):
    """Functional enrichment result from STRING."""

    category: str = Field(description="Enrichment category (GO, KEGG, etc.)")
    term: str = Field(description="Term ID")
    description: str = Field(default="", description="Term description")
    p_value: float = Field(description="P-value")
    fdr: float = Field(default=1.0, description="False discovery rate")
    gene_count: int = Field(default=0, description="Number of genes in term")
    genes: list[str] = Field(default_factory=list, description="Gene list")


class STRINGClient:
    """Client for STRING-db API.

    Provides methods for querying protein-protein interactions,
    functional enrichment, and network visualization.

    Example:
        ```python
        client = STRINGClient()
        interactions = client.get_interactions(["TP53", "MDM2", "CDKN1A"])
        enrichment = client.get_enrichment(["TP53", "BRCA1", "ATM"])
        ```
    """

    BASE_URL = "https://string-db.org/api"

    # Species taxonomy IDs
    SPECIES_MAP = {
        "human": 9606,
        "homo sapiens": 9606,
        "mouse": 10090,
        "mus musculus": 10090,
        "rat": 10116,
        "rattus norvegicus": 10116,
        "yeast": 4932,
        "saccharomyces cerevisiae": 4932,
        "drosophila": 7227,
        "drosophila melanogaster": 7227,
        "zebrafish": 7955,
        "danio rerio": 7955,
    }

    def __init__(self, rate_limit: int = 1):
        """Initialize STRING client.

        Args:
            rate_limit: Maximum requests per second (default: 1, STRING recommends slow requests)
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

    def _get_species_id(self, species: str) -> int:
        """Get taxonomy ID for species.

        Args:
            species: Species name or common name

        Returns:
            NCBI Taxonomy ID
        """
        return self.SPECIES_MAP.get(species.lower(), 9606)  # Default to human

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _make_request(
        self,
        endpoint: str,
        params: dict[str, Any],
        method: str = "GET",
    ) -> requests.Response:
        """Make rate-limited request to STRING API.

        Args:
            endpoint: API endpoint
            params: Query parameters
            method: HTTP method

        Returns:
            Response object
        """
        self._rate_limit()

        url = f"{self.BASE_URL}/{endpoint}"

        if method == "GET":
            response = requests.get(url, params=params, timeout=60)
        elif method == "POST":
            response = requests.post(url, data=params, timeout=60)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        response.raise_for_status()
        return response

    def get_interactions(
        self,
        proteins: list[str],
        species: str = "human",
        required_score: int = 400,
        network_type: str = "functional",
    ) -> list[ProteinInteraction]:
        """Get protein-protein interactions.

        Args:
            proteins: List of protein/gene names
            species: Species name
            required_score: Minimum interaction score (0-1000)
            network_type: 'functional' or 'physical'

        Returns:
            List of ProteinInteraction
        """
        if not proteins:
            return []

        species_id = self._get_species_id(species)

        try:
            params = {
                "identifiers": "%0d".join(proteins),  # Newline-separated
                "species": species_id,
                "required_score": required_score,
                "network_type": network_type,
                "caller_identity": "quration_bioinformatics",
            }

            response = self._make_request("json/network", params, method="POST")
            data = response.json()

            interactions = []
            for item in data:
                interactions.append(
                    ProteinInteraction(
                        protein_a=item.get("stringId_A", ""),
                        protein_b=item.get("stringId_B", ""),
                        gene_a=item.get("preferredName_A", ""),
                        gene_b=item.get("preferredName_B", ""),
                        combined_score=int(item.get("score", 0) * 1000),
                        nscore=item.get("nscore", 0.0),
                        fscore=item.get("fscore", 0.0),
                        pscore=item.get("pscore", 0.0),
                        ascore=item.get("ascore", 0.0),
                        escore=item.get("escore", 0.0),
                        dscore=item.get("dscore", 0.0),
                        tscore=item.get("tscore", 0.0),
                    )
                )

            return interactions

        except Exception as e:
            logger.error(f"Failed to get interactions: {e}")
            return []

    def get_interaction_partners(
        self,
        protein: str,
        species: str = "human",
        limit: int = 10,
        required_score: int = 400,
    ) -> list[InteractionPartner]:
        """Get interaction partners for a protein.

        Args:
            protein: Protein/gene name
            species: Species name
            limit: Maximum partners to return
            required_score: Minimum interaction score

        Returns:
            List of InteractionPartner
        """
        species_id = self._get_species_id(species)

        try:
            params = {
                "identifiers": protein,
                "species": species_id,
                "limit": limit,
                "required_score": required_score,
                "caller_identity": "quration_bioinformatics",
            }

            response = self._make_request(
                "json/interaction_partners", params, method="POST"
            )
            data = response.json()

            partners = []
            for item in data:
                partners.append(
                    InteractionPartner(
                        protein_id=item.get("stringId_B", ""),
                        gene_name=item.get("preferredName_B", ""),
                        annotation=item.get("annotation_B", ""),
                        score=int(item.get("score", 0) * 1000),
                    )
                )

            return partners

        except Exception as e:
            logger.error(f"Failed to get interaction partners for {protein}: {e}")
            return []

    def get_enrichment(
        self,
        proteins: list[str],
        species: str = "human",
    ) -> list[FunctionalEnrichment]:
        """Get functional enrichment for a protein set.

        Args:
            proteins: List of protein/gene names
            species: Species name

        Returns:
            List of FunctionalEnrichment
        """
        if not proteins:
            return []

        species_id = self._get_species_id(species)

        try:
            params = {
                "identifiers": "%0d".join(proteins),
                "species": species_id,
                "caller_identity": "quration_bioinformatics",
            }

            response = self._make_request("json/enrichment", params, method="POST")
            data = response.json()

            results = []
            for item in data:
                # inputGenes can be a list (JSON array) or a string (comma-separated)
                input_genes = item.get("inputGenes", [])
                if isinstance(input_genes, list):
                    genes = input_genes
                elif isinstance(input_genes, str):
                    genes = input_genes.split(",") if input_genes else []
                else:
                    genes = []
                results.append(
                    FunctionalEnrichment(
                        category=item.get("category", ""),
                        term=item.get("term", ""),
                        description=item.get("description", ""),
                        p_value=item.get("p_value", 1.0),
                        fdr=item.get("fdr", 1.0),
                        gene_count=item.get("number_of_genes", 0),
                        genes=genes,
                    )
                )

            return results

        except Exception as e:
            logger.error(f"Failed to get enrichment: {e}")
            return []

    def get_network_image_url(
        self,
        proteins: list[str],
        species: str = "human",
        required_score: int = 400,
        network_flavor: str = "confidence",
    ) -> str:
        """Get URL for network visualization image.

        Args:
            proteins: List of protein/gene names
            species: Species name
            required_score: Minimum interaction score
            network_flavor: 'confidence', 'evidence', or 'actions'

        Returns:
            URL to network image (PNG)
        """
        species_id = self._get_species_id(species)
        identifiers = "%0d".join(proteins)

        return (
            f"{self.BASE_URL}/image/network"
            f"?identifiers={identifiers}"
            f"&species={species_id}"
            f"&required_score={required_score}"
            f"&network_flavor={network_flavor}"
            f"&caller_identity=quration_bioinformatics"
        )

    def resolve_proteins(
        self,
        identifiers: list[str],
        species: str = "human",
    ) -> dict[str, str]:
        """Resolve protein identifiers to STRING IDs.

        Args:
            identifiers: List of protein names/IDs
            species: Species name

        Returns:
            Dict mapping input to STRING ID
        """
        if not identifiers:
            return {}

        species_id = self._get_species_id(species)

        try:
            params = {
                "identifiers": "%0d".join(identifiers),
                "species": species_id,
                "limit": 1,  # Best match only
                "caller_identity": "quration_bioinformatics",
            }

            response = self._make_request("json/get_string_ids", params, method="POST")
            data = response.json()

            result = {}
            for item in data:
                query = item.get("queryItem", "")
                string_id = item.get("stringId", "")
                if query and string_id:
                    result[query] = string_id

            return result

        except Exception as e:
            logger.error(f"Failed to resolve proteins: {e}")
            return {}

    def get_ppi_enrichment(
        self,
        proteins: list[str],
        species: str = "human",
    ) -> dict[str, Any]:
        """Check if protein set has more interactions than expected by chance.

        Args:
            proteins: List of protein/gene names
            species: Species name

        Returns:
            Dict with enrichment statistics
        """
        if not proteins:
            return {"enriched": False}

        species_id = self._get_species_id(species)

        try:
            params = {
                "identifiers": "%0d".join(proteins),
                "species": species_id,
                "caller_identity": "quration_bioinformatics",
            }

            response = self._make_request(
                "json/ppi_enrichment", params, method="POST"
            )
            data = response.json()

            if data:
                item = data[0] if isinstance(data, list) else data
                return {
                    "enriched": item.get("p_value", 1.0) < 0.05,
                    "p_value": item.get("p_value", 1.0),
                    "number_of_edges": item.get("number_of_edges", 0),
                    "expected_edges": item.get("expected_number_of_edges", 0),
                    "average_node_degree": item.get("average_node_degree", 0.0),
                    "local_clustering_coefficient": item.get(
                        "local_clustering_coefficient", 0.0
                    ),
                }

            return {"enriched": False}

        except Exception as e:
            logger.error(f"Failed to get PPI enrichment: {e}")
            return {"enriched": False, "error": str(e)}
