"""LlmAuthoringSuggester: the seeded graph IS the LLM's authored causal hypothesis.

In B-lean mode the canvas is the LLM's reasoning, not KG retrieval. This suggester
ignores the derived seeds and authors a full-mechanism skeleton directly from the
query (rich node vocab, generative variability). Grounding stays on-demand per edge
via the separate KGService, so check_pair has no KG to consult and returns None.
"""

from __future__ import annotations

from quration.hypothesis.connectors.base import SuggestionResult
from quration.hypothesis.graph import Edge


class LlmAuthoringSuggester:
    """Primary `/start` suggester for B-lean: author the graph with the LLM."""

    # Skips seed derivation in HypothesisLoop.start() — seeds are unused here.
    uses_seeds = False

    def __init__(self, seeding):
        self._seeding = seeding

    def expand(self, seeds: list[str], query: str | None = None) -> SuggestionResult:
        skeleton = self._seeding.author_skeleton(query or "")
        return SuggestionResult(nodes=list(skeleton.nodes), edges=list(skeleton.edges))

    def check_pair(self, source: str, target: str) -> Edge | None:
        # No KG to consult; grounding is on-demand via the separate KGService.
        return None
