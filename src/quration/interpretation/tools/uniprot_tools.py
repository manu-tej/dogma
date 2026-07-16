"""
UniProt tools for LLM interpretation.

These tools provide LLM-callable interfaces for protein information
retrieval from UniProt.
"""

import logging
from typing import Any

from quration.data_sources.uniprot import UniProtClient
from quration.interpretation.tools.base import (
    BioinformaticsTool,
    ToolDefinition,
    ToolError,
)

logger = logging.getLogger(__name__)


class GetGeneProteinInfoTool(BioinformaticsTool):
    """Tool for getting protein information for a gene."""

    def __init__(self, client: UniProtClient | None = None):
        """Initialize the tool.

        Args:
            client: UniProtClient instance, creates one if not provided
        """
        self._client = client or UniProtClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_gene_protein_info",
            description=(
                "Get protein information for a gene symbol from UniProt. "
                "Returns protein name, function, subcellular location, GO terms, and keywords. "
                "Use this to understand what a gene's protein product does."
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
                    "uniprot_id": {"type": "string"},
                    "protein_name": {"type": "string"},
                    "function": {"type": "string"},
                    "subcellular_location": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "keywords": {"type": "array", "items": {"type": "string"}},
                },
            },
            category="protein",
            rate_limit=10,
            cacheable=True,
            cache_ttl_seconds=86400,  # 24 hours
            examples=[
                {
                    "input": {"gene_symbol": "TP53", "organism": "human"},
                    "output": {
                        "found": True,
                        "uniprot_id": "P04637",
                        "protein_name": "Cellular tumor antigen p53",
                        "function": "Acts as a tumor suppressor...",
                    },
                }
            ],
        )

    async def execute(
        self, gene_symbol: str, organism: str = "human"
    ) -> dict[str, Any]:
        """Get protein info for a gene.

        Args:
            gene_symbol: Gene symbol
            organism: Organism name

        Returns:
            dict with protein information
        """
        try:
            protein = self._client.get_gene_protein_info(gene_symbol, organism)

            if protein:
                return {
                    "found": True,
                    "gene_symbol": gene_symbol,
                    "uniprot_id": protein.uniprot_id,
                    "entry_name": protein.entry_name,
                    "protein_name": protein.protein_name,
                    "gene_names": protein.gene_names,
                    "organism": protein.organism,
                    "function": protein.function,
                    "subcellular_location": protein.subcellular_location,
                    "keywords": protein.keywords,
                    "sequence_length": protein.sequence_length,
                }
            else:
                return {
                    "found": False,
                    "gene_symbol": gene_symbol,
                    "organism": organism,
                    "message": f"No UniProt entry found for {gene_symbol} in {organism}",
                }

        except Exception as e:
            raise ToolError(f"Failed to get protein info for {gene_symbol}: {e}") from e


class GetProteinFunctionTool(BioinformaticsTool):
    """Tool for getting detailed protein function annotation."""

    def __init__(self, client: UniProtClient | None = None):
        """Initialize the tool.

        Args:
            client: UniProtClient instance, creates one if not provided
        """
        self._client = client or UniProtClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_protein_function",
            description=(
                "Get detailed function annotation for a protein by UniProt ID. "
                "Returns function description, GO terms, and keywords. "
                "Use when you have a UniProt ID and need functional details."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "uniprot_id": {
                        "type": "string",
                        "description": "UniProt accession ID (e.g., 'P04637' or 'P53_HUMAN')",
                    },
                },
                "required": ["uniprot_id"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "found": {"type": "boolean"},
                    "uniprot_id": {"type": "string"},
                    "protein_name": {"type": "string"},
                    "function": {"type": "string"},
                    "go_terms": {"type": "array"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                },
            },
            category="protein",
            rate_limit=10,
            cacheable=True,
            cache_ttl_seconds=86400,
        )

    async def execute(self, uniprot_id: str) -> dict[str, Any]:
        """Get protein function annotation.

        Args:
            uniprot_id: UniProt accession ID

        Returns:
            dict with function information
        """
        try:
            result = self._client.get_function(uniprot_id)

            if "error" in result:
                return {
                    "found": False,
                    "uniprot_id": uniprot_id,
                    "message": result["error"],
                }

            return {
                "found": True,
                **result,
            }

        except Exception as e:
            raise ToolError(
                f"Failed to get function for {uniprot_id}: {e}"
            ) from e


class SearchProteinsTool(BioinformaticsTool):
    """Tool for searching UniProt proteins."""

    def __init__(self, client: UniProtClient | None = None):
        """Initialize the tool.

        Args:
            client: UniProtClient instance, creates one if not provided
        """
        self._client = client or UniProtClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_proteins",
            description=(
                "Search UniProt for proteins matching a query. "
                "Can search by gene name, protein name, function keywords, etc. "
                "Use this to find proteins related to a biological concept."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query - gene name, protein name, keyword, etc. "
                            "Examples: 'kinase', 'DNA repair', 'apoptosis'"
                        ),
                    },
                    "organism": {
                        "type": "string",
                        "description": "Filter by organism",
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
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "uniprot_id": {"type": "string"},
                                "protein_name": {"type": "string"},
                                "gene_names": {"type": "array"},
                            },
                        },
                    },
                    "total_found": {"type": "integer"},
                },
            },
            category="protein",
            rate_limit=10,
            cacheable=True,
            cache_ttl_seconds=3600,
        )

    async def execute(
        self, query: str, organism: str = "human", max_results: int = 10
    ) -> dict[str, Any]:
        """Search for proteins.

        Args:
            query: Search query
            organism: Organism filter
            max_results: Maximum results

        Returns:
            dict with search results
        """
        try:
            proteins = self._client.search(query, organism=organism, limit=max_results)

            return {
                "results": [
                    {
                        "uniprot_id": p.uniprot_id,
                        "entry_name": p.entry_name,
                        "protein_name": p.protein_name,
                        "gene_names": p.gene_names,
                        "organism": p.organism,
                        "function": p.function[:200] + "..."
                        if len(p.function) > 200
                        else p.function,
                    }
                    for p in proteins
                ],
                "total_found": len(proteins),
            }

        except Exception as e:
            raise ToolError(f"Protein search failed: {e}") from e


class BatchLookupProteinsTool(BioinformaticsTool):
    """Tool for batch lookup of multiple gene symbols."""

    def __init__(self, client: UniProtClient | None = None):
        """Initialize the tool.

        Args:
            client: UniProtClient instance, creates one if not provided
        """
        self._client = client or UniProtClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="batch_lookup_proteins",
            description=(
                "Look up protein information for multiple gene symbols at once. "
                "More efficient than calling get_gene_protein_info multiple times. "
                "Use when you have a list of genes from DEG analysis."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "gene_symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of gene symbols (max 50)",
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
                    "proteins": {"type": "object"},
                    "found_count": {"type": "integer"},
                    "not_found": {"type": "array", "items": {"type": "string"}},
                },
            },
            category="protein",
            rate_limit=2,  # Lower rate for batch operations
            cacheable=True,
            cache_ttl_seconds=86400,
        )

    async def execute(
        self, gene_symbols: list[str], organism: str = "human"
    ) -> dict[str, Any]:
        """Batch lookup protein info.

        Args:
            gene_symbols: List of gene symbols
            organism: Organism name

        Returns:
            dict with protein information for each gene
        """
        try:
            # Limit to 50 genes
            genes = gene_symbols[:50]
            results = self._client.batch_lookup(genes, organism)

            proteins = {}
            not_found = []

            for gene, protein in results.items():
                if protein:
                    proteins[gene] = {
                        "uniprot_id": protein.uniprot_id,
                        "protein_name": protein.protein_name,
                        "function": protein.function[:300] + "..."
                        if len(protein.function) > 300
                        else protein.function,
                        "keywords": protein.keywords[:10],  # Limit keywords
                    }
                else:
                    not_found.append(gene)

            return {
                "proteins": proteins,
                "found_count": len(proteins),
                "not_found": not_found,
                "total_queried": len(genes),
            }

        except Exception as e:
            raise ToolError(f"Batch protein lookup failed: {e}") from e


# Factory function
def create_uniprot_tools(
    client: UniProtClient | None = None,
) -> list[BioinformaticsTool]:
    """Create all UniProt tools with a shared client.

    Args:
        client: Optional UniProtClient instance to share

    Returns:
        list of BioinformaticsTool instances
    """
    if client is None:
        client = UniProtClient()

    return [
        GetGeneProteinInfoTool(client),
        GetProteinFunctionTool(client),
        SearchProteinsTool(client),
        BatchLookupProteinsTool(client),
    ]
