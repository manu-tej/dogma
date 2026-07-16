"""
Reactome tools for LLM interpretation.

These tools provide LLM-callable interfaces for Reactome pathway
information and enrichment analysis.
"""

import logging
from typing import Any

from quration.data_sources.reactome import ReactomeClient
from quration.interpretation.tools.base import (
    BioinformaticsTool,
    ToolDefinition,
    ToolError,
)

logger = logging.getLogger(__name__)


class GetReactomePathwayTool(BioinformaticsTool):
    """Tool for getting Reactome pathway information."""

    def __init__(self, client: ReactomeClient | None = None):
        """Initialize the tool.

        Args:
            client: ReactomeClient instance, creates one if not provided
        """
        self._client = client or ReactomeClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_reactome_pathway",
            description=(
                "Get detailed information about a Reactome pathway. "
                "Returns pathway name, summary, and species. "
                "Reactome provides curated biological pathway data."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "pathway_id": {
                        "type": "string",
                        "description": (
                            "Reactome stable ID (e.g., 'R-HSA-109582' for hemostasis, "
                            "'R-HSA-1640170' for cell cycle)"
                        ),
                    },
                },
                "required": ["pathway_id"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "found": {"type": "boolean"},
                    "pathway_id": {"type": "string"},
                    "name": {"type": "string"},
                    "summary": {"type": "string"},
                    "species": {"type": "string"},
                    "diagram_url": {"type": "string"},
                },
            },
            category="pathway",
            rate_limit=10,
            cacheable=True,
            cache_ttl_seconds=86400,
        )

    async def execute(self, pathway_id: str) -> dict[str, Any]:
        """Get pathway information.

        Args:
            pathway_id: Reactome stable ID

        Returns:
            dict with pathway information
        """
        try:
            pathway = self._client.get_pathway(pathway_id)

            if pathway:
                return {
                    "found": True,
                    "pathway_id": pathway.stable_id,
                    "name": pathway.name,
                    "summary": pathway.summary,
                    "species": pathway.species,
                    "diagram_url": self._client.get_pathway_diagram_url(pathway_id),
                    "has_diagram": pathway.diagram_available,
                }
            else:
                return {
                    "found": False,
                    "pathway_id": pathway_id,
                    "message": f"Pathway {pathway_id} not found",
                }

        except Exception as e:
            raise ToolError(f"Failed to get pathway {pathway_id}: {e}") from e


class AnalyzePathwayEnrichmentTool(BioinformaticsTool):
    """Tool for pathway enrichment analysis using Reactome."""

    def __init__(self, client: ReactomeClient | None = None):
        """Initialize the tool.

        Args:
            client: ReactomeClient instance, creates one if not provided
        """
        self._client = client or ReactomeClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="analyze_pathway_enrichment",
            description=(
                "Perform pathway enrichment analysis on a gene list using Reactome. "
                "Returns significantly enriched pathways with p-values and FDR. "
                "Use this for functional enrichment of DEG results."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "gene_list": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of gene symbols for enrichment analysis",
                        "maxItems": 500,
                    },
                    "species": {
                        "type": "string",
                        "description": "Species name",
                        "default": "human",
                        "enum": ["human", "mouse", "rat"],
                    },
                    "p_value_cutoff": {
                        "type": "number",
                        "description": "P-value cutoff for significance",
                        "default": 0.05,
                    },
                },
                "required": ["gene_list"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "pathways": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "pathway_id": {"type": "string"},
                                "name": {"type": "string"},
                                "p_value": {"type": "number"},
                                "fdr": {"type": "number"},
                                "genes_found": {"type": "integer"},
                            },
                        },
                    },
                    "total_significant": {"type": "integer"},
                    "genes_analyzed": {"type": "integer"},
                },
            },
            category="pathway",
            rate_limit=5,  # Lower rate for analysis requests
            cacheable=True,
            cache_ttl_seconds=3600,
        )

    async def execute(
        self,
        gene_list: list[str],
        species: str = "human",
        p_value_cutoff: float = 0.05,
    ) -> dict[str, Any]:
        """Perform pathway enrichment analysis.

        Args:
            gene_list: List of gene symbols
            species: Species name
            p_value_cutoff: P-value cutoff

        Returns:
            dict with enrichment results
        """
        try:
            results = self._client.analyze_genes(gene_list, species)

            # Filter by p-value
            significant = [r for r in results if r.p_value <= p_value_cutoff]

            return {
                "pathways": [
                    {
                        "pathway_id": r.pathway_id,
                        "name": r.pathway_name,
                        "p_value": r.p_value,
                        "fdr": r.fdr,
                        "genes_found": r.entities_found,
                        "genes_total": r.entities_total,
                        "ratio": r.entities_ratio,
                        "diagram_url": self._client.get_pathway_diagram_url(
                            r.pathway_id
                        ),
                    }
                    for r in significant[:30]  # Top 30 pathways
                ],
                "total_significant": len(significant),
                "total_pathways_tested": len(results),
                "genes_analyzed": len(gene_list),
                "p_value_cutoff": p_value_cutoff,
            }

        except Exception as e:
            raise ToolError(f"Enrichment analysis failed: {e}") from e


class SearchReactomePathwaysTool(BioinformaticsTool):
    """Tool for searching Reactome pathways."""

    def __init__(self, client: ReactomeClient | None = None):
        """Initialize the tool.

        Args:
            client: ReactomeClient instance, creates one if not provided
        """
        self._client = client or ReactomeClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_reactome_pathways",
            description=(
                "Search Reactome for pathways matching a query. "
                "Use this to find Reactome pathway IDs for a biological process."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for pathway names",
                    },
                    "species": {
                        "type": "string",
                        "description": "Species name",
                        "default": "human",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results",
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
                    "pathways": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "pathway_id": {"type": "string"},
                                "name": {"type": "string"},
                                "diagram_url": {"type": "string"},
                            },
                        },
                    },
                    "total_found": {"type": "integer"},
                },
            },
            category="pathway",
            rate_limit=10,
            cacheable=True,
            cache_ttl_seconds=3600,
        )

    async def execute(
        self, query: str, species: str = "human", max_results: int = 10
    ) -> dict[str, Any]:
        """Search for pathways.

        Args:
            query: Search query
            species: Species name
            max_results: Maximum results

        Returns:
            dict with search results
        """
        try:
            pathways = self._client.search_pathways(query, species, max_results)

            return {
                "pathways": [
                    {
                        "pathway_id": p.stable_id,
                        "name": p.name,
                        "species": p.species,
                        "diagram_url": self._client.get_pathway_diagram_url(p.stable_id),
                    }
                    for p in pathways
                ],
                "total_found": len(pathways),
            }

        except Exception as e:
            raise ToolError(f"Pathway search failed: {e}") from e


class GetPathwayDiagramURLTool(BioinformaticsTool):
    """Tool for getting Reactome pathway diagram URL."""

    def __init__(self, client: ReactomeClient | None = None):
        """Initialize the tool.

        Args:
            client: ReactomeClient instance, creates one if not provided
        """
        self._client = client or ReactomeClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_pathway_diagram_url",
            description=(
                "Get the URL for a Reactome pathway diagram. "
                "Use this to provide a link to the interactive pathway visualization."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "pathway_id": {
                        "type": "string",
                        "description": "Reactome stable ID",
                    },
                },
                "required": ["pathway_id"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "pathway_id": {"type": "string"},
                    "diagram_url": {"type": "string"},
                },
            },
            category="pathway",
            rate_limit=100,  # No API call needed
            cacheable=True,
            cache_ttl_seconds=86400 * 7,  # 1 week
        )

    async def execute(self, pathway_id: str) -> dict[str, Any]:
        """Get pathway diagram URL.

        Args:
            pathway_id: Reactome stable ID

        Returns:
            dict with URL
        """
        return {
            "pathway_id": pathway_id,
            "diagram_url": self._client.get_pathway_diagram_url(pathway_id),
        }


# Factory function
def create_reactome_tools(
    client: ReactomeClient | None = None,
) -> list[BioinformaticsTool]:
    """Create all Reactome tools with a shared client.

    Args:
        client: Optional ReactomeClient instance to share

    Returns:
        list of BioinformaticsTool instances
    """
    if client is None:
        client = ReactomeClient()

    return [
        GetReactomePathwayTool(client),
        AnalyzePathwayEnrichmentTool(client),
        SearchReactomePathwaysTool(client),
        GetPathwayDiagramURLTool(client),
    ]
