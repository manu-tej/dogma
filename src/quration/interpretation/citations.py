"""
Citation generator for interpretation claims.

This module provides citation generation and formatting for
evidence sources used in bioinformatics interpretations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from quration.interpretation.models import EvidenceSource, ToolCallRecord


class CitationStyle(str, Enum):
    """Citation formatting styles."""

    SIMPLE = "simple"  # Author Year format
    APA = "apa"  # APA style
    VANCOUVER = "vancouver"  # Vancouver (numbered)
    INLINE = "inline"  # Inline format for text
    MARKDOWN = "markdown"  # Markdown with links


@dataclass
class Citation:
    """A formatted citation."""

    citation_id: str  # Unique identifier (e.g., "1", "smith2020")
    source_type: str  # pmid, doi, database, tool
    source_id: str  # The actual ID (PMID number, etc.)
    formatted: str  # Formatted citation text
    url: str = ""  # Link to source
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    journal: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CitationCollection:
    """Collection of citations with bibliography generation."""

    citations: list[Citation] = field(default_factory=list)
    _id_counter: int = 1
    _by_source: dict[str, Citation] = field(default_factory=dict)

    def add(self, citation: Citation) -> str:
        """Add a citation and return its ID.

        Args:
            citation: Citation to add

        Returns:
            Citation ID
        """
        # Check for duplicates
        key = f"{citation.source_type}:{citation.source_id}"
        if key in self._by_source:
            return self._by_source[key].citation_id

        if not citation.citation_id:
            citation.citation_id = str(self._id_counter)
            self._id_counter += 1

        self.citations.append(citation)
        self._by_source[key] = citation
        return citation.citation_id

    def get(self, citation_id: str) -> Citation | None:
        """Get citation by ID."""
        for c in self.citations:
            if c.citation_id == citation_id:
                return c
        return None

    def get_by_source(self, source_type: str, source_id: str) -> Citation | None:
        """Get citation by source."""
        key = f"{source_type}:{source_id}"
        return self._by_source.get(key)

    def generate_bibliography(self, style: CitationStyle = CitationStyle.SIMPLE) -> str:
        """Generate bibliography in specified style.

        Args:
            style: Citation style to use

        Returns:
            Formatted bibliography
        """
        lines = []

        for citation in self.citations:
            if style == CitationStyle.VANCOUVER:
                lines.append(f"[{citation.citation_id}] {citation.formatted}")
            elif style == CitationStyle.MARKDOWN:
                if citation.url:
                    lines.append(f"- [{citation.citation_id}] [{citation.formatted}]({citation.url})")
                else:
                    lines.append(f"- [{citation.citation_id}] {citation.formatted}")
            else:
                lines.append(f"{citation.formatted}")

        return "\n".join(lines)


class CitationGenerator:
    """Generator for creating citations from tool results.

    Supports:
    - PubMed articles
    - Database entries (UniProt, KEGG, Reactome, STRING)
    - NCBI Gene entries
    - Custom sources

    Example:
        ```python
        generator = CitationGenerator()

        # From PubMed result
        citation = generator.from_pubmed_result({
            'pmid': '12345678',
            'title': 'Study Title',
            'authors': ['Smith J', 'Jones K'],
            'year': 2020,
            'journal': 'Nature'
        })

        # From tool call
        citations = generator.from_tool_call(tool_call_record)
        ```
    """

    def __init__(self, default_style: CitationStyle = CitationStyle.SIMPLE):
        """Initialize generator.

        Args:
            default_style: Default citation style
        """
        self.default_style = default_style

    def from_pubmed_result(
        self,
        result: dict[str, Any],
        style: CitationStyle | None = None,
    ) -> Citation:
        """Create citation from PubMed search result.

        Args:
            result: PubMed result dict with pmid, title, authors, year, journal
            style: Citation style to use

        Returns:
            Formatted Citation
        """
        style = style or self.default_style
        pmid = str(result.get("pmid", ""))
        title = result.get("title", "Untitled")
        authors = result.get("authors", [])
        year = result.get("year")
        journal = result.get("journal", "")
        doi = result.get("doi", "")

        # Format based on style
        formatted = self._format_article_citation(
            authors, year, title, journal, style
        )

        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""

        return Citation(
            citation_id="",  # Will be assigned when added to collection
            source_type="pmid",
            source_id=pmid,
            formatted=formatted,
            url=url,
            title=title,
            authors=authors,
            year=year,
            journal=journal,
            metadata={"doi": doi},
        )

    def from_gene_info(
        self,
        result: dict[str, Any],
        style: CitationStyle | None = None,
    ) -> Citation:
        """Create citation from NCBI Gene result.

        Args:
            result: Gene info dict
            style: Citation style

        Returns:
            Database citation
        """
        style = style or self.default_style
        gene_id = str(result.get("gene_id", result.get("ncbi_id", "")))
        symbol = result.get("symbol", result.get("gene_symbol", ""))
        name = result.get("name", "")

        formatted = f"NCBI Gene: {symbol}"
        if name:
            formatted += f" - {name}"
        formatted += f" (GeneID: {gene_id})"

        url = f"https://www.ncbi.nlm.nih.gov/gene/{gene_id}" if gene_id else ""

        return Citation(
            citation_id="",
            source_type="ncbi_gene",
            source_id=gene_id,
            formatted=formatted,
            url=url,
            title=f"{symbol} - {name}",
            metadata={"symbol": symbol, "name": name},
        )

    def from_pathway_result(
        self,
        result: dict[str, Any],
        database: str = "reactome",
    ) -> Citation:
        """Create citation from pathway database result.

        Args:
            result: Pathway result dict
            database: Database source (reactome, kegg)

        Returns:
            Pathway citation
        """
        pathway_id = result.get("pathway_id", result.get("stable_id", ""))
        name = result.get("name", result.get("pathway_name", ""))

        if database.lower() == "reactome":
            formatted = f"Reactome: {name} ({pathway_id})"
            url = f"https://reactome.org/PathwayBrowser/#/{pathway_id}"
        elif database.lower() == "kegg":
            formatted = f"KEGG Pathway: {name} ({pathway_id})"
            url = f"https://www.kegg.jp/entry/{pathway_id}"
        else:
            formatted = f"{database}: {name} ({pathway_id})"
            url = result.get("url", "")

        return Citation(
            citation_id="",
            source_type=database.lower(),
            source_id=pathway_id,
            formatted=formatted,
            url=url,
            title=name,
            metadata={"database": database},
        )

    def from_protein_result(
        self,
        result: dict[str, Any],
        database: str = "uniprot",
    ) -> Citation:
        """Create citation from protein database result.

        Args:
            result: Protein result dict
            database: Database source

        Returns:
            Protein citation
        """
        accession = result.get("accession", result.get("uniprot_id", ""))
        name = result.get("protein_name", result.get("name", ""))
        gene = result.get("gene_name", result.get("gene", ""))

        if database.lower() == "uniprot":
            formatted = f"UniProt: {name}"
            if gene:
                formatted += f" ({gene})"
            formatted += f" - {accession}"
            url = f"https://www.uniprot.org/uniprot/{accession}"
        elif database.lower() == "string":
            formatted = f"STRING: {name} ({accession})"
            url = f"https://string-db.org/network/{accession}"
        else:
            formatted = f"{database}: {name} ({accession})"
            url = result.get("url", "")

        return Citation(
            citation_id="",
            source_type=database.lower(),
            source_id=accession,
            formatted=formatted,
            url=url,
            title=name,
            metadata={"gene": gene, "database": database},
        )

    def from_tool_call(self, tool_call: ToolCallRecord) -> list[Citation]:
        """Extract citations from a tool call result.

        Args:
            tool_call: Tool call record

        Returns:
            List of citations extracted from results
        """
        citations = []

        if not tool_call.tool_output:
            return citations

        output = tool_call.tool_output
        tool_name = tool_call.tool_name

        # Handle different tool types
        if "pubmed" in tool_name or "literature" in tool_name:
            citations.extend(self._extract_pubmed_citations(output))

        elif "gene_info" in tool_name or "ncbi" in tool_name:
            if isinstance(output, dict) and output.get("found", True):
                citations.append(self.from_gene_info(output))

        elif "reactome" in tool_name or "pathway" in tool_name:
            citations.extend(self._extract_pathway_citations(output, "reactome"))

        elif "kegg" in tool_name:
            citations.extend(self._extract_pathway_citations(output, "kegg"))

        elif "uniprot" in tool_name or "protein" in tool_name:
            citations.extend(self._extract_protein_citations(output))

        elif "string" in tool_name or "interaction" in tool_name:
            # STRING results typically reference the network, not individual proteins
            if isinstance(output, dict):
                if output.get("network_image_url"):
                    citations.append(
                        Citation(
                            citation_id="",
                            source_type="string",
                            source_id="network",
                            formatted=f"STRING Interaction Network",
                            url=output.get("network_image_url", ""),
                            title="STRING Network",
                            metadata={"proteins": output.get("proteins_queried", [])},
                        )
                    )

        return citations

    def to_evidence_source(self, citation: Citation) -> EvidenceSource:
        """Convert citation to EvidenceSource model.

        Args:
            citation: Citation to convert

        Returns:
            EvidenceSource
        """
        return EvidenceSource(
            source_type=citation.source_type,
            source_id=citation.source_id,
            source_url=citation.url,
            description=citation.formatted,
        )

    def _format_article_citation(
        self,
        authors: list[str],
        year: int | None,
        title: str,
        journal: str,
        style: CitationStyle,
    ) -> str:
        """Format an article citation in the specified style."""
        if style == CitationStyle.SIMPLE:
            author_str = authors[0] if authors else "Unknown"
            if len(authors) > 1:
                author_str += " et al."
            year_str = str(year) if year else "n.d."
            return f"{author_str} ({year_str}). {title}"

        elif style == CitationStyle.APA:
            if authors:
                author_str = ", ".join(authors[:6])
                if len(authors) > 6:
                    author_str += ", ... et al."
            else:
                author_str = "Unknown"
            year_str = str(year) if year else "n.d."
            return f"{author_str} ({year_str}). {title}. {journal}."

        elif style == CitationStyle.VANCOUVER:
            author_str = ", ".join(authors[:3])
            if len(authors) > 3:
                author_str += ", et al."
            year_str = str(year) if year else ""
            return f"{author_str}. {title}. {journal} {year_str}."

        elif style == CitationStyle.INLINE:
            author_str = authors[0].split()[-1] if authors else "Unknown"
            if len(authors) > 1:
                author_str += " et al."
            year_str = str(year) if year else "n.d."
            return f"({author_str}, {year_str})"

        elif style == CitationStyle.MARKDOWN:
            author_str = authors[0] if authors else "Unknown"
            if len(authors) > 1:
                author_str += " et al."
            year_str = str(year) if year else "n.d."
            return f"**{author_str} ({year_str})** {title}. *{journal}*"

        return f"{title}"

    def _extract_pubmed_citations(self, output: dict[str, Any]) -> list[Citation]:
        """Extract citations from PubMed tool output."""
        citations = []

        # Handle search results
        articles = output.get("articles", [])
        for article in articles:
            citations.append(self.from_pubmed_result(article))

        # Handle single article
        if not articles and output.get("pmid"):
            citations.append(self.from_pubmed_result(output))

        return citations

    def _extract_pathway_citations(
        self, output: dict[str, Any], database: str
    ) -> list[Citation]:
        """Extract citations from pathway tool output."""
        citations = []

        # Handle enrichment results
        pathways = output.get("pathways", [])
        for pathway in pathways[:10]:  # Limit to top 10
            citations.append(self.from_pathway_result(pathway, database))

        # Handle single pathway
        if not pathways and output.get("pathway_id"):
            citations.append(self.from_pathway_result(output, database))

        return citations

    def _extract_protein_citations(self, output: dict[str, Any]) -> list[Citation]:
        """Extract citations from protein tool output."""
        citations = []

        # Handle batch results
        proteins = output.get("proteins", {})
        if isinstance(proteins, dict):
            for accession, info in list(proteins.items())[:10]:
                if info:
                    info["accession"] = accession
                    citations.append(self.from_protein_result(info))

        # Handle single protein
        if not proteins and output.get("accession"):
            citations.append(self.from_protein_result(output))

        return citations


def generate_inline_citations(
    text: str,
    citations: CitationCollection,
    style: CitationStyle = CitationStyle.INLINE,
) -> str:
    """Add inline citations to text.

    Replaces citation markers [1], [2] etc. with formatted citations.

    Args:
        text: Text with citation markers
        citations: Citation collection
        style: Citation style

    Returns:
        Text with formatted inline citations
    """
    import re

    def replace_marker(match: re.Match) -> str:
        citation_id = match.group(1)
        citation = citations.get(citation_id)
        if citation:
            if style == CitationStyle.MARKDOWN and citation.url:
                return f"[{citation.formatted}]({citation.url})"
            return f"({citation.formatted})"
        return match.group(0)

    # Replace [1], [2] style markers
    pattern = r"\[(\d+)\]"
    return re.sub(pattern, replace_marker, text)
