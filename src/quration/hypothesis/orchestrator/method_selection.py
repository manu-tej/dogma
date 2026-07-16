"""Broker-backed recommendation of which method fits a proposed test.

Advisory only: produces a `MethodChoice` for `ProposedTest.method`; never runs
anything. Selection is synchronous (called from the sync `next_proposal`), so it
uses the sync `broker.matcher.find_matches` — never the async `process_request`.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol

from quration.broker.models import DataModality, ParsedRequest
from quration.hypothesis.graph import CausalGraph
from quration.hypothesis.orchestrator.checkpoint import MethodChoice, ProposedTest
from quration.hypothesis.orchestrator.graph_grounding import grounding_text, provider_of


class _SupportsMatching(Protocol):
    matcher: object  # exposes find_matches(parsed_request, max_results, min_score) -> list


CONFIDENCE_THRESHOLD = 0.4


IntentAuthor = Callable[[ProposedTest, CausalGraph], str]


def _modality_for_accession(accession: str | None) -> DataModality:
    """Heuristic: GEO series (GSE…) are expression → rna_seq; otherwise unknown.

    Deliberately crude for this slice; refined later via platform annotation.
    """
    if (accession or "").upper().startswith("GSE"):
        return DataModality.RNA_SEQ
    return DataModality.UNKNOWN


def enrich_intent(proposed: ProposedTest, graph: CausalGraph) -> str:
    """Deterministic context-enricher used as the default fallback author.

    Composes a richer query from the edge's node labels, relation, and gene
    symbols. Stands in for an LLM-backed author (deferred — needs an async bridge).
    """
    parts: list[str] = []
    edge = graph.get_edge(proposed.edge_id)
    if edge is not None:
        source = graph.get_node(edge.source_id)
        target = graph.get_node(edge.target_id)
        if source is not None:
            parts.append(source.label)
        if target is not None:
            parts.append(target.label)
        if edge.relation:
            parts.append(edge.relation)
    parts += [
        proposed.source_symbol or "",
        proposed.target_symbol or "",
        "differential expression",
        "correlation",
    ]
    return " ".join(p for p in parts if p)


class BrokerMethodSelector:
    """Selects a `MethodChoice` for a proposed test using a `MethodBroker`."""

    def __init__(
        self,
        broker: _SupportsMatching,
        intent_author: IntentAuthor | None = None,
        threshold: float = CONFIDENCE_THRESHOLD,
    ):
        self._broker = broker
        self._author = intent_author
        self._threshold = threshold

    def select(self, proposed: ProposedTest, graph: CausalGraph) -> MethodChoice | None:
        modality = _modality_for_accession(proposed.data_accession)
        keywords = [
            k for k in (proposed.source_symbol, proposed.target_symbol,
                        "expression", "correlation") if k
        ]
        structural = ParsedRequest(
            original_query=" ".join(keywords),
            data_modality=modality,
            analysis_type="expression correlation",
            keywords=keywords,
            confidence=1.0,
        )
        choice = self._best(structural, source="structural")

        if (choice is None or choice.score < self._threshold) and self._author is not None:
            query = self._author(proposed, graph)
            # modality comes from the accession (not the query), so reuse the structural value
            enriched = ParsedRequest(
                original_query=query,
                data_modality=modality,
                analysis_type="expression correlation",
                keywords=query.split(),
                confidence=1.0,
            )
            alt = self._best(enriched, source="fallback")
            if alt is not None and (choice is None or alt.score > choice.score):
                choice = alt

        # Advisory grounding: attach the chosen method's knowledge-graph neighborhood,
        # seeded by the method name only. Best-effort — never alters the pick.
        # Gene symbols are intentionally NOT seeded: the methods-graph has no gene
        # layer, so they match nothing — passing them would imply an edge-specificity
        # the grounding does not have (the text is a function of the method alone).
        if choice is not None:
            provider = provider_of(self._broker)
            if provider is not None:
                choice.grounding = grounding_text(provider, [choice.name])
        return choice

    def _best(self, parsed: ParsedRequest, *, source: Literal["structural", "fallback"]) -> MethodChoice | None:
        matches = self._broker.matcher.find_matches(parsed, max_results=1, min_score=0.0)
        if not matches:
            return None
        top = matches[0]
        return MethodChoice(
            method_id=top.method.id,
            name=top.method.name,
            score=top.score,
            source=source,
            rationale=(
                f"{top.method.name} fits a {parsed.data_modality.value} test "
                f"(broker score {top.score:.2f})"
            ),
        )
