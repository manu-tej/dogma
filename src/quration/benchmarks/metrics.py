"""Metrics for evaluating interpretation quality.

This module provides metrics calculators for assessing the accuracy,
reliability, and quality of interpretation outputs.
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricResult:
    """Result of a metric calculation."""

    name: str
    value: float
    max_value: float = 1.0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def normalized(self) -> float:
        """Get normalized value (0-1)."""
        if self.max_value == 0:
            return 0.0
        return min(1.0, max(0.0, self.value / self.max_value))

    @property
    def percentage(self) -> float:
        """Get percentage value."""
        return self.normalized * 100


@dataclass
class BenchmarkMetrics:
    """Collection of metrics for a benchmark run."""

    accuracy: MetricResult | None = None
    completeness: MetricResult | None = None
    citation_validity: MetricResult | None = None
    hallucination_rate: MetricResult | None = None
    claim_precision: MetricResult | None = None
    claim_recall: MetricResult | None = None
    tool_utilization: MetricResult | None = None
    confidence_calibration: MetricResult | None = None
    custom_metrics: dict[str, MetricResult] = field(default_factory=dict)

    @property
    def overall_score(self) -> float:
        """Calculate weighted overall score."""
        weights = {
            "accuracy": 0.25,
            "completeness": 0.15,
            "citation_validity": 0.15,
            "hallucination_rate": 0.20,  # Inverted (lower is better)
            "claim_precision": 0.10,
            "claim_recall": 0.10,
            "confidence_calibration": 0.05,
        }

        total_weight = 0.0
        weighted_sum = 0.0

        for metric_name, weight in weights.items():
            metric = getattr(self, metric_name)
            if metric is not None:
                value = metric.normalized
                # Invert hallucination rate (lower is better)
                if metric_name == "hallucination_rate":
                    value = 1.0 - value
                weighted_sum += value * weight
                total_weight += weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {"overall_score": self.overall_score}

        for attr in [
            "accuracy",
            "completeness",
            "citation_validity",
            "hallucination_rate",
            "claim_precision",
            "claim_recall",
            "tool_utilization",
            "confidence_calibration",
        ]:
            metric = getattr(self, attr)
            if metric is not None:
                result[attr] = {
                    "value": metric.value,
                    "normalized": metric.normalized,
                    "percentage": metric.percentage,
                    "details": metric.details,
                }

        if self.custom_metrics:
            result["custom_metrics"] = {
                name: {
                    "value": m.value,
                    "normalized": m.normalized,
                    "details": m.details,
                }
                for name, m in self.custom_metrics.items()
            }

        return result


class AccuracyCalculator:
    """Calculate accuracy of interpretation claims."""

    def calculate(
        self,
        predicted_claims: list[str],
        ground_truth_claims: list[str],
        fuzzy_match: bool = True,
    ) -> MetricResult:
        """Calculate claim accuracy.

        Args:
            predicted_claims: Claims from interpretation
            ground_truth_claims: Expected ground truth claims
            fuzzy_match: Use fuzzy string matching

        Returns:
            MetricResult with accuracy score
        """
        if not ground_truth_claims:
            return MetricResult(
                name="accuracy",
                value=1.0 if not predicted_claims else 0.0,
                details={"note": "No ground truth claims"},
            )

        correct = 0
        matches = []

        for pred in predicted_claims:
            for truth in ground_truth_claims:
                if self._match_claim(pred, truth, fuzzy_match):
                    correct += 1
                    matches.append({"predicted": pred, "ground_truth": truth})
                    break

        accuracy = correct / len(ground_truth_claims)

        return MetricResult(
            name="accuracy",
            value=accuracy,
            details={
                "correct": correct,
                "total": len(ground_truth_claims),
                "predicted_count": len(predicted_claims),
                "matches": matches,
            },
        )

    def _match_claim(self, pred: str, truth: str, fuzzy: bool) -> bool:
        """Check if claims match."""
        pred_lower = pred.lower().strip()
        truth_lower = truth.lower().strip()

        if pred_lower == truth_lower:
            return True

        if not fuzzy:
            return False

        # Fuzzy matching - check for key term overlap
        pred_terms = set(re.findall(r"\b\w{3,}\b", pred_lower))
        truth_terms = set(re.findall(r"\b\w{3,}\b", truth_lower))

        if not truth_terms:
            return False

        overlap = len(pred_terms & truth_terms) / len(truth_terms)
        return overlap >= 0.6


class CompletenessCalculator:
    """Calculate completeness of interpretation coverage."""

    def calculate(
        self,
        covered_aspects: list[str],
        required_aspects: list[str],
    ) -> MetricResult:
        """Calculate coverage completeness.

        Args:
            covered_aspects: Aspects covered by interpretation
            required_aspects: Required aspects

        Returns:
            MetricResult with completeness score
        """
        if not required_aspects:
            return MetricResult(
                name="completeness",
                value=1.0,
                details={"note": "No required aspects"},
            )

        covered_set = set(a.lower() for a in covered_aspects)
        required_set = set(a.lower() for a in required_aspects)

        covered_count = len(covered_set & required_set)
        completeness = covered_count / len(required_set)

        missing = required_set - covered_set
        extra = covered_set - required_set

        return MetricResult(
            name="completeness",
            value=completeness,
            details={
                "covered": covered_count,
                "required": len(required_set),
                "missing": list(missing),
                "extra": list(extra),
            },
        )


class CitationValidityCalculator:
    """Calculate validity of citations in interpretations."""

    def __init__(self, valid_sources: set[str] | None = None):
        """Initialize with optional valid sources.

        Args:
            valid_sources: Set of valid source identifiers
        """
        self.valid_sources = valid_sources or set()

    def calculate(
        self,
        citations: list[dict[str, Any]],
        check_urls: bool = False,
    ) -> MetricResult:
        """Calculate citation validity.

        Args:
            citations: List of citation dicts with source_type, source_id
            check_urls: Check if URLs are valid (not implemented)

        Returns:
            MetricResult with validity score
        """
        if not citations:
            return MetricResult(
                name="citation_validity",
                value=1.0,
                details={"note": "No citations to validate"},
            )

        valid_count = 0
        invalid_citations = []

        for citation in citations:
            source_type = citation.get("source_type", "")
            source_id = citation.get("source_id", "")

            # Check if in valid sources set
            key = f"{source_type}:{source_id}"
            if self.valid_sources and key in self.valid_sources:
                valid_count += 1
                continue

            # Basic validation rules
            if self._validate_citation(source_type, source_id):
                valid_count += 1
            else:
                invalid_citations.append(citation)

        validity = valid_count / len(citations)

        return MetricResult(
            name="citation_validity",
            value=validity,
            details={
                "valid": valid_count,
                "total": len(citations),
                "invalid": invalid_citations,
            },
        )

    def _validate_citation(self, source_type: str, source_id: str) -> bool:
        """Basic citation validation."""
        if not source_type or not source_id:
            return False

        # PMID validation
        if source_type.lower() in ["pmid", "pubmed"]:
            return source_id.isdigit() and len(source_id) >= 1

        # DOI validation
        if source_type.lower() == "doi":
            return source_id.startswith("10.")

        # Gene ID validation
        if source_type.lower() in ["ncbi_gene", "gene_id"]:
            return source_id.isdigit()

        # UniProt validation
        if source_type.lower() == "uniprot":
            return bool(re.match(r"^[A-Z][0-9][A-Z0-9]{3}[0-9]$", source_id.upper()))

        # Pathway IDs
        if source_type.lower() in ["reactome", "kegg"]:
            return len(source_id) >= 3

        return True  # Accept unknown types


class HallucinationDetector:
    """Detect hallucinations in interpretation outputs."""

    def __init__(
        self,
        known_genes: set[str] | None = None,
        known_pathways: set[str] | None = None,
    ):
        """Initialize with known valid entities.

        Args:
            known_genes: Set of valid gene symbols
            known_pathways: Set of valid pathway names/IDs
        """
        self.known_genes = known_genes or set()
        self.known_pathways = known_pathways or set()

    def calculate(
        self,
        claims: list[dict[str, Any]],
        mentioned_genes: list[str],
        mentioned_pathways: list[str],
        input_genes: list[str] | None = None,
    ) -> MetricResult:
        """Calculate hallucination rate.

        Args:
            claims: List of claim dicts
            mentioned_genes: Genes mentioned in interpretation
            mentioned_pathways: Pathways mentioned
            input_genes: Genes provided as input

        Returns:
            MetricResult with hallucination rate (lower is better)
        """
        hallucinations = []
        total_entities = 0

        # Check genes
        input_gene_set = set(g.upper() for g in (input_genes or []))

        for gene in mentioned_genes:
            total_entities += 1
            gene_upper = gene.upper()

            # Not a hallucination if in input or known genes
            if gene_upper in input_gene_set:
                continue
            if self.known_genes and gene_upper in self.known_genes:
                continue

            # Check if it looks like a valid gene symbol
            if not self._is_valid_gene_pattern(gene):
                hallucinations.append({"type": "gene", "value": gene})

        # Check pathways
        for pathway in mentioned_pathways:
            total_entities += 1

            if self.known_pathways and pathway in self.known_pathways:
                continue

            # Basic pathway validation
            if not self._is_valid_pathway_pattern(pathway):
                hallucinations.append({"type": "pathway", "value": pathway})

        # Calculate rate
        if total_entities == 0:
            rate = 0.0
        else:
            rate = len(hallucinations) / total_entities

        return MetricResult(
            name="hallucination_rate",
            value=rate,
            details={
                "hallucinations": hallucinations,
                "total_entities": total_entities,
                "hallucination_count": len(hallucinations),
            },
        )

    def _is_valid_gene_pattern(self, gene: str) -> bool:
        """Check if string looks like a valid gene symbol."""
        # Gene symbols are typically 1-10 uppercase letters/numbers
        if not gene:
            return False
        # Common patterns: TP53, BRCA1, IL6, HLA-A
        return bool(re.match(r"^[A-Z][A-Z0-9\-]{0,15}$", gene.upper()))

    def _is_valid_pathway_pattern(self, pathway: str) -> bool:
        """Check if string looks like a valid pathway."""
        if not pathway or len(pathway) < 3:
            return False
        # Pathways should have reasonable length
        return len(pathway) < 200


class ClaimPrecisionRecallCalculator:
    """Calculate precision and recall for claim extraction.

    Uses fuzzy matching to compare predicted claims against expected claims,
    since exact string matching is too strict for natural language claims.
    """

    # Gene name aliases for normalization (maps alternate names to canonical)
    # Keys should be lowercase with no hyphens/underscores (normalized form)
    GENE_ALIASES: dict[str, str] = {
        # p53 family
        "p53": "tp53", "trp53": "tp53",
        "p63": "tp63", "p73": "tp73",
        # Common aliases
        "her2": "erbb2", "neu": "erbb2",
        "ras": "kras",  # Often used interchangeably
        "erk": "mapk1", "erk1": "mapk3", "erk2": "mapk1",
        "akt": "akt1",
        "mek": "map2k1", "mek1": "map2k1",
        "nfkb": "nfkb1", "nfkb": "nfkb1",
        "tgfb": "tgfb1", "tgfb1": "tgfb1", "tgfbeta": "tgfb1",
        "vegf": "vegfa",
        "il6": "il6", "il1b": "il1b", "il1": "il1b",
        "bcl2": "bcl2",
        "cmyc": "myc",
    }

    # Canonical term mappings - all variants map to same canonical form
    # This allows "increased expression" to match "upregulated"
    CANONICAL_TERMS: dict[str, str] = {
        # Upregulation synonyms -> canonical "up"
        "upregulated": "up", "upregulation": "up",
        "increased": "up", "elevated": "up", "higher": "up",
        "activated": "up", "overexpressed": "up", "induced": "up",
        # Downregulation synonyms -> canonical "down"
        "downregulated": "down", "downregulation": "down",
        "decreased": "down", "reduced": "down", "lower": "down",
        "inhibited": "down", "suppressed": "down", "underexpressed": "down",
        # Pathway terms -> canonical "pathway"
        "pathway": "pathway", "signaling": "pathway", "cascade": "pathway",
        # Expression terms -> canonical "expression"
        "expression": "expression", "expressed": "expression",
        "transcript": "expression", "mrna": "expression",
    }

    def __init__(self, similarity_threshold: float = 0.4):
        """Initialize with similarity threshold.

        Args:
            similarity_threshold: Minimum similarity (0-1) for a match.
                0.4 means 40% of key terms must overlap (lowered from 0.5
                to allow more semantic flexibility).
        """
        self.similarity_threshold = similarity_threshold

    def _normalize_gene(self, gene: str) -> str:
        """Normalize gene name to canonical form."""
        gene_lower = gene.lower().replace("-", "").replace("_", "")
        return self.GENE_ALIASES.get(gene_lower, gene_lower)

    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text into significant words with normalization.

        Applies:
        1. Gene name normalization (TP53 = p53)
        2. Canonical term mapping (upregulated = increased = elevated)
        """
        # Lowercase and extract words 3+ characters
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())

        # Extract gene symbols - both uppercase (TP53) and common lowercase forms (p53)
        genes_upper = re.findall(r'\b[A-Z][A-Z0-9]{1,10}\b', text)
        # Also catch lowercase gene patterns like p53, p21, il6
        genes_lower = re.findall(r'\b[a-z]{1,3}\d{1,3}\b', text.lower())

        # Normalize all genes
        normalized_genes = {self._normalize_gene(g) for g in genes_upper}
        normalized_genes |= {self._normalize_gene(g) for g in genes_lower}

        # Combine words with normalized genes
        tokens = set(words) | normalized_genes

        # Map terms to canonical forms for better matching
        canonical = set()
        for token in tokens:
            canonical.add(token)  # Keep original
            if token in self.CANONICAL_TERMS:
                canonical.add(self.CANONICAL_TERMS[token])  # Add canonical form

        return canonical

    def _fuzzy_match(self, predicted: str, expected: str) -> bool:
        """Check if predicted claim fuzzy-matches expected claim.

        Uses multiple matching strategies:
        1. Token overlap with normalization and synonyms
        2. Key entity matching (genes, pathways)
        3. Substring containment for short expected claims
        """
        expected_tokens = self._tokenize(expected)
        predicted_tokens = self._tokenize(predicted)

        if not expected_tokens:
            return False

        # Strategy 1: Standard token overlap
        overlap = len(expected_tokens & predicted_tokens)
        token_ratio = overlap / len(expected_tokens)

        if token_ratio >= self.similarity_threshold:
            return True

        # Strategy 2: Key entity matching (genes are critical)
        expected_genes = set(self._normalize_gene(g) for g in
                           re.findall(r'\b[A-Z][A-Z0-9]{1,10}\b', expected))
        predicted_genes = set(self._normalize_gene(g) for g in
                            re.findall(r'\b[A-Z][A-Z0-9]{1,10}\b', predicted))

        if expected_genes:
            gene_overlap = len(expected_genes & predicted_genes)
            gene_ratio = gene_overlap / len(expected_genes)

            # If most genes match and some other content matches, it's a match
            if gene_ratio >= 0.5 and token_ratio >= 0.3:
                return True

        # Strategy 3: Check for core phrase containment
        # Useful when expected is short like "p53 is upregulated"
        expected_lower = expected.lower().strip()
        predicted_lower = predicted.lower().strip()

        # Normalize both for comparison
        expected_normalized = re.sub(r'\s+', ' ', expected_lower)
        predicted_normalized = re.sub(r'\s+', ' ', predicted_lower)

        # Short claims (< 50 chars) can use substring matching
        if len(expected_normalized) < 50:
            # Check if key phrase is contained
            if expected_normalized in predicted_normalized:
                return True

            # Check if normalized version matches (handling synonyms)
            expected_key = self._extract_key_phrase(expected)
            predicted_key = self._extract_key_phrase(predicted)
            if expected_key and predicted_key:
                if expected_key == predicted_key:
                    return True

        # Strategy 4: Bidirectional matching for recall
        # If predicted is much longer, check if expected content is there
        if len(predicted) > 2 * len(expected):
            reverse_ratio = len(expected_tokens & predicted_tokens) / max(1, len(expected_tokens))
            if reverse_ratio >= 0.6:  # 60% of expected terms are in predicted
                return True

        return False

    def _extract_key_phrase(self, text: str) -> str | None:
        """Extract the core biological assertion from a claim.

        Returns normalized key phrase like 'gene:tp53 state:upregulated'
        """
        text_lower = text.lower()

        # Extract gene
        genes = re.findall(r'\b[A-Z][A-Z0-9]{1,10}\b', text)
        gene = self._normalize_gene(genes[0]) if genes else None

        # Extract state/action
        state = None
        if any(w in text_lower for w in ['upregulated', 'increased', 'elevated', 'activated', 'overexpressed']):
            state = 'upregulated'
        elif any(w in text_lower for w in ['downregulated', 'decreased', 'reduced', 'inhibited', 'suppressed']):
            state = 'downregulated'
        elif 'pathway' in text_lower or 'signaling' in text_lower:
            if 'activated' in text_lower or 'enriched' in text_lower:
                state = 'pathway_activated'
            elif 'inhibited' in text_lower:
                state = 'pathway_inhibited'

        if gene and state:
            return f"gene:{gene} state:{state}"
        return None

    def _find_matches(
        self, predicted_claims: list[str], relevant_claims: list[str]
    ) -> tuple[int, list[tuple[str, str]]]:
        """Find matching claims using fuzzy matching.

        Returns:
            Tuple of (match_count, list of (predicted, relevant) match pairs)
        """
        matched_relevant = set()
        matches = []

        for predicted in predicted_claims:
            for i, relevant in enumerate(relevant_claims):
                if i not in matched_relevant and self._fuzzy_match(predicted, relevant):
                    matched_relevant.add(i)
                    matches.append((predicted, relevant))
                    break

        return len(matches), matches

    def calculate_precision(
        self,
        predicted_claims: list[str],
        relevant_claims: list[str],
    ) -> MetricResult:
        """Calculate precision (correct / predicted) using fuzzy matching.

        Args:
            predicted_claims: Extracted claims
            relevant_claims: Relevant/correct claims

        Returns:
            MetricResult with precision
        """
        if not predicted_claims:
            return MetricResult(
                name="claim_precision",
                value=1.0 if not relevant_claims else 0.0,
                details={"note": "No predicted claims"},
            )

        correct, matches = self._find_matches(predicted_claims, relevant_claims)
        precision = correct / len(predicted_claims)

        return MetricResult(
            name="claim_precision",
            value=precision,
            details={
                "correct": correct,
                "predicted": len(predicted_claims),
                "matches": [(p[:50], r[:50]) for p, r in matches[:5]],  # First 5 matches
            },
        )

    def calculate_recall(
        self,
        predicted_claims: list[str],
        relevant_claims: list[str],
    ) -> MetricResult:
        """Calculate recall (correct / relevant) using fuzzy matching.

        Args:
            predicted_claims: Extracted claims
            relevant_claims: Relevant/correct claims

        Returns:
            MetricResult with recall
        """
        if not relevant_claims:
            return MetricResult(
                name="claim_recall",
                value=1.0,
                details={"note": "No relevant claims"},
            )

        found, matches = self._find_matches(predicted_claims, relevant_claims)
        recall = found / len(relevant_claims)

        return MetricResult(
            name="claim_recall",
            value=recall,
            details={
                "found": found,
                "relevant": len(relevant_claims),
                "matched_claims": [r[:50] for _, r in matches],
            },
        )


class ConfidenceCalibrationCalculator:
    """Calculate confidence score calibration."""

    def calculate(
        self,
        predicted_confidences: list[float],
        actual_correctness: list[bool],
    ) -> MetricResult:
        """Calculate calibration error.

        Args:
            predicted_confidences: Confidence scores (0-1)
            actual_correctness: Whether predictions were correct

        Returns:
            MetricResult with calibration score (1 - error)
        """
        if len(predicted_confidences) != len(actual_correctness):
            raise ValueError("Confidence and correctness lists must match")

        if not predicted_confidences:
            return MetricResult(
                name="confidence_calibration",
                value=1.0,
                details={"note": "No predictions to calibrate"},
            )

        # Bin predictions and calculate calibration error
        bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
        bin_data = {i: {"count": 0, "correct": 0, "conf_sum": 0.0} for i in range(len(bins) - 1)}

        for conf, correct in zip(predicted_confidences, actual_correctness):
            for i in range(len(bins) - 1):
                if bins[i] <= conf < bins[i + 1] or (i == len(bins) - 2 and conf == 1.0):
                    bin_data[i]["count"] += 1
                    bin_data[i]["correct"] += int(correct)
                    bin_data[i]["conf_sum"] += conf
                    break

        # Calculate Expected Calibration Error
        total_samples = len(predicted_confidences)
        ece = 0.0

        for bin_idx, data in bin_data.items():
            if data["count"] > 0:
                avg_conf = data["conf_sum"] / data["count"]
                accuracy = data["correct"] / data["count"]
                weight = data["count"] / total_samples
                ece += weight * abs(accuracy - avg_conf)

        # Convert to calibration score (1 - error)
        calibration_score = 1.0 - ece

        return MetricResult(
            name="confidence_calibration",
            value=calibration_score,
            details={
                "expected_calibration_error": ece,
                "bin_data": bin_data,
                "total_samples": total_samples,
            },
        )


class ToolUtilizationCalculator:
    """Calculate tool utilization effectiveness."""

    def calculate(
        self,
        tool_calls: list[dict[str, Any]],
        expected_tools: list[str] | None = None,
    ) -> MetricResult:
        """Calculate tool utilization score.

        Args:
            tool_calls: List of tool call records
            expected_tools: Tools that should have been used

        Returns:
            MetricResult with utilization score
        """
        if not tool_calls:
            return MetricResult(
                name="tool_utilization",
                value=0.0 if expected_tools else 1.0,
                details={"note": "No tool calls made"},
            )

        # Calculate success rate
        successful = sum(1 for t in tool_calls if t.get("status") == "success")
        success_rate = successful / len(tool_calls)

        # Calculate coverage of expected tools
        used_tools = set(t.get("tool_name", "") for t in tool_calls)
        coverage = 1.0

        if expected_tools:
            expected_set = set(expected_tools)
            covered = len(used_tools & expected_set)
            coverage = covered / len(expected_set)

        # Combined score
        utilization = (success_rate * 0.6) + (coverage * 0.4)

        return MetricResult(
            name="tool_utilization",
            value=utilization,
            details={
                "success_rate": success_rate,
                "tool_coverage": coverage,
                "tools_used": list(used_tools),
                "expected_tools": expected_tools,
                "successful_calls": successful,
                "total_calls": len(tool_calls),
            },
        )
