"""
PubMed E-utilities client for literature search.

This module provides a client for searching PubMed and retrieving abstracts
using NCBI E-utilities.

API Documentation: https://www.ncbi.nlm.nih.gov/books/NBK25499/
"""

import logging
import time
import xml.etree.ElementTree as ET
from typing import Any

import requests
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from quration.config import get_config

logger = logging.getLogger(__name__)


class PubMedArticle(BaseModel):
    """PubMed article information."""

    pmid: str = Field(description="PubMed ID")
    title: str = Field(default="", description="Article title")
    abstract: str = Field(default="", description="Article abstract")
    authors: list[str] = Field(default_factory=list, description="Author list")
    journal: str = Field(default="", description="Journal name")
    year: int | None = Field(default=None, description="Publication year")
    doi: str = Field(default="", description="DOI if available")
    pmcid: str = Field(default="", description="PMC ID if available")


class PubMedClient:
    """Client for PubMed E-utilities API.

    Provides methods for searching PubMed and retrieving article metadata.

    Example:
        ```python
        client = PubMedClient()
        articles = client.search("TP53 cancer", max_results=10)
        article = client.get_abstract("12345678")
        ```
    """

    BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, rate_limit: int | None = None):
        """Initialize PubMed client.

        Args:
            rate_limit: Requests per second (default: from config)
        """
        config = get_config().data_sources.geo  # Reuse GEO config for NCBI settings
        self.tool = config.tool
        self.email = config.email
        self.api_key = config.api_key

        # Rate limiting: 3/sec without API key, 10/sec with
        if rate_limit is None:
            rate_limit = config.get_effective_rate_limit()

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
        self, endpoint: str, params: dict[str, Any]
    ) -> requests.Response:
        """Make rate-limited request to E-utilities.

        Args:
            endpoint: E-utilities endpoint
            params: Query parameters

        Returns:
            Response object
        """
        self._rate_limit()

        # Add required NCBI parameters
        params["tool"] = self.tool
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key

        url = f"{self.BASE_URL}/{endpoint}"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        return response

    def search(
        self, query: str, max_results: int = 10, sort: str = "relevance"
    ) -> list[PubMedArticle]:
        """Search PubMed for articles.

        Args:
            query: Search query
            max_results: Maximum results
            sort: Sort order ('relevance' or 'date')

        Returns:
            List of PubMedArticle
        """
        try:
            # Search for PMIDs
            search_params = {
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retmode": "xml",
                "sort": sort,
            }

            search_response = self._make_request("esearch.fcgi", search_params)
            search_root = ET.fromstring(search_response.content)

            id_list = search_root.find("IdList")
            if id_list is None:
                return []

            pmids = [id_elem.text for id_elem in id_list.findall("Id") if id_elem.text]

            if not pmids:
                return []

            # Fetch article details
            return self._fetch_articles(pmids)

        except Exception as e:
            logger.error(f"PubMed search failed: {e}")
            return []

    def get_abstract(self, pmid: str) -> PubMedArticle | None:
        """Get article by PMID.

        Args:
            pmid: PubMed ID

        Returns:
            PubMedArticle or None
        """
        articles = self._fetch_articles([pmid])
        return articles[0] if articles else None

    def search_gene_literature(
        self, gene_symbol: str, context: str = "", max_results: int = 5
    ) -> list[PubMedArticle]:
        """Search for literature about a specific gene.

        Args:
            gene_symbol: Gene symbol
            context: Additional context (e.g., 'cancer', 'function')
            max_results: Maximum results

        Returns:
            List of PubMedArticle
        """
        # Build gene-focused query
        if context:
            query = f'"{gene_symbol}"[Title/Abstract] AND {context}'
        else:
            query = f'"{gene_symbol}"[Title/Abstract] AND ("gene function" OR "role" OR "mechanism")'

        return self.search(query, max_results=max_results)

    def _fetch_articles(self, pmids: list[str]) -> list[PubMedArticle]:
        """Fetch article details for PMIDs.

        Args:
            pmids: List of PubMed IDs

        Returns:
            List of PubMedArticle
        """
        if not pmids:
            return []

        try:
            fetch_params = {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
            }

            fetch_response = self._make_request("efetch.fcgi", fetch_params)
            root = ET.fromstring(fetch_response.content)

            articles = []
            for article_elem in root.findall(".//PubmedArticle"):
                article = self._parse_article(article_elem)
                if article:
                    articles.append(article)

            return articles

        except Exception as e:
            logger.error(f"Failed to fetch articles: {e}")
            return []

    def _parse_article(self, elem: ET.Element) -> PubMedArticle | None:
        """Parse PubMed XML article element.

        Args:
            elem: XML element

        Returns:
            PubMedArticle or None
        """
        try:
            # Get PMID
            pmid_elem = elem.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else ""

            # Get title
            title_elem = elem.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else ""

            # Get abstract
            abstract_parts = []
            for abstract_text in elem.findall(".//AbstractText"):
                if abstract_text.text:
                    label = abstract_text.get("Label", "")
                    if label:
                        abstract_parts.append(f"{label}: {abstract_text.text}")
                    else:
                        abstract_parts.append(abstract_text.text)
            abstract = " ".join(abstract_parts)

            # Get authors
            authors = []
            for author in elem.findall(".//Author"):
                last_name = author.find("LastName")
                first_name = author.find("ForeName")
                if last_name is not None and last_name.text:
                    name = last_name.text
                    if first_name is not None and first_name.text:
                        name = f"{first_name.text} {last_name.text}"
                    authors.append(name)

            # Get journal
            journal_elem = elem.find(".//Journal/Title")
            journal = journal_elem.text if journal_elem is not None else ""

            # Get year
            year = None
            year_elem = elem.find(".//PubDate/Year")
            if year_elem is not None and year_elem.text:
                try:
                    year = int(year_elem.text)
                except ValueError:
                    pass

            # Get DOI
            doi = ""
            for article_id in elem.findall(".//ArticleId"):
                if article_id.get("IdType") == "doi":
                    doi = article_id.text or ""
                    break

            # Get PMCID
            pmcid = ""
            for article_id in elem.findall(".//ArticleId"):
                if article_id.get("IdType") == "pmc":
                    pmcid = article_id.text or ""
                    break

            return PubMedArticle(
                pmid=pmid,
                title=title,
                abstract=abstract,
                authors=authors[:5],  # Limit authors
                journal=journal,
                year=year,
                doi=doi,
                pmcid=pmcid,
            )

        except Exception as e:
            logger.error(f"Failed to parse article: {e}")
            return None
