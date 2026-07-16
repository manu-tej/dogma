"""
NCBI Gene tools for LLM interpretation.

These tools provide LLM-callable interfaces for NCBI Gene information
retrieval including gene symbols, summaries, aliases, and functions.
"""

import logging
from typing import Any

from quration.data_sources.ncbi_gene import NCBIGeneClient
from quration.interpretation.tools.base import (
    BioinformaticsTool,
    ToolDefinition,
    ToolError,
)

logger = logging.getLogger(__name__)


class GetGeneInfoTool(BioinformaticsTool):
    """Tool for getting gene information by symbol."""

    def __init__(self, client: NCBIGeneClient | None = None):
        """Initialize the tool.

        Args:
            client: NCBIGeneClient instance, creates one if not provided
        """
        self._client = client or NCBIGeneClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_gene_info",
            description=(
                "Get detailed information about a gene from NCBI Gene database. "
                "Returns gene symbol, name, summary, aliases, and genomic location. "
                "Use this to understand a gene's basic identity and function."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "gene_symbol": {
                        "type": "string",
                        "description": "Gene symbol (e.g., 'TP53', 'BRCA1', 'EGFR')",
                    },
                    "organism": {
                        "type": "string",
                        "description": "Organism name",
                        "default": "human",
                        "enum": ["human", "mouse", "rat"],
                    },
                },
                "required": ["gene_symbol"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "found": {"type": "boolean"},
                    "gene_id": {"type": "integer"},
                    "symbol": {"type": "string"},
                    "name": {"type": "string"},
                    "summary": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "chromosome": {"type": "string"},
                    "gene_type": {"type": "string"},
                },
            },
            category="gene",
            rate_limit=3,
            cacheable=True,
            cache_ttl_seconds=86400,
            examples=[
                {
                    "input": {"gene_symbol": "TP53"},
                    "output": {
                        "found": True,
                        "gene_id": 7157,
                        "symbol": "TP53",
                        "name": "tumor protein p53",
                        "summary": "This gene encodes a tumor suppressor...",
                    },
                }
            ],
        )

    async def execute(
        self, gene_symbol: str, organism: str = "human"
    ) -> dict[str, Any]:
        """Get gene information.

        Args:
            gene_symbol: Gene symbol
            organism: Organism name

        Returns:
            dict with gene information
        """
        try:
            gene = self._client.get_gene_info(gene_symbol, organism)

            if gene:
                return {
                    "found": True,
                    "gene_id": gene.gene_id,
                    "symbol": gene.symbol,
                    "name": gene.name,
                    "summary": gene.summary[:800] + "..."
                    if len(gene.summary) > 800
                    else gene.summary,
                    "aliases": gene.aliases,
                    "chromosome": gene.chromosome,
                    "map_location": gene.map_location,
                    "gene_type": gene.gene_type,
                    "organism": gene.organism,
                    "ncbi_url": f"https://www.ncbi.nlm.nih.gov/gene/{gene.gene_id}",
                }
            else:
                return {
                    "found": False,
                    "gene_symbol": gene_symbol,
                    "organism": organism,
                    "message": f"Gene {gene_symbol} not found for {organism}",
                }

        except Exception as e:
            raise ToolError(f"Failed to get gene info for {gene_symbol}: {e}") from e


class GetGeneSummaryTool(BioinformaticsTool):
    """Tool for getting gene summary by NCBI Gene ID."""

    def __init__(self, client: NCBIGeneClient | None = None):
        """Initialize the tool.

        Args:
            client: NCBIGeneClient instance, creates one if not provided
        """
        self._client = client or NCBIGeneClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_gene_summary",
            description=(
                "Get the summary text for a gene by its NCBI Gene ID. "
                "The summary provides a concise description of the gene's function. "
                "Use when you have a Gene ID and need the functional description."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "gene_id": {
                        "type": "integer",
                        "description": "NCBI Gene ID (e.g., 7157 for TP53)",
                    },
                },
                "required": ["gene_id"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "gene_id": {"type": "integer"},
                    "summary": {"type": "string"},
                },
            },
            category="gene",
            rate_limit=3,
            cacheable=True,
            cache_ttl_seconds=86400,
        )

    async def execute(self, gene_id: int) -> dict[str, Any]:
        """Get gene summary.

        Args:
            gene_id: NCBI Gene ID

        Returns:
            dict with gene summary
        """
        try:
            summary = self._client.get_gene_summary(gene_id)

            return {
                "gene_id": gene_id,
                "summary": summary if summary else "No summary available",
                "ncbi_url": f"https://www.ncbi.nlm.nih.gov/gene/{gene_id}",
            }

        except Exception as e:
            raise ToolError(f"Failed to get summary for gene {gene_id}: {e}") from e


class GetGeneAliasesTool(BioinformaticsTool):
    """Tool for getting gene aliases."""

    def __init__(self, client: NCBIGeneClient | None = None):
        """Initialize the tool.

        Args:
            client: NCBIGeneClient instance, creates one if not provided
        """
        self._client = client or NCBIGeneClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_gene_aliases",
            description=(
                "Get alternative names/symbols for a gene. "
                "Useful for understanding gene nomenclature and finding related names. "
                "Helps when literature uses different names for the same gene."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "gene_symbol": {
                        "type": "string",
                        "description": "Gene symbol",
                    },
                    "organism": {
                        "type": "string",
                        "description": "Organism name",
                        "default": "human",
                    },
                },
                "required": ["gene_symbol"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "gene_symbol": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                },
            },
            category="gene",
            rate_limit=3,
            cacheable=True,
            cache_ttl_seconds=86400,
        )

    async def execute(
        self, gene_symbol: str, organism: str = "human"
    ) -> dict[str, Any]:
        """Get gene aliases.

        Args:
            gene_symbol: Gene symbol
            organism: Organism name

        Returns:
            dict with aliases
        """
        try:
            aliases = self._client.get_gene_aliases(gene_symbol, organism)

            return {
                "gene_symbol": gene_symbol,
                "organism": organism,
                "aliases": aliases,
                "total_aliases": len(aliases),
            }

        except Exception as e:
            raise ToolError(f"Failed to get aliases for {gene_symbol}: {e}") from e


class SearchGenesTool(BioinformaticsTool):
    """Tool for searching genes."""

    def __init__(self, client: NCBIGeneClient | None = None):
        """Initialize the tool.

        Args:
            client: NCBIGeneClient instance, creates one if not provided
        """
        self._client = client or NCBIGeneClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_genes",
            description=(
                "Search NCBI Gene database for genes matching a query. "
                "Can search by function, pathway, disease association, etc. "
                "Use this to discover genes related to a biological concept."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query. Can include gene names, functions, "
                            "diseases, or biological processes."
                        ),
                    },
                    "organism": {
                        "type": "string",
                        "description": "Organism name",
                        "default": "human",
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
                    "genes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "gene_id": {"type": "integer"},
                                "symbol": {"type": "string"},
                                "name": {"type": "string"},
                            },
                        },
                    },
                    "total_found": {"type": "integer"},
                },
            },
            category="gene",
            rate_limit=3,
            cacheable=True,
            cache_ttl_seconds=3600,
        )

    async def execute(
        self, query: str, organism: str = "human", max_results: int = 10
    ) -> dict[str, Any]:
        """Search for genes.

        Args:
            query: Search query
            organism: Organism name
            max_results: Maximum results

        Returns:
            dict with search results
        """
        try:
            genes = self._client.search_genes(query, organism, max_results)

            return {
                "query": query,
                "organism": organism,
                "genes": [
                    {
                        "gene_id": g.gene_id,
                        "symbol": g.symbol,
                        "name": g.name,
                        "chromosome": g.chromosome,
                        "gene_type": g.gene_type,
                        "ncbi_url": f"https://www.ncbi.nlm.nih.gov/gene/{g.gene_id}",
                    }
                    for g in genes
                ],
                "total_found": len(genes),
            }

        except Exception as e:
            raise ToolError(f"Gene search failed: {e}") from e


class BatchLookupGenesTool(BioinformaticsTool):
    """Tool for batch gene lookup."""

    def __init__(self, client: NCBIGeneClient | None = None):
        """Initialize the tool.

        Args:
            client: NCBIGeneClient instance, creates one if not provided
        """
        self._client = client or NCBIGeneClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="batch_lookup_genes",
            description=(
                "Look up information for multiple genes at once. "
                "More efficient than individual lookups for gene lists. "
                "Use when you have a list of genes from DEG analysis."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "gene_symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of gene symbols to look up",
                        "maxItems": 50,
                    },
                    "organism": {
                        "type": "string",
                        "description": "Organism name",
                        "default": "human",
                    },
                },
                "required": ["gene_symbols"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "genes": {"type": "object"},
                    "found_count": {"type": "integer"},
                    "not_found": {"type": "array"},
                },
            },
            category="gene",
            rate_limit=2,  # Lower rate for batch operations
            cacheable=True,
            cache_ttl_seconds=86400,
        )

    async def execute(
        self, gene_symbols: list[str], organism: str = "human"
    ) -> dict[str, Any]:
        """Batch lookup genes.

        Args:
            gene_symbols: List of gene symbols
            organism: Organism name

        Returns:
            dict with lookup results
        """
        try:
            results = self._client.batch_lookup(gene_symbols, organism)

            genes = {}
            not_found = []

            for symbol, gene in results.items():
                if gene:
                    genes[symbol] = {
                        "gene_id": gene.gene_id,
                        "symbol": gene.symbol,
                        "name": gene.name,
                        "summary": gene.summary[:300] + "..."
                        if len(gene.summary) > 300
                        else gene.summary,
                        "chromosome": gene.chromosome,
                        "gene_type": gene.gene_type,
                    }
                else:
                    not_found.append(symbol)

            return {
                "organism": organism,
                "genes": genes,
                "found_count": len(genes),
                "not_found": not_found,
                "not_found_count": len(not_found),
            }

        except Exception as e:
            raise ToolError(f"Batch gene lookup failed: {e}") from e


# Factory function
def create_ncbi_gene_tools(
    client: NCBIGeneClient | None = None,
) -> list[BioinformaticsTool]:
    """Create all NCBI Gene tools with a shared client.

    Args:
        client: Optional NCBIGeneClient instance to share

    Returns:
        list of BioinformaticsTool instances
    """
    if client is None:
        client = NCBIGeneClient()

    return [
        GetGeneInfoTool(client),
        GetGeneSummaryTool(client),
        GetGeneAliasesTool(client),
        SearchGenesTool(client),
        BatchLookupGenesTool(client),
    ]
