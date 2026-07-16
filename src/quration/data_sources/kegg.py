"""
KEGG REST API client for pathway information retrieval.

This module provides a client for accessing KEGG pathway data including
pathway details, gene-pathway mappings, and pathway search.

API Documentation: https://www.kegg.jp/kegg/rest/keggapi.html
"""

import logging
import re
import time
from typing import Any

import requests
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class PathwayInfo(BaseModel):
    """KEGG pathway information."""

    pathway_id: str = Field(description="KEGG pathway ID (e.g., 'hsa04110')")
    name: str = Field(default="", description="Pathway name")
    description: str = Field(default="", description="Pathway description")
    organism: str = Field(default="", description="Organism code (e.g., 'hsa' for human)")
    gene_count: int | None = Field(default=None, description="Number of genes in pathway")
    url: str = Field(default="", description="URL to KEGG pathway page")


class GenePathwayMapping(BaseModel):
    """Gene to pathway mapping."""

    gene_id: str = Field(description="KEGG gene ID or gene symbol")
    pathways: list[PathwayInfo] = Field(
        default_factory=list, description="Pathways containing this gene"
    )


class KEGGClient:
    """Client for KEGG REST API.

    Provides methods for pathway lookup, gene-pathway mapping, and pathway search.

    Example:
        ```python
        client = KEGGClient()
        pathway = client.get_pathway("hsa04110")
        pathways = client.map_genes_to_pathways(["TP53", "BRCA1"], organism="hsa")
        ```
    """

    BASE_URL = "https://rest.kegg.jp"

    # Organism code mapping
    ORGANISM_CODES = {
        "human": "hsa",
        "homo sapiens": "hsa",
        "mouse": "mmu",
        "mus musculus": "mmu",
        "rat": "rno",
        "rattus norvegicus": "rno",
    }

    def __init__(self, rate_limit: int = 10):
        """Initialize KEGG client.

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

    def _get_organism_code(self, organism: str) -> str:
        """Convert organism name to KEGG organism code.

        Args:
            organism: Organism name or code

        Returns:
            KEGG organism code
        """
        return self.ORGANISM_CODES.get(organism.lower(), organism.lower())

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _make_request(self, endpoint: str) -> str:
        """Make rate-limited request to KEGG API.

        Args:
            endpoint: API endpoint

        Returns:
            Response text
        """
        self._rate_limit()

        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        return response.text

    def get_pathway(self, pathway_id: str) -> PathwayInfo | None:
        """Get pathway information.

        Args:
            pathway_id: KEGG pathway ID (e.g., 'hsa04110' or 'path:hsa04110')

        Returns:
            PathwayInfo or None if not found
        """
        # Normalize pathway ID
        if pathway_id.startswith("path:"):
            pathway_id = pathway_id[5:]

        try:
            # Get pathway info
            response = self._make_request(f"get/{pathway_id}")

            # Parse the flat file response
            info = self._parse_pathway_entry(response, pathway_id)
            return info

        except requests.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception as e:
            logger.error(f"Failed to get pathway {pathway_id}: {e}")
            return None

    def _parse_pathway_entry(self, text: str, pathway_id: str) -> PathwayInfo:
        """Parse KEGG pathway flat file entry.

        Args:
            text: KEGG flat file text
            pathway_id: Pathway ID

        Returns:
            PathwayInfo
        """
        name = ""
        description = ""
        organism = ""
        gene_count = 0

        current_section = None
        description_lines = []

        for line in text.split("\n"):
            if not line:
                continue

            # Check for section headers
            if line.startswith("NAME"):
                name = line[12:].strip()
            elif line.startswith("DESCRIPTION"):
                current_section = "DESCRIPTION"
                description_lines.append(line[12:].strip())
            elif line.startswith("ORGANISM"):
                current_section = None
                org_match = re.search(r"(\w+)\s+", line[12:])
                if org_match:
                    organism = org_match.group(1)
            elif line.startswith("GENE"):
                current_section = "GENE"
                gene_count = 1
            elif line.startswith("            ") and current_section == "GENE":
                gene_count += 1
            elif line.startswith("            ") and current_section == "DESCRIPTION":
                description_lines.append(line.strip())
            elif line[0] != " ":
                current_section = None

        # Extract organism from pathway ID if not found
        if not organism and len(pathway_id) >= 3:
            organism = pathway_id[:3]

        return PathwayInfo(
            pathway_id=pathway_id,
            name=name,
            description=" ".join(description_lines) if description_lines else "",
            organism=organism,
            gene_count=gene_count if gene_count > 0 else None,
            url=f"https://www.kegg.jp/pathway/{pathway_id}",
        )

    def search_pathways(
        self, query: str, organism: str = "human", limit: int = 20
    ) -> list[PathwayInfo]:
        """Search for pathways.

        Args:
            query: Search query
            organism: Organism name or code
            limit: Maximum results

        Returns:
            List of PathwayInfo
        """
        org_code = self._get_organism_code(organism)

        try:
            # List all pathways for organism
            response = self._make_request(f"list/pathway/{org_code}")

            # Filter by query
            pathways = []
            query_lower = query.lower()

            for line in response.strip().split("\n"):
                if not line:
                    continue

                parts = line.split("\t")
                if len(parts) >= 2:
                    pathway_id = parts[0].replace("path:", "")
                    name = parts[1]

                    # Check if query matches
                    if query_lower in name.lower():
                        pathways.append(
                            PathwayInfo(
                                pathway_id=pathway_id,
                                name=name,
                                organism=org_code,
                                url=f"https://www.kegg.jp/pathway/{pathway_id}",
                            )
                        )

                        if len(pathways) >= limit:
                            break

            return pathways

        except Exception as e:
            logger.error(f"Pathway search failed: {e}")
            return []

    def get_genes_in_pathway(self, pathway_id: str) -> list[str]:
        """Get list of genes in a pathway.

        Args:
            pathway_id: KEGG pathway ID

        Returns:
            List of gene symbols
        """
        if pathway_id.startswith("path:"):
            pathway_id = pathway_id[5:]

        try:
            response = self._make_request(f"link/genes/{pathway_id}")

            genes = []
            for line in response.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 2:
                    # Extract gene symbol from KEGG gene ID (e.g., "hsa:7157" -> "TP53")
                    gene_id = parts[1]
                    genes.append(gene_id)

            # Get gene symbols for the IDs
            if genes:
                return self._get_gene_symbols(genes[:100])  # Limit to 100

            return genes

        except Exception as e:
            logger.error(f"Failed to get genes for pathway {pathway_id}: {e}")
            return []

    def _get_gene_symbols(self, gene_ids: list[str]) -> list[str]:
        """Convert KEGG gene IDs to gene symbols.

        Args:
            gene_ids: List of KEGG gene IDs (e.g., 'hsa:7157')

        Returns:
            List of gene symbols
        """
        # Batch query genes
        ids_str = "+".join(gene_ids[:10])  # Limit batch size
        try:
            response = self._make_request(f"get/{ids_str}")

            symbols = []
            for line in response.split("\n"):
                if line.startswith("SYMBOL"):
                    symbol = line.split()[1] if len(line.split()) > 1 else ""
                    symbols.append(symbol)

            return symbols

        except Exception:
            # Return IDs if symbol lookup fails
            return [gid.split(":")[-1] if ":" in gid else gid for gid in gene_ids]

    def map_genes_to_pathways(
        self, genes: list[str], organism: str = "human"
    ) -> dict[str, list[PathwayInfo]]:
        """Map genes to their pathways.

        Args:
            genes: List of gene symbols
            organism: Organism name or code

        Returns:
            Dict mapping gene symbols to pathway lists
        """
        org_code = self._get_organism_code(organism)

        result = {gene: [] for gene in genes}

        try:
            # First, convert gene symbols to KEGG IDs
            for gene in genes:
                try:
                    # Search for gene
                    response = self._make_request(f"find/genes/{org_code}+{gene}")

                    kegg_gene_id = None
                    for line in response.strip().split("\n"):
                        if line and gene.upper() in line.upper():
                            kegg_gene_id = line.split("\t")[0]
                            break

                    if kegg_gene_id:
                        # Get pathways for this gene
                        pathway_response = self._make_request(
                            f"link/pathway/{kegg_gene_id}"
                        )

                        for pline in pathway_response.strip().split("\n"):
                            if not pline:
                                continue
                            parts = pline.split("\t")
                            if len(parts) >= 2:
                                pathway_id = parts[1].replace("path:", "")
                                result[gene].append(
                                    PathwayInfo(
                                        pathway_id=pathway_id,
                                        organism=org_code,
                                        url=f"https://www.kegg.jp/pathway/{pathway_id}",
                                    )
                                )

                except Exception as e:
                    logger.warning(f"Failed to map gene {gene}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Gene-pathway mapping failed: {e}")

        return result

    def find_pathways_for_gene_list(
        self, genes: list[str], organism: str = "human"
    ) -> list[dict[str, Any]]:
        """Find pathways enriched for a gene list.

        Args:
            genes: List of gene symbols
            organism: Organism name or code

        Returns:
            List of pathways with gene counts
        """
        # Map all genes to pathways
        gene_pathways = self.map_genes_to_pathways(genes, organism)

        # Count genes per pathway
        pathway_counts: dict[str, dict[str, Any]] = {}

        for gene, pathways in gene_pathways.items():
            for pathway in pathways:
                pid = pathway.pathway_id
                if pid not in pathway_counts:
                    pathway_counts[pid] = {
                        "pathway_id": pid,
                        "name": pathway.name,
                        "url": pathway.url,
                        "genes": [],
                        "count": 0,
                    }
                pathway_counts[pid]["genes"].append(gene)
                pathway_counts[pid]["count"] += 1

        # Sort by gene count
        result = sorted(
            pathway_counts.values(), key=lambda x: x["count"], reverse=True
        )

        # Fetch pathway names for top results
        for item in result[:20]:
            if not item["name"]:
                pathway_info = self.get_pathway(item["pathway_id"])
                if pathway_info:
                    item["name"] = pathway_info.name

        return result
