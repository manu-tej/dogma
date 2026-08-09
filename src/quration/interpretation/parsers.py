"""
Response parsers for extracting structured information from LLM outputs.

This module provides parsers to extract claims, citations, confidence
levels, and other structured data from interpretation responses.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any

from quration.interpretation.models import (
    ClaimType,
    ConfidenceLevel,
    InterpretationClaim,
)


@dataclass
class ParsedSection:
    """A parsed section from a response."""

    title: str
    content: str
    level: int = 1  # Heading level (1-6)


@dataclass
class ParsedCitation:
    """A parsed citation from a response."""

    text: str
    source_type: str  # 'pmid', 'doi', 'url', 'gene', 'pathway', 'tool'
    source_id: str
    context: str = ""  # Surrounding text


@dataclass
class ParsedResponse:
    """Fully parsed interpretation response."""

    raw_text: str
    summary: str = ""
    sections: list[ParsedSection] = field(default_factory=list)
    claims: list[InterpretationClaim] = field(default_factory=list)
    citations: list[ParsedCitation] = field(default_factory=list)
    confidence_statements: list[str] = field(default_factory=list)
    genes_mentioned: list[str] = field(default_factory=list)
    pathways_mentioned: list[str] = field(default_factory=list)


class ResponseParser:
    """Parser for extracting structured information from LLM responses.

    This parser extracts:
    - Sections and their content
    - Claims with confidence levels
    - Citations to literature and databases
    - Gene and pathway mentions

    Example:
        ```python
        parser = ResponseParser()
        parsed = parser.parse(response_text)

        print(f"Found {len(parsed.claims)} claims")
        for claim in parsed.claims:
            print(f"- {claim.claim_text} ({claim.confidence})")
        ```
    """

    # Regex patterns for extraction
    SECTION_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    NUMBERED_SECTION_PATTERN = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*", re.MULTILINE)
    PMID_PATTERN = re.compile(r"PMID[:\s]*(\d{7,8})", re.IGNORECASE)
    DOI_PATTERN = re.compile(r"(10\.\d{4,}/[^\s]+)")
    URL_PATTERN = re.compile(r"https?://[^\s\)]+")

    # Gene symbol pattern (conservative - uppercase letters and numbers)
    GENE_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]{1,10})\b")

    # Pathway patterns
    REACTOME_PATTERN = re.compile(r"R-[A-Z]{3}-\d+")
    KEGG_PATTERN = re.compile(r"hsa\d{5}|KEGG:\s*([^\s,]+)")
    GO_PATTERN = re.compile(r"GO:\d{7}")

    # Confidence indicators
    HIGH_CONFIDENCE_PHRASES = [
        "clearly",
        "strongly suggests",
        "well-established",
        "definitive",
        "conclusive",
        "demonstrated",
        "proven",
        "confirmed",
        "substantial evidence",
    ]
    MEDIUM_CONFIDENCE_PHRASES = [
        "suggests",
        "indicates",
        "likely",
        "appears to",
        "consistent with",
        "supports",
        "evidence suggests",
        "probable",
    ]
    LOW_CONFIDENCE_PHRASES = [
        "may",
        "might",
        "could",
        "possibly",
        "potentially",
        "speculative",
        "unclear",
        "uncertain",
        "limited evidence",
        "preliminary",
    ]

    # Known gene symbols (subset for validation)
    KNOWN_GENES = {
        "TP53",
        "BRCA1",
        "BRCA2",
        "EGFR",
        "MYC",
        "KRAS",
        "PIK3CA",
        "AKT1",
        "PTEN",
        "RB1",
        "CDKN1A",
        "CDKN2A",
        "MDM2",
        "BCL2",
        "BAX",
        "VEGFA",
        "HIF1A",
        "MAPK1",
        "MAPK3",
        "JAK2",
        "STAT3",
        "NFKB1",
        "TNF",
        "IL6",
        "IL1B",
        "TGFB1",
        "WNT1",
        "CTNNB1",
        "APC",
        "NOTCH1",
        "SHH",
        "ERBB2",
        "MET",
        "ALK",
        "ROS1",
        "RET",
        "BRAF",
        "NRAS",
        "HRAS",
        "RAF1",
        "MEK1",
        "ERK1",
        "ATM",
        "ATR",
        "CHEK1",
        "CHEK2",
        "CDK4",
        "CDK6",
        "CCND1",
        "CCNE1",
        "E2F1",
    }

    def parse(self, text: str) -> ParsedResponse:
        """Parse an interpretation response.

        Args:
            text: Raw response text

        Returns:
            ParsedResponse with extracted components
        """
        response = ParsedResponse(raw_text=text)

        # Extract sections
        response.sections = self._extract_sections(text)

        # Extract summary (first section or first paragraph)
        response.summary = self._extract_summary(text, response.sections)

        # Extract citations
        response.citations = self._extract_citations(text)

        # Extract genes and pathways
        response.genes_mentioned = self._extract_genes(text)
        response.pathways_mentioned = self._extract_pathways(text)

        # Extract claims
        response.claims = self._extract_claims(text)

        # Extract confidence statements
        response.confidence_statements = self._extract_confidence_statements(text)

        return response

    def _extract_sections(self, text: str) -> list[ParsedSection]:
        """Extract sections from markdown-formatted text."""
        sections = []

        # Try markdown headers first
        for match in self.SECTION_PATTERN.finditer(text):
            level = len(match.group(1))
            title = match.group(2).strip()

            # Find content until next section
            start = match.end()
            next_match = self.SECTION_PATTERN.search(text, start)
            end = next_match.start() if next_match else len(text)
            content = text[start:end].strip()

            sections.append(ParsedSection(title=title, content=content, level=level))

        # Try numbered sections if no markdown headers
        if not sections:
            for match in self.NUMBERED_SECTION_PATTERN.finditer(text):
                title = match.group(2).strip()
                start = match.end()
                next_match = self.NUMBERED_SECTION_PATTERN.search(text, start)
                end = next_match.start() if next_match else len(text)
                content = text[start:end].strip()

                sections.append(ParsedSection(title=title, content=content, level=1))

        return sections

    def _extract_summary(
        self, text: str, sections: list[ParsedSection]
    ) -> str:
        """Extract summary from response."""
        # Check for a Summary section
        for section in sections:
            if "summary" in section.title.lower():
                return section.content

        # Use first paragraph if no summary section
        paragraphs = text.split("\n\n")
        for para in paragraphs:
            para = para.strip()
            if para and not para.startswith("#") and len(para) > 50:
                return para[:500]

        return ""

    def _extract_citations(self, text: str) -> list[ParsedCitation]:
        """Extract citations from text."""
        citations = []

        # Extract PMIDs
        for match in self.PMID_PATTERN.finditer(text):
            pmid = match.group(1)
            context = self._get_context(text, match.start(), match.end())
            citations.append(
                ParsedCitation(
                    text=f"PMID:{pmid}",
                    source_type="pmid",
                    source_id=pmid,
                    context=context,
                )
            )

        # Extract DOIs
        for match in self.DOI_PATTERN.finditer(text):
            doi = match.group(1).rstrip(".")
            context = self._get_context(text, match.start(), match.end())
            citations.append(
                ParsedCitation(
                    text=doi,
                    source_type="doi",
                    source_id=doi,
                    context=context,
                )
            )

        # Extract PubMed URLs
        for match in self.URL_PATTERN.finditer(text):
            url = match.group()
            if "pubmed" in url.lower():
                # Try to extract PMID from URL
                pmid_match = re.search(r"/(\d{7,8})/?", url)
                if pmid_match:
                    citations.append(
                        ParsedCitation(
                            text=url,
                            source_type="pmid",
                            source_id=pmid_match.group(1),
                            context=self._get_context(text, match.start(), match.end()),
                        )
                    )

        return citations

    def _extract_genes(self, text: str) -> list[str]:
        """Extract gene symbols from text."""
        candidates = set(self.GENE_PATTERN.findall(text))

        # Filter to known genes and high-confidence candidates
        genes = []
        for candidate in candidates:
            if candidate in self.KNOWN_GENES:
                genes.append(candidate)
            elif len(candidate) >= 2 and candidate not in self._common_words():
                # Check if it looks like a gene symbol
                if self._looks_like_gene(candidate):
                    genes.append(candidate)

        return sorted(set(genes))

    def _extract_pathways(self, text: str) -> list[str]:
        """Extract pathway identifiers from text."""
        pathways = []

        # Reactome IDs
        pathways.extend(self.REACTOME_PATTERN.findall(text))

        # KEGG IDs
        for match in self.KEGG_PATTERN.finditer(text):
            kegg_id = match.group(0) if match.group(0).startswith("hsa") else match.group(1)
            if kegg_id:
                pathways.append(kegg_id)

        # GO terms
        pathways.extend(self.GO_PATTERN.findall(text))

        return list(set(pathways))

    def _strip_markdown(self, text: str) -> str:
        """Strip markdown formatting to get clean prose for claim extraction.

        Removes bold/italic markers, headers, list prefixes, and other
        formatting that confuses sentence splitting.
        """
        # Remove markdown headers (### Header -> Header)
        cleaned = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

        # Remove bold/italic markers (**text** -> text, *text* -> text)
        cleaned = re.sub(r'\*{1,3}([^*]+?)\*{1,3}', r'\1', cleaned)

        # Remove numbered list prefixes (1. item -> item)
        cleaned = re.sub(r'^\d+\.\s+', '', cleaned, flags=re.MULTILINE)

        # Remove bullet list prefixes (- item, * item, • item)
        cleaned = re.sub(r'^[-*•]\s+', '', cleaned, flags=re.MULTILINE)

        # Remove checkmarks and X marks (✓, ✅, ❌)
        cleaned = re.sub(r'[✓✅❌]\s*', '', cleaned)

        # Collapse multiple newlines into sentence boundaries
        cleaned = re.sub(r'\n{2,}', '. ', cleaned)

        # Replace single newlines with space (continuation)
        cleaned = re.sub(r'\n', ' ', cleaned)

        # Clean up multiple spaces
        cleaned = re.sub(r'\s{2,}', ' ', cleaned)

        return cleaned.strip()

    def _extract_claims(self, text: str) -> list[InterpretationClaim]:
        """Extract claims from text.

        Combines atomic claim extraction (pattern-based) with sentence-level
        extraction for comprehensive claim coverage.
        """
        claims = []
        seen_statements = set()  # Avoid duplicates

        # Strip markdown before extraction to get clean prose
        clean_text = self._strip_markdown(text)

        # First, extract atomic claims using patterns (on clean text)
        atomic_claims = self._extract_atomic_claims(clean_text)
        for claim in atomic_claims:
            normalized = claim.statement.lower().strip()
            if normalized not in seen_statements:
                seen_statements.add(normalized)
                claims.append(claim)

        # Then extract from sentences (for claims not caught by patterns)
        sentences = self._split_sentences(clean_text)

        for sentence in sentences:
            # Skip short sentences and questions
            if len(sentence) < 20 or sentence.strip().endswith("?"):
                continue

            # Simplify first, then vet — the substantive-claim check must run
            # on the statement that is actually stored. It used to run on the
            # full sentence while the simplified version was stored, so
            # "Statistical robustness — the nominal p=0.001 has not been
            # corrected..." passed the check as a sentence and then the em-dash
            # split stored the two-word label the check would have rejected.
            simplified = self._simplify_to_atomic(sentence)
            if len(sentence) > 200:
                if not simplified:
                    continue
                statement = simplified
            else:
                statement = simplified or sentence

            claim_type = self._determine_claim_type(statement)
            confidence = self._assess_confidence(statement)

            if not self._is_substantive_claim(statement, claim_type):
                continue
            normalized = statement.lower().strip()
            if normalized in seen_statements:
                continue
            seen_statements.add(normalized)
            claims.append(
                InterpretationClaim(
                    claim_type=claim_type,
                    statement=statement,
                    confidence=confidence,
                    evidence=[],
                    genes_mentioned=[],
                    pathways_mentioned=[],
                )
            )

        return claims

    def _extract_atomic_claims(self, text: str) -> list[InterpretationClaim]:
        """Extract atomic biological claims using specific patterns.

        Looks for patterns like:
        - "GENE is upregulated/downregulated"
        - "GENE is significantly expressed"
        - "PATHWAY pathway is activated/enriched"
        - "GENE regulates GENE2"
        """
        claims = []

        # Pattern for gene expression changes (FROM_DATA - directly from input)
        expression_patterns = [
            # "TP53 is upregulated" or "TP53 is significantly upregulated"
            (r'\b([A-Z][A-Z0-9]{1,10})\b\s+is\s+(?:significantly\s+)?(?:up|down)[-\s]?regulated',
             ClaimType.FROM_DATA, ConfidenceLevel.HIGH),
            # "upregulated genes include TP53" or "TP53 shows increased expression"
            (r'\b([A-Z][A-Z0-9]{1,10})\b\s+(?:shows?|exhibits?|has)\s+(?:increased|decreased|elevated|reduced)\s+expression',
             ClaimType.FROM_DATA, ConfidenceLevel.MEDIUM),
            # "TP53 expression is increased"
            (r'\b([A-Z][A-Z0-9]{1,10})\b\s+expression\s+is\s+(?:increased|decreased|elevated|reduced)',
             ClaimType.FROM_DATA, ConfidenceLevel.MEDIUM),
        ]

        # Pattern for pathway involvement (TOOL_RESULT - from pathway analysis)
        pathway_patterns = [
            # "p53 pathway is activated" or "cell cycle pathway is enriched"
            (r'([A-Za-z0-9\s]+?)\s+pathway\s+is\s+(?:activated|inhibited|enriched|significant)',
             ClaimType.TOOL_RESULT, ConfidenceLevel.MEDIUM),
            # "activation of the p53 pathway"
            (r'(?:activation|inhibition|enrichment)\s+of\s+(?:the\s+)?([A-Za-z0-9\s]+?)\s+pathway',
             ClaimType.TOOL_RESULT, ConfidenceLevel.MEDIUM),
        ]

        # Pattern for regulatory relationships (INFERENCE - inferred from data)
        regulatory_patterns = [
            # "TP53 regulates CDKN1A" or "TP53 activates BAX"
            (r'\b([A-Z][A-Z0-9]{1,10})\b\s+(?:regulates?|activates?|inhibits?|suppresses?|induces?)\s+\b([A-Z][A-Z0-9]{1,10})\b',
             ClaimType.INFERENCE, ConfidenceLevel.MEDIUM),
            # "TP53-mediated regulation"
            (r'\b([A-Z][A-Z0-9]{1,10})\b[-\s]mediated\s+(?:regulation|activation|inhibition)',
             ClaimType.INFERENCE, ConfidenceLevel.MEDIUM),
        ]

        # Pattern for functional claims (LITERATURE - from known literature)
        function_patterns = [
            # "TP53 is a tumor suppressor" or "BAX is pro-apoptotic"
            (r'\b([A-Z][A-Z0-9]{1,10})\b\s+is\s+(?:a\s+)?(?:tumor\s+suppressor|oncogene|pro-apoptotic|anti-apoptotic|transcription\s+factor)',
             ClaimType.LITERATURE, ConfidenceLevel.HIGH),
            # "TP53 functions as/in"
            (r'\b([A-Z][A-Z0-9]{1,10})\b\s+(?:functions?|acts?|plays?\s+a\s+role)\s+(?:as|in)\s+([^.]{10,50})',
             ClaimType.LITERATURE, ConfidenceLevel.MEDIUM),
        ]

        # Process all pattern groups. Flags are per-group, and the distinction
        # is load-bearing: the pathway patterns match prose names ("p53 pathway
        # is enriched") and want case-insensitivity, but the gene patterns'
        # entire selectivity is the uppercase symbol class [A-Z][A-Z0-9]{1,10}.
        # A blanket IGNORECASE erased that constraint, so "that", "their" and
        # "the" qualified as gene symbols and every "X activates Y" word triple
        # in prose became a regulatory claim — the first honest benchmark run
        # scored 'NANOG activate their' and 'that activate the' as claims.
        all_patterns = [
            (expression_patterns, "expression", 0),
            (pathway_patterns, "pathway", re.IGNORECASE),
            (regulatory_patterns, "regulatory", 0),
            (function_patterns, "function", 0),
        ]

        for pattern_group, group_name, flags in all_patterns:
            for pattern, claim_type, confidence in pattern_group:
                for match in re.finditer(pattern, text, flags):
                    # Build atomic statement from match
                    statement = self._build_atomic_statement(match, group_name)
                    if statement and len(statement) >= 15 and len(statement) <= 150:
                        claim = InterpretationClaim(
                            claim_type=claim_type,
                            statement=statement,
                            confidence=confidence,
                            evidence=[],
                            genes_mentioned=[],
                            pathways_mentioned=[],
                        )
                        claims.append(claim)

        return claims

    def _build_atomic_statement(self, match: re.Match, pattern_type: str) -> str:
        """Build a clean atomic statement from a regex match."""
        full_match = match.group(0).strip()

        # Clean up the match
        # Remove leading/trailing punctuation
        full_match = re.sub(r'^[^\w]+|[^\w]+$', '', full_match)

        # Capitalize first letter
        if full_match:
            full_match = full_match[0].upper() + full_match[1:]

        return full_match

    def _simplify_to_atomic(self, sentence: str) -> str | None:
        """Try to simplify a long sentence to an atomic claim.

        Extracts the core assertion from complex sentences while preserving
        parenthetical content (like gene lists).
        """
        # If already short enough, return as-is
        if len(sentence) <= 100:
            return sentence.strip()

        # Protect parenthetical content by replacing with placeholder
        paren_content = []
        def save_paren(match: re.Match) -> str:
            paren_content.append(match.group(0))
            return f"__PAREN_{len(paren_content)-1}__"

        protected = re.sub(r'\([^)]+\)', save_paren, sentence)

        # Try to extract the main clause before subordinate markers
        subordinate_markers = [
            r',\s*which\s+',
            r',\s*that\s+',
            r'\s+because\s+',
            r'\s+since\s+',
            r'\s+while\s+',
            r'\s+whereas\s+',
            r'\s+although\s+',
            r'\s*[-–—]\s+',  # em-dash explanations
        ]

        result = None
        for marker in subordinate_markers:
            parts = re.split(marker, protected, maxsplit=1)
            if len(parts) > 1 and len(parts[0]) >= 20:
                result = parts[0].strip()
                break

        # If no subordinate clause found, try first sentence segment
        if result is None:
            # Split on comma only if NOT inside parentheses (already protected)
            comma_split = protected.split(',', 1)
            if len(comma_split) > 1 and len(comma_split[0]) >= 20:
                result = comma_split[0].strip()

        if result is None:
            return None

        # Restore parenthetical content
        for i, paren in enumerate(paren_content):
            result = result.replace(f"__PAREN_{i}__", paren)

        # Final length check - allow up to 200 chars for claims with gene lists
        if len(result) > 200:
            return None

        return result

    def _extract_confidence_statements(self, text: str) -> list[str]:
        """Extract statements about confidence/uncertainty."""
        statements = []
        sentences = self._split_sentences(text)

        confidence_keywords = [
            "confidence",
            "certain",
            "uncertain",
            "clear",
            "unclear",
            "strong",
            "weak",
            "limited",
            "preliminary",
            "conclusive",
            "inconclusive",
        ]

        for sentence in sentences:
            lower = sentence.lower()
            if any(kw in lower for kw in confidence_keywords):
                statements.append(sentence.strip())

        return statements

    def _determine_claim_type(self, sentence: str) -> ClaimType:
        """Determine the source type of a claim.

        ClaimType indicates where the claim's evidence comes from:
        - FROM_DATA: Direct observation from data
        - INFERENCE: LLM-inferred conclusion
        - LITERATURE: Supported by cited literature
        - TOOL_RESULT: Based on tool/database lookup
        """
        lower = sentence.lower()

        # Check for literature references
        if any(w in lower for w in ["pmid", "pubmed", "study", "paper", "published", "reported"]):
            return ClaimType.LITERATURE

        # Check for tool/database references
        if any(w in lower for w in ["database", "tool", "ncbi", "reactome", "kegg", "string"]):
            return ClaimType.TOOL_RESULT

        # Check for direct data observations
        if any(w in lower for w in ["shows", "data", "results", "observed", "measured", "detected"]):
            return ClaimType.FROM_DATA

        # Default to inference for interpretive statements
        return ClaimType.INFERENCE

    def _assess_confidence(self, sentence: str) -> ConfidenceLevel:
        """Assess confidence level of a sentence."""
        lower = sentence.lower()

        # Check high confidence indicators
        if any(phrase in lower for phrase in self.HIGH_CONFIDENCE_PHRASES):
            return ConfidenceLevel.HIGH

        # Check low confidence indicators
        if any(phrase in lower for phrase in self.LOW_CONFIDENCE_PHRASES):
            return ConfidenceLevel.LOW

        # Check medium confidence indicators
        if any(phrase in lower for phrase in self.MEDIUM_CONFIDENCE_PHRASES):
            return ConfidenceLevel.MEDIUM

        # Default to medium
        return ConfidenceLevel.MEDIUM

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Basic sentence splitting
        # Handle common abbreviations
        text = re.sub(r"(\b(?:Dr|Mr|Mrs|Ms|Prof|et al|e\.g|i\.e|vs)\.)\s", r"\1<DOT>", text)

        # Split on sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", text)

        # Restore abbreviations
        sentences = [s.replace("<DOT>", " ") for s in sentences]

        return [s for s in sentences if s.strip()]

    def _get_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """Get context around a match."""
        context_start = max(0, start - window)
        context_end = min(len(text), end + window)
        return text[context_start:context_end].strip()

    def _is_substantive_claim(self, sentence: str, claim_type: ClaimType) -> bool:
        """Check if a sentence represents a substantive claim.

        A substantive claim is an assertive statement making a biological
        claim, not a section header, fragment, or purely descriptive text.
        """
        # Filter out meta-statements
        meta_phrases = [
            "I will",
            "let me",
            "I'll search",
            "I'll look",
            "using the",
            "based on the tool",
            "according to",
            "as shown",
            "as mentioned",
            "see also",
            "note that",
            "for example",
            "for instance",
        ]

        lower = sentence.lower()
        stripped = sentence.strip()

        if any(phrase in lower for phrase in meta_phrases):
            return False

        # Filter out markdown section headers (e.g., "**Title:**" or "### Header")
        if re.match(r'^\*\*[^*]+\*\*:?\s*$', stripped):
            return False
        if re.match(r'^#{1,6}\s+', stripped):
            return False
        # Filter out bullet points that are just labels
        if re.match(r'^[-*•]\s*\*\*[^*]+\*\*\s*$', stripped):
            return False

        # Filter out incomplete fragments (orphaned subordinate clauses)
        if stripped and stripped[0].islower() and not stripped.startswith("p53"):
            return False
        if re.match(r'^(And|Or|But|Also|However|That|Which|Itself|Directly|Its)\s', stripped):
            return False

        # Filter out very short "claims" that are likely fragments
        word_count = len(stripped.split())
        if word_count < 5:
            return False

        # Filter out sentences ending with colon (section headers, not claims)
        if stripped.rstrip('.').endswith(':'):
            return False

        # Filter out gene annotation dumps (e.g. "FOS - log2FC: 0.90 Function:...")
        if re.search(r'log2FC:|Function:', stripped):
            return False

        # Filter out emoji artifacts from markdown
        if re.search(r'[⚠✓✅❌⬆⬇]', stripped):
            return False

        # Filter out trailing double periods (artifact from markdown collapse)
        if stripped.endswith('..'):
            return False

        # Filter out statements that are just lists of items
        if re.match(r'^[-*•\d.]\s*[A-Z][A-Z0-9]+\s*[-–:]\s*', stripped):
            return False

        # Must contain ASSERTIVE biological content, not just mentions
        # Assertive patterns: "X is Y", "X shows Y", "X indicates Y", etc.
        assertive_patterns = [
            r'\bis\s+(?:a\s+)?(?:significantly|strongly|highly)?\s*(?:up|down)?regulated',
            r'\bis\s+(?:activated|inhibited|enriched|expressed)',
            r'\bshows?\s+(?:increased|decreased|elevated|reduced)',
            r'\bindicates?\s+',
            r'\bsuggests?\s+',
            r'\bdemonstrates?\s+',
            r'\breveals?\s+',
            r'\bconfirms?\s+',
            r'\bimplicates?\s+',
            r'\bplays?\s+(?:a\s+)?(?:key|critical|important|major)\s+role',
            r'\bdrives?\s+',
            r'\bpromotes?\s+',
            r'\binhibits?\s+',
            r'\bregulates?\s+',
            r'\bactivates?\s+',
            r'\bmediates?\s+',
            # Noun-phrase claim patterns (common in summaries)
            r'\b(?:up|down)regulation\s+of\b',
            r'\bevidence\s+of\b',
            r'\bconsistent\s+with\b',
            r'\benrichment\s+(?:for|of|in)\b',
            r'\bactivation\s+of\b',
            r'\binhibition\s+of\b',
            r'\btransition\s+(?:from|to|pattern)\b',
            r'\bsignature\s+(?:indicates?|consistent|suggests?)\b',
        ]

        has_assertion = any(re.search(p, lower) for p in assertive_patterns)

        # Also check for statistical significance claims
        has_stats = bool(re.search(r'p\s*[<=]\s*0\.\d+|FDR|q-value|significant', lower))

        # Must have either an assertive statement or statistical backing
        if not (has_assertion or has_stats):
            return False

        # Final check: must mention biological entities
        has_gene = bool(re.search(r'\b[A-Z][A-Z0-9]{1,10}\b', sentence))
        has_pathway = "pathway" in lower or "signaling" in lower
        has_bio_term = any(term in lower for term in [
            "gene", "protein", "expression", "cell", "pathway",
            "signaling", "receptor", "kinase", "transcription"
        ])

        return has_gene or has_pathway or has_bio_term

    def _looks_like_gene(self, candidate: str) -> bool:
        """Check if a string looks like a gene symbol."""
        # Gene symbols are typically 2-10 uppercase letters/numbers
        if not re.match(r"^[A-Z][A-Z0-9]{1,9}$", candidate):
            return False

        # Should not be common abbreviations
        if candidate in {"DNA", "RNA", "ATP", "ADP", "GTP", "GDP", "NAD", "NADH"}:
            return False

        return True

    def _common_words(self) -> set[str]:
        """Get set of common words to filter out."""
        return {
            "THE",
            "AND",
            "FOR",
            "ARE",
            "BUT",
            "NOT",
            "YOU",
            "ALL",
            "CAN",
            "HER",
            "WAS",
            "ONE",
            "OUR",
            "OUT",
            "DNA",
            "RNA",
            "ATP",
            "GTP",
        }


class ClaimExtractor:
    """Specialized extractor for biological claims.

    Focuses on extracting and categorizing biological claims
    with their evidence and confidence levels.
    """

    def __init__(self):
        self._parser = ResponseParser()

    def extract_claims(
        self,
        text: str,
        min_confidence: ConfidenceLevel = ConfidenceLevel.LOW,
    ) -> list[InterpretationClaim]:
        """Extract claims meeting minimum confidence threshold.

        Args:
            text: Response text
            min_confidence: Minimum confidence level

        Returns:
            List of claims meeting threshold
        """
        parsed = self._parser.parse(text)

        confidence_order = {
            ConfidenceLevel.LOW: 0,
            ConfidenceLevel.MEDIUM: 1,
            ConfidenceLevel.HIGH: 2,
        }

        min_level = confidence_order[min_confidence]

        return [
            claim
            for claim in parsed.claims
            if confidence_order.get(claim.confidence, 0) >= min_level
        ]

    def extract_by_type(
        self, text: str, claim_type: ClaimType
    ) -> list[InterpretationClaim]:
        """Extract claims of a specific type.

        Args:
            text: Response text
            claim_type: Type of claims to extract

        Returns:
            List of claims of the specified type
        """
        parsed = self._parser.parse(text)
        return [claim for claim in parsed.claims if claim.claim_type == claim_type]

    def summarize_claims(self, claims: list[InterpretationClaim]) -> dict[str, Any]:
        """Summarize a list of claims.

        Args:
            claims: List of claims

        Returns:
            Summary statistics
        """
        by_type: dict[str, int] = {}
        by_confidence: dict[str, int] = {}

        for claim in claims:
            type_name = claim.claim_type.value
            conf_name = claim.confidence.value

            by_type[type_name] = by_type.get(type_name, 0) + 1
            by_confidence[conf_name] = by_confidence.get(conf_name, 0) + 1

        return {
            "total_claims": len(claims),
            "by_type": by_type,
            "by_confidence": by_confidence,
        }


# Fence language for the machine-readable claims channel. A dedicated language
# tag rather than plain ```json so an unrelated JSON example in the report
# cannot be mistaken for the claims list.
_CLAIMS_BLOCK = re.compile(r"```claims\s*\n(.*?)```", re.DOTALL)


def extract_declared_claims(text: str) -> list[InterpretationClaim] | None:
    """Parse the claims the interpreter declared, or None to trigger fallback.

    Two benchmark runs bracketed why this exists. Regex extraction over prose
    first scored 'NANOG activate their' as a claim; once that was fixed, the
    same extractor pulled ONE claim from a report that plainly asserted all
    four expected findings. Parsing assertions back out of markdown fails in
    whichever direction it isn't currently tuned for, so the model now emits
    its claims as data (see SYSTEM_OUTPUT_FORMAT) and prose parsing is the
    fallback.

    Semantics at the boundaries:

    - No block, malformed JSON, a non-list payload, or a list with no valid
      entry: return None — an instruction failure, the caller falls back.
    - An empty list: return [] — an honest "this report asserts nothing",
      which must NOT be overridden by a regex that would invent claims the
      model deliberately declined to make.
    - The last block wins, so a model that revises mid-report supersedes
      its earlier list.
    """
    blocks = _CLAIMS_BLOCK.findall(text)
    if not blocks:
        return None

    try:
        payload = json.loads(blocks[-1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, list):
        return None

    valid_types = {t.value for t in ClaimType}
    valid_confidence = {c.value for c in ConfidenceLevel}

    claims = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        statement = entry.get("statement")
        if not isinstance(statement, str) or not statement.strip():
            continue
        declared_type = entry.get("type")
        declared_confidence = entry.get("confidence")
        claims.append(
            InterpretationClaim(
                claim_type=ClaimType(declared_type)
                if declared_type in valid_types
                else ClaimType.INFERENCE,
                statement=statement.strip(),
                confidence=ConfidenceLevel(declared_confidence)
                if declared_confidence in valid_confidence
                else ConfidenceLevel.MEDIUM,
                evidence=[],
                genes_mentioned=[],
                pathways_mentioned=[],
            )
        )

    if not claims and payload:
        # A non-empty list in which nothing was usable is a failure to follow
        # the format, not a declaration of no claims.
        return None
    return claims
