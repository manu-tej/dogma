"""
Method Broker

Main orchestrator for matching user requests to analysis methods.
"""

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from quration.broker.matching_engine import MatchingEngine
from quration.broker.method_registry import MethodRegistry
from quration.broker.models import (
    MatchResult,
    MethodRequest,
    MethodResponse,
    ParsedRequest,
)
from quration.broker.request_parser import RequestParser
from quration.config import QurationConfig

logger = logging.getLogger(__name__)

#: Env var pointing at a built methods_graph Kùzu database. When set (and
#: methods_graph is installed), the broker grounds its registry on that graph
#: instead of the hardcoded defaults.
METHODS_GRAPH_DB_ENV = "QURATION_METHODS_GRAPH_DB"


def _provider_from_env() -> object:
    """Lazily build a methods-graph provider from the environment.

    Returns a provider exposing ``get_methods()`` if ``QURATION_METHODS_GRAPH_DB``
    points at an existing database AND methods_graph is importable; otherwise None,
    so the broker falls back to its hardcoded registry. The import is deferred here
    so quration carries no hard dependency on methods_graph.
    """
    db = os.environ.get(METHODS_GRAPH_DB_ENV)
    if not db:
        return None
    try:
        from methods_graph.provider.quration_provider import KuzuMethodsGraphProvider
    except ImportError:
        logger.warning(
            "%s is set but methods_graph is not installed; "
            "using the default method registry.",
            METHODS_GRAPH_DB_ENV,
        )
        return None
    path = Path(db)
    if not path.exists():
        logger.warning(
            "%s=%s does not exist; using the default method registry.",
            METHODS_GRAPH_DB_ENV,
            db,
        )
        return None
    return KuzuMethodsGraphProvider(path)


class MethodBroker:
    """
    Central broker for routing analysis requests to appropriate methods.

    Integrates:
    - LLM-based request parsing
    - Method registry
    - Intelligent matching engine
    """

    def __init__(
        self,
        config: QurationConfig,
        registry_path: Optional[Path] = None,
        method_provider: object = None,
    ):
        """
        Initialize the method broker.

        Args:
            config: Quration configuration
            registry_path: Optional path to method registry file
            method_provider: Optional methods provider exposing
                ``get_methods() -> list[dict]`` (e.g. methods_graph's
                KuzuMethodsGraphProvider). When omitted, one is built from
                ``QURATION_METHODS_GRAPH_DB`` if set; failing that, the registry
                falls back to its hardcoded defaults.
        """
        self.config = config
        if method_provider is None:
            method_provider = _provider_from_env()
        # Retain the resolved provider so the orchestrator can call its graph/RAG
        # surface (retrieve_context*). None when grounded on the hardcoded registry.
        self.method_provider = method_provider
        self.registry = MethodRegistry(registry_path, provider=method_provider)
        self.parser = RequestParser(config)
        self.matcher = MatchingEngine(self.registry)

    async def process_request(
        self,
        request: MethodRequest,
        context: Optional[Dict[str, Any]] = None,
    ) -> MethodResponse:
        """
        Process an analysis request and return method recommendations.

        Args:
            request: Method request from user
            context: Optional conversation context

        Returns:
            MethodResponse with matched methods
        """
        start_time = time.time()

        # Parse the natural language query
        parsed_request = self.parser.parse_request(request.query, context)

        # Override with any explicitly provided parameters
        if request.data_modality:
            parsed_request.data_modality = request.data_modality

        # Apply user preferences
        parsed_request.preferences["prefer_published"] = request.prefer_published
        parsed_request.preferences["prefer_reproducible"] = request.prefer_reproducible
        parsed_request.preferences["min_quality_score"] = request.min_quality_score

        # Find matching methods
        matches = self.matcher.find_matches(
            parsed_request,
            max_results=request.max_recommendations,
            min_score=request.min_quality_score,
        )

        # Filter by quality preferences
        matches = self._apply_quality_filters(matches, request)

        # Execute if requested and we have a clear winner
        execution_result = None
        if request.execute and matches:
            top_match = matches[0]
            if top_match.recommended and top_match.score >= 0.7:
                # In a full implementation, this would execute the method
                execution_result = {
                    "status": "queued",
                    "method_id": top_match.method.id,
                    "message": "Method execution queued (not implemented in this version)",
                }

        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000

        return MethodResponse(
            request=request,
            parsed_request=parsed_request,
            matches=matches,
            execution_result=execution_result,
            processing_time_ms=processing_time,
        )

    def _apply_quality_filters(
        self, matches: List[MatchResult], request: MethodRequest
    ) -> List[MatchResult]:
        """
        Apply quality filters based on user preferences.

        Args:
            matches: List of match results
            request: Original request with preferences

        Returns:
            Filtered list of matches
        """
        filtered = matches

        if request.prefer_published:
            # Boost peer-reviewed methods
            filtered = sorted(
                filtered,
                key=lambda m: (
                    m.method.quality_metrics.peer_reviewed,
                    m.score,
                ),
                reverse=True,
            )

        if request.prefer_reproducible:
            # Filter out low reproducibility methods
            filtered = [
                m
                for m in filtered
                if m.method.quality_metrics.reproducibility_score >= 0.7
            ]

        return filtered

    def get_method(self, method_id: str):
        """
        Get a specific method by ID.

        Args:
            method_id: Method identifier

        Returns:
            AnalysisMethod if found, None otherwise
        """
        return self.registry.get_method(method_id)

    def list_all_methods(self):
        """
        List all methods in the registry.

        Returns:
            List of all methods
        """
        return self.registry.list_methods()

    def search_methods(self, query: str, max_results: int = 10):
        """
        Search methods by keyword.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of matching methods
        """
        return self.registry.search_methods(query, max_results)

    def get_registry_stats(self):
        """
        Get registry statistics.

        Returns:
            Dictionary with registry stats
        """
        return self.registry.get_stats()

    def add_method(self, method):
        """
        Add a new method to the registry.

        Args:
            method: AnalysisMethod to add
        """
        self.registry.add_method(method)

    def save_registry(self, path: Path):
        """
        Save registry to disk.

        Args:
            path: Path to save registry
        """
        self.registry.save_to_disk(path)

    def explain_match(self, match: MatchResult) -> str:
        """
        Generate a human-readable explanation of why a method was matched.

        Args:
            match: MatchResult to explain

        Returns:
            Formatted explanation string
        """
        explanation = f"**{match.method.name}** (Score: {match.score:.2f})\n\n"

        explanation += "**Why this method matches:**\n"
        for reason in match.match_reasons:
            explanation += f"- {reason}\n"

        if match.potential_issues:
            explanation += "\n**Potential concerns:**\n"
            for issue in match.potential_issues:
                explanation += f"- ⚠️ {issue}\n"

        explanation += f"\n**Quality Metrics:**\n"
        explanation += f"- Reproducibility: {match.method.quality_metrics.reproducibility_score:.2f}\n"
        explanation += f"- Code Available: {'Yes' if match.method.quality_metrics.code_availability else 'No'}\n"
        explanation += f"- Peer Reviewed: {'Yes' if match.method.quality_metrics.peer_reviewed else 'No'}\n"

        if match.method.quality_metrics.community_rating:
            explanation += f"- Community Rating: {match.method.quality_metrics.community_rating}/5.0\n"

        explanation += f"\n**Computational Requirements:**\n"
        if match.method.compute_requirements:
            for key, value in match.method.compute_requirements.items():
                explanation += f"- {key}: {value}\n"

        if match.method.estimated_runtime:
            explanation += f"\n**Estimated Runtime:** {match.method.estimated_runtime}\n"

        return explanation
