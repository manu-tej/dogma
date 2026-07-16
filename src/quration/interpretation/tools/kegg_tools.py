"""
KEGG tools for LLM interpretation.

These tools provide LLM-callable interfaces for KEGG pathway
information retrieval and gene-pathway mapping.
"""

import logging
from typing import Any

from quration.data_sources.kegg import KEGGClient
from quration.interpretation.tools.base import (
    BioinformaticsTool,
    ToolDefinition,
    ToolError,
)

logger = logging.getLogger(__name__)


class GetKEGGPathwayTool(BioinformaticsTool):
    """Tool for getting KEGG pathway information."""

    def __init__(self, client: KEGGClient | None = None):
        """Initialize the tool.

        Args:
            client: KEGGClient instance, creates one if not provided
        """
        self._client = client or KEGGClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_kegg_pathway",
            description=(
                "Get detailed information about a KEGG pathway. "
                "Returns pathway name, description, and associated genes. "
                "Use when you have a KEGG pathway ID and need details about it."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "pathway_id": {
                        "type": "string",
                        "description": (
                            "KEGG pathway ID (e.g., 'hsa04110' for cell cycle, "
                            "'hsa05200' for pathways in cancer)"
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
                    "description": {"type": "string"},
                    "organism": {"type": "string"},
                    "gene_count": {"type": "integer"},
                    "url": {"type": "string"},
                },
            },
            category="pathway",
            rate_limit=10,
            cacheable=True,
            cache_ttl_seconds=86400,
            examples=[
                {
                    "input": {"pathway_id": "hsa04110"},
                    "output": {
                        "found": True,
                        "pathway_id": "hsa04110",
                        "name": "Cell cycle - Homo sapiens (human)",
                        "url": "https://www.kegg.jp/pathway/hsa04110",
                    },
                }
            ],
        )

    async def execute(self, pathway_id: str) -> dict[str, Any]:
        """Get pathway information.

        Args:
            pathway_id: KEGG pathway ID

        Returns:
            dict with pathway information
        """
        try:
            pathway = self._client.get_pathway(pathway_id)

            if pathway:
                return {
                    "found": True,
                    "pathway_id": pathway.pathway_id,
                    "name": pathway.name,
                    "description": pathway.description,
                    "organism": pathway.organism,
                    "gene_count": pathway.gene_count,
                    "url": pathway.url,
                }
            else:
                return {
                    "found": False,
                    "pathway_id": pathway_id,
                    "message": f"Pathway {pathway_id} not found",
                }

        except Exception as e:
            raise ToolError(f"Failed to get pathway {pathway_id}: {e}") from e


class SearchPathwaysTool(BioinformaticsTool):
    """Tool for searching KEGG pathways."""

    def __init__(self, client: KEGGClient | None = None):
        """Initialize the tool.

        Args:
            client: KEGGClient instance, creates one if not provided
        """
        self._client = client or KEGGClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_pathways",
            description=(
                "Search KEGG for pathways matching a query. "
                "Use this to find pathways related to a biological process or disease. "
                "Examples: 'apoptosis', 'cancer', 'insulin signaling'"
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for pathway names",
                    },
                    "organism": {
                        "type": "string",
                        "description": "Organism name",
                        "default": "human",
                        "enum": ["human", "mouse", "rat"],
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return",
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
                                "url": {"type": "string"},
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
        self, query: str, organism: str = "human", max_results: int = 10
    ) -> dict[str, Any]:
        """Search for pathways.

        Args:
            query: Search query
            organism: Organism name
            max_results: Maximum results

        Returns:
            dict with search results
        """
        try:
            pathways = self._client.search_pathways(query, organism, max_results)

            return {
                "pathways": [
                    {
                        "pathway_id": p.pathway_id,
                        "name": p.name,
                        "organism": p.organism,
                        "url": p.url,
                    }
                    for p in pathways
                ],
                "total_found": len(pathways),
            }

        except Exception as e:
            raise ToolError(f"Pathway search failed: {e}") from e


class FindPathwaysForGenesTool(BioinformaticsTool):
    """Tool for finding pathways associated with a gene list."""

    def __init__(self, client: KEGGClient | None = None):
        """Initialize the tool.

        Args:
            client: KEGGClient instance, creates one if not provided
        """
        self._client = client or KEGGClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="find_pathways_for_genes",
            description=(
                "Find KEGG pathways associated with a list of genes. "
                "Returns pathways ranked by the number of input genes they contain. "
                "Use this for pathway enrichment analysis of DEG results."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "gene_list": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of gene symbols (max 100)",
                        "maxItems": 100,
                    },
                    "organism": {
                        "type": "string",
                        "description": "Organism name",
                        "default": "human",
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
                                "gene_count": {"type": "integer"},
                                "genes": {"type": "array"},
                                "url": {"type": "string"},
                            },
                        },
                    },
                    "genes_mapped": {"type": "integer"},
                    "genes_not_found": {"type": "array"},
                },
            },
            category="pathway",
            rate_limit=2,  # Lower rate for complex queries
            cacheable=True,
            cache_ttl_seconds=3600,
        )

    async def execute(
        self, gene_list: list[str], organism: str = "human"
    ) -> dict[str, Any]:
        """Find pathways for a gene list.

        Args:
            gene_list: List of gene symbols
            organism: Organism name

        Returns:
            dict with pathway results
        """
        try:
            # Limit to 100 genes
            genes = gene_list[:100]

            pathways = self._client.find_pathways_for_gene_list(genes, organism)

            # Find genes that weren't mapped
            mapped_genes = set()
            for pathway in pathways:
                mapped_genes.update(pathway.get("genes", []))

            not_found = [g for g in genes if g not in mapped_genes]

            return {
                "pathways": [
                    {
                        "pathway_id": p["pathway_id"],
                        "name": p.get("name", ""),
                        "gene_count": p["count"],
                        "genes": p["genes"],
                        "url": p["url"],
                    }
                    for p in pathways[:20]  # Top 20 pathways
                ],
                "genes_mapped": len(mapped_genes),
                "genes_not_found": not_found,
                "total_pathways": len(pathways),
            }

        except Exception as e:
            raise ToolError(f"Failed to find pathways for genes: {e}") from e


class GetGenesInPathwayTool(BioinformaticsTool):
    """Tool for getting genes in a KEGG pathway."""

    def __init__(self, client: KEGGClient | None = None):
        """Initialize the tool.

        Args:
            client: KEGGClient instance, creates one if not provided
        """
        self._client = client or KEGGClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_genes_in_pathway",
            description=(
                "Get the list of genes that are part of a KEGG pathway. "
                "Use this to see which genes are involved in a specific pathway."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "pathway_id": {
                        "type": "string",
                        "description": "KEGG pathway ID (e.g., 'hsa04110')",
                    },
                },
                "required": ["pathway_id"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "pathway_id": {"type": "string"},
                    "genes": {"type": "array", "items": {"type": "string"}},
                    "gene_count": {"type": "integer"},
                },
            },
            category="pathway",
            rate_limit=10,
            cacheable=True,
            cache_ttl_seconds=86400,
        )

    async def execute(self, pathway_id: str) -> dict[str, Any]:
        """Get genes in a pathway.

        Args:
            pathway_id: KEGG pathway ID

        Returns:
            dict with gene list
        """
        try:
            genes = self._client.get_genes_in_pathway(pathway_id)

            return {
                "pathway_id": pathway_id,
                "genes": genes,
                "gene_count": len(genes),
            }

        except Exception as e:
            raise ToolError(
                f"Failed to get genes for pathway {pathway_id}: {e}"
            ) from e


# Factory function
def create_kegg_tools(client: KEGGClient | None = None) -> list[BioinformaticsTool]:
    """Create all KEGG tools with a shared client.

    Args:
        client: Optional KEGGClient instance to share

    Returns:
        list of BioinformaticsTool instances
    """
    if client is None:
        client = KEGGClient()

    return [
        GetKEGGPathwayTool(client),
        SearchPathwaysTool(client),
        FindPathwaysForGenesTool(client),
        GetGenesInPathwayTool(client),
    ]
