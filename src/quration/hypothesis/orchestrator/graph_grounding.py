"""Defensive access to a methods provider's graph/RAG surface.

The methods-graph provider exposes retrieve_context_for_keywords(); the hardcoded
fallback registry does not. Every call here is best-effort and advisory: any
failure or empty result yields None so method selection never breaks.
"""
from __future__ import annotations


def provider_of(broker: object) -> object | None:
    """Return the broker's methods provider iff it exposes the RAG capability."""
    provider = getattr(broker, "method_provider", None)
    if provider is None:
        return None
    if not callable(getattr(provider, "retrieve_context_for_keywords", None)):
        return None
    return provider


# 2 hops so the grounding reaches a method's inherited assumptions:
#   Method -USES_STATISTICAL_METHOD-> StatisticalMethod -REQUIRES_ASSUMPTION-> Assumption
# A 1-hop seed reaches the statistical-method crosslink but not its assumptions.
GROUNDING_HOPS = 2


def grounding_text(
    provider: object, keywords: list[str], *, k_hops: int = GROUNDING_HOPS
) -> str | None:
    """RAG text for the given keywords, or None on empty/error.

    Treats the returned text as an opaque blob (no parsing) — robust to the
    provider's evolving to_rag_text format.
    """
    try:
        text = provider.retrieve_context_for_keywords(keywords, k_hops=k_hops)
    except Exception:
        return None
    return text or None
