"""
STRING tools for LLM interpretation.

These tools provide LLM-callable interfaces for STRING protein-protein
interaction database queries including network analysis, interaction
partners, and functional enrichment.
"""

import logging
from typing import Any

from quration.data_sources.string_db import STRINGClient
from quration.interpretation.tools.base import (
    BioinformaticsTool,
    ToolDefinition,
    ToolError,
)

logger = logging.getLogger(__name__)


class GetProteinInteractionsTool(BioinformaticsTool):
    """Tool for getting protein-protein interactions."""

    def __init__(self, client: STRINGClient | None = None):
        """Initialize the tool.

        Args:
            client: STRINGClient instance, creates one if not provided
        """
        self._client = client or STRINGClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_protein_interactions",
            description=(
                "Get protein-protein interactions from STRING database for a set of "
                "proteins/genes. Returns interaction partners and confidence scores. "
                "Use this to understand how genes in a DEG list might interact."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "proteins": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of protein or gene names",
                        "maxItems": 100,
                    },
                    "species": {
                        "type": "string",
                        "description": "Species name",
                        "default": "human",
                        "enum": ["human", "mouse", "rat", "yeast", "drosophila", "zebrafish"],
                    },
                    "min_score": {
                        "type": "integer",
                        "description": (
                            "Minimum interaction score (0-1000). "
                            "400 = medium confidence, 700 = high, 900 = highest"
                        ),
                        "default": 400,
                        "minimum": 0,
                        "maximum": 1000,
                    },
                },
                "required": ["proteins"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "interactions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "gene_a": {"type": "string"},
                                "gene_b": {"type": "string"},
                                "score": {"type": "integer"},
                            },
                        },
                    },
                    "total_interactions": {"type": "integer"},
                    "network_image_url": {"type": "string"},
                },
            },
            category="interaction",
            rate_limit=1,  # STRING recommends slow requests
            cacheable=True,
            cache_ttl_seconds=86400,
            examples=[
                {
                    "input": {"proteins": ["TP53", "MDM2", "CDKN1A"]},
                    "output": {
                        "interactions": [
                            {"gene_a": "TP53", "gene_b": "MDM2", "score": 999}
                        ],
                        "total_interactions": 3,
                    },
                }
            ],
        )

    async def execute(
        self,
        proteins: list[str],
        species: str = "human",
        min_score: int = 400,
    ) -> dict[str, Any]:
        """Get protein interactions.

        Args:
            proteins: List of proteins
            species: Species name
            min_score: Minimum interaction score

        Returns:
            dict with interaction data
        """
        try:
            interactions = self._client.get_interactions(
                proteins, species=species, required_score=min_score
            )

            return {
                "proteins_queried": proteins,
                "species": species,
                "min_score": min_score,
                "interactions": [
                    {
                        "gene_a": i.gene_a,
                        "gene_b": i.gene_b,
                        "score": i.combined_score,
                        "experimental_score": int(i.escore * 1000),
                        "database_score": int(i.dscore * 1000),
                        "textmining_score": int(i.tscore * 1000),
                    }
                    for i in interactions
                ],
                "total_interactions": len(interactions),
                "network_image_url": self._client.get_network_image_url(
                    proteins, species=species, required_score=min_score
                ),
            }

        except Exception as e:
            raise ToolError(f"Failed to get protein interactions: {e}") from e


class GetInteractionPartnersTool(BioinformaticsTool):
    """Tool for getting interaction partners of a single protein."""

    def __init__(self, client: STRINGClient | None = None):
        """Initialize the tool.

        Args:
            client: STRINGClient instance, creates one if not provided
        """
        self._client = client or STRINGClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_interaction_partners",
            description=(
                "Get interaction partners for a single protein/gene from STRING. "
                "Returns the top interacting proteins with confidence scores. "
                "Use this to find what proteins interact with a gene of interest."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "protein": {
                        "type": "string",
                        "description": "Protein or gene name",
                    },
                    "species": {
                        "type": "string",
                        "description": "Species name",
                        "default": "human",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of partners to return",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                    },
                    "min_score": {
                        "type": "integer",
                        "description": "Minimum interaction score (0-1000)",
                        "default": 400,
                    },
                },
                "required": ["protein"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "protein": {"type": "string"},
                    "partners": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "gene_name": {"type": "string"},
                                "score": {"type": "integer"},
                                "annotation": {"type": "string"},
                            },
                        },
                    },
                    "total_partners": {"type": "integer"},
                },
            },
            category="interaction",
            rate_limit=1,
            cacheable=True,
            cache_ttl_seconds=86400,
        )

    async def execute(
        self,
        protein: str,
        species: str = "human",
        limit: int = 10,
        min_score: int = 400,
    ) -> dict[str, Any]:
        """Get interaction partners.

        Args:
            protein: Protein name
            species: Species name
            limit: Maximum partners
            min_score: Minimum score

        Returns:
            dict with partner data
        """
        try:
            partners = self._client.get_interaction_partners(
                protein, species=species, limit=limit, required_score=min_score
            )

            return {
                "protein": protein,
                "species": species,
                "partners": [
                    {
                        "gene_name": p.gene_name,
                        "score": p.score,
                        "annotation": p.annotation[:200] if p.annotation else "",
                    }
                    for p in partners
                ],
                "total_partners": len(partners),
            }

        except Exception as e:
            raise ToolError(f"Failed to get partners for {protein}: {e}") from e


class GetSTRINGEnrichmentTool(BioinformaticsTool):
    """Tool for STRING functional enrichment analysis."""

    def __init__(self, client: STRINGClient | None = None):
        """Initialize the tool.

        Args:
            client: STRINGClient instance, creates one if not provided
        """
        self._client = client or STRINGClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_string_enrichment",
            description=(
                "Perform functional enrichment analysis on a protein/gene set using STRING. "
                "Returns enriched GO terms, KEGG pathways, and other annotations. "
                "Use this for quick functional characterization of DEG lists."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "proteins": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of protein or gene names",
                        "maxItems": 500,
                    },
                    "species": {
                        "type": "string",
                        "description": "Species name",
                        "default": "human",
                    },
                },
                "required": ["proteins"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "enrichment_results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "category": {"type": "string"},
                                "term": {"type": "string"},
                                "description": {"type": "string"},
                                "p_value": {"type": "number"},
                                "fdr": {"type": "number"},
                            },
                        },
                    },
                    "total_enriched": {"type": "integer"},
                },
            },
            category="enrichment",
            rate_limit=1,
            cacheable=True,
            cache_ttl_seconds=3600,
        )

    async def execute(
        self, proteins: list[str], species: str = "human"
    ) -> dict[str, Any]:
        """Perform enrichment analysis.

        Args:
            proteins: List of proteins
            species: Species name

        Returns:
            dict with enrichment results
        """
        try:
            results = self._client.get_enrichment(proteins, species=species)

            # Filter significant results and limit output
            significant = [r for r in results if r.fdr < 0.05]

            # Group by category
            by_category: dict[str, list] = {}
            for r in significant:
                cat = r.category
                if cat not in by_category:
                    by_category[cat] = []
                if len(by_category[cat]) < 5:  # Top 5 per category
                    by_category[cat].append(
                        {
                            "term": r.term,
                            "description": r.description,
                            "p_value": r.p_value,
                            "fdr": r.fdr,
                            "gene_count": r.gene_count,
                        }
                    )

            return {
                "proteins_analyzed": len(proteins),
                "species": species,
                "enrichment_by_category": by_category,
                "total_significant": len(significant),
                "categories_found": list(by_category.keys()),
            }

        except Exception as e:
            raise ToolError(f"STRING enrichment failed: {e}") from e


class GetNetworkStatsTool(BioinformaticsTool):
    """Tool for getting PPI network statistics."""

    def __init__(self, client: STRINGClient | None = None):
        """Initialize the tool.

        Args:
            client: STRINGClient instance, creates one if not provided
        """
        self._client = client or STRINGClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_network_stats",
            description=(
                "Check if a gene set has significantly more protein interactions "
                "than expected by chance. Tests for PPI enrichment. "
                "Use this to determine if DEG list forms a connected network."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "proteins": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of protein or gene names",
                        "maxItems": 500,
                    },
                    "species": {
                        "type": "string",
                        "description": "Species name",
                        "default": "human",
                    },
                },
                "required": ["proteins"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "is_significantly_connected": {"type": "boolean"},
                    "p_value": {"type": "number"},
                    "number_of_edges": {"type": "integer"},
                    "expected_edges": {"type": "number"},
                    "average_node_degree": {"type": "number"},
                },
            },
            category="interaction",
            rate_limit=1,
            cacheable=True,
            cache_ttl_seconds=3600,
        )

    async def execute(
        self, proteins: list[str], species: str = "human"
    ) -> dict[str, Any]:
        """Get network statistics.

        Args:
            proteins: List of proteins
            species: Species name

        Returns:
            dict with network stats
        """
        try:
            stats = self._client.get_ppi_enrichment(proteins, species=species)

            return {
                "proteins_analyzed": len(proteins),
                "species": species,
                "is_significantly_connected": stats.get("enriched", False),
                "p_value": stats.get("p_value", 1.0),
                "number_of_edges": stats.get("number_of_edges", 0),
                "expected_edges": stats.get("expected_edges", 0),
                "average_node_degree": stats.get("average_node_degree", 0.0),
                "clustering_coefficient": stats.get("local_clustering_coefficient", 0.0),
                "interpretation": (
                    "This gene set shows significantly more interactions than expected, "
                    "suggesting biological connectivity."
                    if stats.get("enriched", False)
                    else "This gene set does not show significant PPI enrichment."
                ),
            }

        except Exception as e:
            raise ToolError(f"Network statistics failed: {e}") from e


class GetNetworkImageURLTool(BioinformaticsTool):
    """Tool for getting STRING network visualization URL."""

    def __init__(self, client: STRINGClient | None = None):
        """Initialize the tool.

        Args:
            client: STRINGClient instance, creates one if not provided
        """
        self._client = client or STRINGClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_network_image_url",
            description=(
                "Get a URL for a STRING network visualization image. "
                "Returns a PNG image URL showing protein interactions. "
                "Use this to provide visual network representation to users."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "proteins": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of protein or gene names",
                        "maxItems": 50,
                    },
                    "species": {
                        "type": "string",
                        "description": "Species name",
                        "default": "human",
                    },
                    "min_score": {
                        "type": "integer",
                        "description": "Minimum interaction score",
                        "default": 400,
                    },
                    "network_flavor": {
                        "type": "string",
                        "description": "Network visualization type",
                        "default": "confidence",
                        "enum": ["confidence", "evidence", "actions"],
                    },
                },
                "required": ["proteins"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "image_url": {"type": "string"},
                    "proteins": {"type": "array"},
                },
            },
            category="interaction",
            rate_limit=100,  # No API call needed
            cacheable=True,
            cache_ttl_seconds=86400 * 7,
        )

    async def execute(
        self,
        proteins: list[str],
        species: str = "human",
        min_score: int = 400,
        network_flavor: str = "confidence",
    ) -> dict[str, Any]:
        """Get network image URL.

        Args:
            proteins: List of proteins
            species: Species name
            min_score: Minimum score
            network_flavor: Visualization type

        Returns:
            dict with image URL
        """
        url = self._client.get_network_image_url(
            proteins,
            species=species,
            required_score=min_score,
            network_flavor=network_flavor,
        )

        return {
            "proteins": proteins,
            "species": species,
            "min_score": min_score,
            "network_flavor": network_flavor,
            "image_url": url,
            "note": "This URL returns a PNG image of the protein interaction network",
        }


# Factory function
def create_string_tools(
    client: STRINGClient | None = None,
) -> list[BioinformaticsTool]:
    """Create all STRING tools with a shared client.

    Args:
        client: Optional STRINGClient instance to share

    Returns:
        list of BioinformaticsTool instances
    """
    if client is None:
        client = STRINGClient()

    return [
        GetProteinInteractionsTool(client),
        GetInteractionPartnersTool(client),
        GetSTRINGEnrichmentTool(client),
        GetNetworkStatsTool(client),
        GetNetworkImageURLTool(client),
    ]
