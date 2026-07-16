"""
Matching Engine

Matches user requests to appropriate analysis methods using heuristic scoring.
"""

from typing import List

from quration.broker.method_registry import MethodRegistry
from quration.broker.models import (
    AnalysisMethod,
    DataModality,
    MatchResult,
    ParsedRequest,
)


class MatchingEngine:
    """
    Matches parsed requests to appropriate analysis methods.
    """

    def __init__(self, registry: MethodRegistry):
        """
        Initialize the matching engine.

        Args:
            registry: Method registry to search
        """
        self.registry = registry

    def find_matches(
        self,
        parsed_request: ParsedRequest,
        max_results: int = 5,
        min_score: float = 0.3,
    ) -> List[MatchResult]:
        """
        Find matching methods for a parsed request.

        Args:
            parsed_request: Structured request to match
            max_results: Maximum number of results to return
            min_score: Minimum match score threshold

        Returns:
            List of MatchResult objects, ranked by score
        """
        matches = []

        # Score each method in the registry
        for method in self.registry.list_methods(status="active"):
            match_result = self._score_method(method, parsed_request)

            # Only include if above threshold
            if match_result.score >= min_score:
                matches.append(match_result)

        # Sort by score (descending)
        matches.sort(key=lambda x: x.score, reverse=True)

        # Assign ranks
        for i, match in enumerate(matches[:max_results], 1):
            match.rank = i

        return matches[:max_results]

    def _score_method(
        self, method: AnalysisMethod, request: ParsedRequest
    ) -> MatchResult:
        """
        Score a single method against a request.

        Args:
            method: Method to score
            request: Parsed request

        Returns:
            MatchResult with score and explanations
        """
        # Component scores
        modality_score = self._score_modality_match(method, request)
        analysis_type_score = self._score_analysis_type(method, request)
        tool_match_score = self._score_tool_match(method, request)
        organism_score = self._score_organism_compatibility(method, request)
        sample_count_score = self._score_sample_count(method, request)
        keyword_score = self._score_keywords(method, request)

        # Quality scores
        quality_score = self._score_quality(method, request)

        # Compute weighted relevance score
        relevance_score = (
            modality_score * 0.30
            + analysis_type_score * 0.25
            + tool_match_score * 0.20
            + organism_score * 0.10
            + sample_count_score * 0.05
            + keyword_score * 0.10
        )

        # Compute compatibility score (requirements met)
        compatibility_score = (
            modality_score * 0.5 + organism_score * 0.3 + sample_count_score * 0.2
        )

        # Overall score combines relevance, quality, and compatibility
        overall_score = (
            relevance_score * 0.5 + quality_score * 0.3 + compatibility_score * 0.2
        )

        # Generate match reasons and issues
        match_reasons = self._generate_match_reasons(
            method, request, modality_score, analysis_type_score, tool_match_score
        )
        potential_issues = self._identify_potential_issues(method, request)

        # Determine if recommended
        recommended = (
            overall_score >= 0.6
            and modality_score > 0.5
            and len(potential_issues) == 0
        )

        return MatchResult(
            method=method,
            score=overall_score,
            relevance_score=relevance_score,
            quality_score=quality_score,
            compatibility_score=compatibility_score,
            match_reasons=match_reasons,
            potential_issues=potential_issues,
            recommended=recommended,
            rank=0,  # Will be set later
        )

    def _score_modality_match(
        self, method: AnalysisMethod, request: ParsedRequest
    ) -> float:
        """Score how well the method's supported modalities match the request."""
        if request.data_modality == DataModality.UNKNOWN:
            return 0.5  # Neutral score if modality is unknown

        if request.data_modality in method.supported_modalities:
            return 1.0

        # Check for related modalities
        related_modalities = {
            DataModality.SINGLE_CELL_RNA: [DataModality.RNA_SEQ],
            DataModality.RNA_SEQ: [DataModality.SINGLE_CELL_RNA],
        }

        if request.data_modality in related_modalities:
            for related in related_modalities[request.data_modality]:
                if related in method.supported_modalities:
                    return 0.7

        return 0.0

    def _score_analysis_type(
        self, method: AnalysisMethod, request: ParsedRequest
    ) -> float:
        """Score how well the method matches the requested analysis type."""
        analysis_type = request.analysis_type.lower()
        method_desc = method.description.lower()
        method_name = method.name.lower()
        method_category = method.category.value.lower()

        # Exact matches
        if analysis_type in method_name or analysis_type in method_category:
            return 1.0

        # Partial matches in description
        if analysis_type in method_desc:
            return 0.8

        # Keyword matches
        analysis_keywords = analysis_type.split()
        matches = sum(
            1
            for keyword in analysis_keywords
            if keyword in method_desc or keyword in method_name
        )

        if len(analysis_keywords) > 0:
            return min(1.0, matches / len(analysis_keywords) * 0.7)

        return 0.0

    def _score_tool_match(
        self, method: AnalysisMethod, request: ParsedRequest
    ) -> float:
        """Score if a specific tool was requested and this method uses it."""
        if not request.specific_tools:
            return 0.5  # Neutral if no specific tool requested

        method_name_lower = method.name.lower()
        method_id_lower = method.id.lower()

        for tool in request.specific_tools:
            tool_lower = tool.lower()
            if tool_lower in method_name_lower or tool_lower in method_id_lower:
                return 1.0

        return 0.0

    def _score_organism_compatibility(
        self, method: AnalysisMethod, request: ParsedRequest
    ) -> float:
        """Score organism compatibility."""
        if request.organism is None:
            return 1.0  # No constraint

        if method.supported_organisms is None:
            return 1.0  # Method works with any organism

        organism_lower = request.organism.lower()
        if any(organism_lower in org.lower() for org in method.supported_organisms):
            return 1.0

        return 0.3  # Might still work, but not explicitly supported

    def _score_sample_count(
        self, method: AnalysisMethod, request: ParsedRequest
    ) -> float:
        """Score sample count compatibility."""
        if request.sample_count is None:
            return 1.0  # No constraint

        sample_count = request.sample_count

        # Check minimum samples
        if method.min_samples and sample_count < method.min_samples:
            return 0.2  # Below minimum

        # Check maximum samples
        if method.max_samples and sample_count > method.max_samples:
            return 0.5  # Above maximum (might be slow)

        return 1.0  # Within range

    def _score_keywords(self, method: AnalysisMethod, request: ParsedRequest) -> float:
        """Score based on keyword matches."""
        if not request.keywords:
            return 0.5

        method_text = (
            f"{method.name} {method.description} {' '.join(method.tags)}"
        ).lower()

        matches = sum(1 for keyword in request.keywords if keyword.lower() in method_text)

        if len(request.keywords) > 0:
            return matches / len(request.keywords)

        return 0.5

    def _score_quality(self, method: AnalysisMethod, request: ParsedRequest) -> float:
        """Score method quality based on metrics and preferences."""
        metrics = method.quality_metrics

        # Base quality score
        quality_score = (
            metrics.reproducibility_score * 0.4
            + metrics.documentation_quality * 0.2
            + (1.0 if metrics.code_availability else 0.0) * 0.2
            + (1.0 if metrics.peer_reviewed else 0.5) * 0.2
        )

        # Apply user preferences if available
        prefer_published = request.preferences.get("prefer_published", True)
        prefer_reproducible = request.preferences.get("prefer_reproducible", True)

        if prefer_published and not metrics.peer_reviewed:
            quality_score *= 0.8

        if prefer_reproducible and metrics.reproducibility_score < 0.8:
            quality_score *= 0.9

        return quality_score

    def _generate_match_reasons(
        self,
        method: AnalysisMethod,
        request: ParsedRequest,
        modality_score: float,
        analysis_type_score: float,
        tool_match_score: float,
    ) -> List[str]:
        """Generate human-readable match reasons."""
        reasons = []

        if modality_score >= 0.8:
            reasons.append(
                f"Supports {request.data_modality.value} data modality"
            )

        if analysis_type_score >= 0.8:
            reasons.append(
                f"Well-suited for {request.analysis_type} analysis"
            )

        if tool_match_score == 1.0 and request.specific_tools:
            reasons.append(
                f"Uses requested tool(s): {', '.join(request.specific_tools)}"
            )

        if method.quality_metrics.peer_reviewed:
            reasons.append("Peer-reviewed method")

        if method.quality_metrics.reproducibility_score >= 0.9:
            reasons.append("Highly reproducible (score >= 0.9)")

        if method.quality_metrics.community_rating and method.quality_metrics.community_rating >= 4.5:
            reasons.append(
                f"Highly rated by community ({method.quality_metrics.community_rating}/5.0)"
            )

        return reasons

    def _identify_potential_issues(
        self, method: AnalysisMethod, request: ParsedRequest
    ) -> List[str]:
        """Identify potential issues or concerns."""
        issues = []

        # Check sample count requirements
        if request.sample_count and method.min_samples:
            if request.sample_count < method.min_samples:
                issues.append(
                    f"Requires minimum {method.min_samples} samples, but request has {request.sample_count}"
                )

        # Check organism compatibility
        if (
            request.organism
            and method.supported_organisms
            and request.organism.lower()
            not in [org.lower() for org in method.supported_organisms]
        ):
            issues.append(
                f"Organism '{request.organism}' not explicitly supported (supports: {', '.join(method.supported_organisms)})"
            )

        # Check for high-severity caveats
        for caveat in method.caveats:
            if caveat.severity == "high":
                issues.append(f"Caveat: {caveat.description}")

        # Check for critical assumptions
        critical_assumptions = [a for a in method.assumptions if a.critical]
        if critical_assumptions:
            for assumption in critical_assumptions[:2]:  # Limit to first 2
                issues.append(f"Assumes: {assumption.description}")

        return issues
