# src/quration/hypothesis/orchestrator/grounding_eval.py
"""Methods-graph grounding: method + PER-ASSUMPTION preconditions for an edge.

Wires the previously-dead `method_preconditions()` seam (quration_provider.py:179):
each assumption becomes a structured AssumptionOutcome carrying its checkable flag,
threshold, and provenance. Grounding is methodological, not biological proof.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from quration.hypothesis.orchestrator.evaluation_plan import AssumptionOutcome
from quration.hypothesis.orchestrator.relation_method_map import keywords_for_relation

logger = logging.getLogger(__name__)

GROUNDED = "GROUNDED"
PARTIALLY_GROUNDED = "PARTIALLY_GROUNDED"
COVERAGE_GAP = "COVERAGE_GAP"
NOT_EVALUABLE = "NOT_EVALUABLE"
_MAX_CANDIDATES = 8


class GroundingResult(BaseModel):
    verdict: str
    method_id: str | None = None
    assumptions: list[AssumptionOutcome] = Field(default_factory=list)
    summary: str = ""


def ground_edge(provider, relation: str | None) -> GroundingResult:
    keywords = keywords_for_relation(relation)
    if not keywords:
        return GroundingResult(verdict=NOT_EVALUABLE,
                               summary="Definitional / not measurable by an analysis method.")
    if provider is None:
        return GroundingResult(verdict=COVERAGE_GAP,
                               summary="No methods-graph provider configured.")
    try:
        ids = provider.resolve_method_ids(keywords)
    except Exception as exc:  # provider/db hiccup -> honest gap, never crash
        logger.warning("resolve_method_ids failed: %s", exc)
        ids = []
    if not ids:
        return GroundingResult(verdict=COVERAGE_GAP, summary="No method matches the readout (coverage gap).")

    fallback_id = None
    for mid in ids[:_MAX_CANDIDATES]:
        try:
            pre = provider.method_preconditions(mid)
        except KeyError:
            continue
        except Exception as exc:
            logger.warning("method_preconditions failed for %s: %s", mid, exc)
            continue
        if fallback_id is None:
            fallback_id = mid
        outcomes = [
            AssumptionOutcome(
                name=a.get("name", ""), checkable=str(a.get("checkable", "") or ""),
                threshold=a.get("threshold"), via=list(a.get("via", [])),
            )
            for a in pre.get("assumptions", [])
        ]
        if outcomes:
            return GroundingResult(
                verdict=GROUNDED, method_id=mid, assumptions=outcomes,
                summary=f"Grounded via {mid}: {len(outcomes)} assumption(s) that must hold.")
    return GroundingResult(verdict=COVERAGE_GAP, method_id=fallback_id,
                           summary="No grounded assumptions in the methods graph yet (coverage gap).")
