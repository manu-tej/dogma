# src/quration/hypothesis/connectors/composite.py
"""Composite EdgeSuggester: union the suggestions of several connectors."""

import logging

from quration.hypothesis.connectors.base import EdgeSuggester, SuggestionResult
from quration.hypothesis.graph import Edge, Node

logger = logging.getLogger(__name__)


class CompositeEdgeSuggester:
    """Runs each member suggester and unions results.

    Nodes dedupe by id; edges dedupe by (source_id, target_id, relation) with their
    `suggested_by` provenance merged (an edge backed by both SIGNOR and CollecTRI
    shows both citations). A member that raises contributes nothing.
    """

    def __init__(self, suggesters: list[EdgeSuggester]):
        self._suggesters = suggesters

    def expand(self, seeds: list[str], query: str | None = None) -> SuggestionResult:
        nodes: dict[str, Node] = {}
        edges: dict[tuple[str, str, str], Edge] = {}
        for suggester in self._suggesters:
            try:
                result = suggester.expand(seeds, query)
            except Exception:
                logger.warning("suggester %r failed; skipping", suggester, exc_info=True)
                continue
            for node in result.nodes:
                nodes.setdefault(node.id, node)
            for edge in result.edges:
                key = (edge.source_id, edge.target_id, edge.relation)
                existing = edges.get(key)
                if existing is None:
                    edges[key] = edge
                else:
                    edges[key] = existing.model_copy(
                        update={"suggested_by": existing.suggested_by + edge.suggested_by}
                    )
        return SuggestionResult(nodes=list(nodes.values()), edges=list(edges.values()))

    def check_pair(self, source: str, target: str) -> Edge | None:
        for suggester in self._suggesters:
            try:
                edge = suggester.check_pair(source, target)
            except Exception:
                logger.warning("suggester %r check_pair failed; skipping", suggester, exc_info=True)
                continue
            if edge is not None:
                return edge
        return None
