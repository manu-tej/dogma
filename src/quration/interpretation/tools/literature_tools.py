"""
Literature tools for LLM interpretation.

These tools provide LLM-callable interfaces for PubMed literature search
and abstract retrieval.
"""

import logging
from typing import Any

from quration.data_sources.pubmed import PubMedClient
from quration.interpretation.tools.base import (
    BioinformaticsTool,
    ToolDefinition,
    ToolError,
)

logger = logging.getLogger(__name__)


class SearchPubMedTool(BioinformaticsTool):
    """Tool for searching PubMed."""

    def __init__(self, client: PubMedClient | None = None):
        """Initialize the tool.

        Args:
            client: PubMedClient instance, creates one if not provided
        """
        self._client = client or PubMedClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_pubmed",
            description=(
                "Search PubMed for scientific articles. Returns article titles, "
                "abstracts, and publication info. Use this to find literature "
                "supporting biological claims."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "PubMed search query. Can use AND, OR, NOT operators. "
                            "Examples: 'TP53 cancer', 'BRCA1 AND breast cancer'"
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": ["query"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "articles": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "pmid": {"type": "string"},
                                "title": {"type": "string"},
                                "abstract": {"type": "string"},
                                "authors": {"type": "array"},
                                "journal": {"type": "string"},
                                "year": {"type": "integer"},
                            },
                        },
                    },
                    "total_found": {"type": "integer"},
                },
            },
            category="literature",
            rate_limit=3,
            cacheable=True,
            cache_ttl_seconds=3600,
            examples=[
                {
                    "input": {"query": "TP53 tumor suppressor mechanism"},
                    "output": {
                        "articles": [
                            {
                                "pmid": "12345678",
                                "title": "The role of p53 in...",
                                "abstract": "...",
                            }
                        ],
                        "total_found": 1,
                    },
                }
            ],
        )

    async def execute(
        self, query: str, max_results: int = 5
    ) -> dict[str, Any]:
        """Search PubMed.

        Args:
            query: Search query
            max_results: Maximum results

        Returns:
            dict with search results
        """
        try:
            articles = self._client.search(query, max_results=max_results)

            return {
                "articles": [
                    {
                        "pmid": a.pmid,
                        "title": a.title,
                        "abstract": a.abstract[:500] + "..."
                        if len(a.abstract) > 500
                        else a.abstract,
                        "authors": a.authors,
                        "journal": a.journal,
                        "year": a.year,
                        "doi": a.doi,
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{a.pmid}/",
                    }
                    for a in articles
                ],
                "total_found": len(articles),
            }

        except Exception as e:
            raise ToolError(f"PubMed search failed: {e}") from e


class GetAbstractTool(BioinformaticsTool):
    """Tool for getting PubMed abstract by PMID."""

    def __init__(self, client: PubMedClient | None = None):
        """Initialize the tool.

        Args:
            client: PubMedClient instance, creates one if not provided
        """
        self._client = client or PubMedClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_abstract",
            description=(
                "Get the full abstract of a PubMed article by its PMID. "
                "Use this when you need to read the full abstract of a specific paper."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "pmid": {
                        "type": "string",
                        "description": "PubMed ID (e.g., '12345678')",
                    },
                },
                "required": ["pmid"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "found": {"type": "boolean"},
                    "pmid": {"type": "string"},
                    "title": {"type": "string"},
                    "abstract": {"type": "string"},
                    "authors": {"type": "array"},
                    "journal": {"type": "string"},
                    "year": {"type": "integer"},
                },
            },
            category="literature",
            rate_limit=3,
            cacheable=True,
            cache_ttl_seconds=86400,
        )

    async def execute(self, pmid: str) -> dict[str, Any]:
        """Get article abstract.

        Args:
            pmid: PubMed ID

        Returns:
            dict with article info
        """
        try:
            article = self._client.get_abstract(pmid)

            if article:
                return {
                    "found": True,
                    "pmid": article.pmid,
                    "title": article.title,
                    "abstract": article.abstract,
                    "authors": article.authors,
                    "journal": article.journal,
                    "year": article.year,
                    "doi": article.doi,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{article.pmid}/",
                }
            else:
                return {
                    "found": False,
                    "pmid": pmid,
                    "message": f"Article with PMID {pmid} not found",
                }

        except Exception as e:
            raise ToolError(f"Failed to get abstract for PMID {pmid}: {e}") from e


class SearchGeneLiteratureTool(BioinformaticsTool):
    """Tool for searching literature about a specific gene."""

    def __init__(self, client: PubMedClient | None = None):
        """Initialize the tool.

        Args:
            client: PubMedClient instance, creates one if not provided
        """
        self._client = client or PubMedClient()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_gene_literature",
            description=(
                "Search PubMed for literature about a specific gene. "
                "Automatically constructs a gene-focused query. "
                "Use this to find papers about a gene's function or role."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "gene_symbol": {
                        "type": "string",
                        "description": "Gene symbol (e.g., 'TP53', 'BRCA1')",
                    },
                    "context": {
                        "type": "string",
                        "description": (
                            "Additional context to narrow search "
                            "(e.g., 'cancer', 'signaling', 'therapy')"
                        ),
                        "default": "",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10,
                    },
                },
                "required": ["gene_symbol"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "articles": {"type": "array"},
                    "total_found": {"type": "integer"},
                },
            },
            category="literature",
            rate_limit=3,
            cacheable=True,
            cache_ttl_seconds=3600,
        )

    async def execute(
        self,
        gene_symbol: str,
        context: str = "",
        max_results: int = 5,
    ) -> dict[str, Any]:
        """Search gene literature.

        Args:
            gene_symbol: Gene symbol
            context: Additional context
            max_results: Maximum results

        Returns:
            dict with search results
        """
        try:
            articles = self._client.search_gene_literature(
                gene_symbol, context=context, max_results=max_results
            )

            return {
                "gene_symbol": gene_symbol,
                "context": context,
                "articles": [
                    {
                        "pmid": a.pmid,
                        "title": a.title,
                        "abstract": a.abstract[:400] + "..."
                        if len(a.abstract) > 400
                        else a.abstract,
                        "year": a.year,
                        "journal": a.journal,
                        "url": f"https://pubmed.ncbi.nlm.nih.gov/{a.pmid}/",
                    }
                    for a in articles
                ],
                "total_found": len(articles),
            }

        except Exception as e:
            raise ToolError(f"Gene literature search failed: {e}") from e


# Factory function
def create_literature_tools(
    client: PubMedClient | None = None,
) -> list[BioinformaticsTool]:
    """Create all literature tools with a shared client.

    Args:
        client: Optional PubMedClient instance to share

    Returns:
        list of BioinformaticsTool instances
    """
    if client is None:
        client = PubMedClient()

    return [
        SearchPubMedTool(client),
        GetAbstractTool(client),
        SearchGeneLiteratureTool(client),
    ]
