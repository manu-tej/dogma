# src/quration/hypothesis/orchestrator/methods_eval.py
"""Methods-graph edge evaluation: methodological grounding (NOT biological proof).

The methods graph has no datasets and no quantitative evidence, so it cannot
support/refute biology. This runner answers: is there a grounded analysis method
that could validly measure this edge, and what statistical assumptions must hold?
Verdicts are mapped to a low-weight INCONCLUSIVE EvidenceEntry so Edge.state never
flips to SUPPORTED on grounding alone. Missing methods are honest COVERAGE_GAPs,
never invented.
"""

from __future__ import annotations

import logging

from quration.hypothesis.evidence import (
    EvidenceDirection,
    EvidenceEntry,
    EvidenceKind,
)
from quration.hypothesis.orchestrator.checkpoint import PipelineResult, ProposedTest
from quration.hypothesis.provenance import GroundingProvenance

logger = logging.getLogger(__name__)

# raw["verdict"] values
GROUNDED = "GROUNDED"
PARTIALLY_GROUNDED = "PARTIALLY_GROUNDED"
COVERAGE_GAP = "COVERAGE_GAP"
NOT_EVALUABLE = "NOT_EVALUABLE"


class MethodsGraphEvaluationRunner:
    """Resolve a method for the edge and read its statistical methods + assumptions."""

    def __init__(self, provider):
        self._provider = provider

    def run(self, proposed: ProposedTest) -> PipelineResult:
        from quration.hypothesis.orchestrator.grounding_eval import ground_edge
        res = ground_edge(self._provider, proposed.relation)
        return PipelineResult(
            run_id=f"methods-graph-eval-{proposed.edge_id}", data_accession="methods-graph",
            summary=res.summary,
            raw={"verdict": res.verdict, "evaluable": res.verdict != "NOT_EVALUABLE",
                 "method_id": res.method_id,
                 "assumptions": [{"name": a.name, "via": a.via} for a in res.assumptions],
                 "coverage_gap": res.verdict == "COVERAGE_GAP"})


class MethodsGraphSupervisor:
    """Interprets a methods-graph evaluation as low-weight INCONCLUSIVE evidence.

    The methods graph cannot confirm/refute biology, so grounding never adds
    support/refute weight; it records the methodological context on the edge."""

    def interpret(self, proposed: ProposedTest, result: PipelineResult) -> EvidenceEntry:
        verdict = result.raw.get("verdict", COVERAGE_GAP)
        # Warn if verdict is not one of the four known constants
        if verdict not in (GROUNDED, PARTIALLY_GROUNDED, COVERAGE_GAP, NOT_EVALUABLE):
            logger.warning("Unknown verdict for %s: %s", proposed.edge_id, verdict)
        return EvidenceEntry(
            edge_id=proposed.edge_id,
            # Stated explicitly, though it is also the default: every verdict this
            # runner emits (GROUNDED / PARTIALLY_GROUNDED / COVERAGE_GAP /
            # NOT_EVALUABLE) is a judgement about whether the claim can be measured.
            # None of them is a measurement, and recording them as such is what made
            # the loop report edges as examined that it had never measured.
            kind=EvidenceKind.FEASIBILITY,
            direction=EvidenceDirection.INCONCLUSIVE,
            weight=0.01,
            magnitude=verdict,
            rationale=result.summary,
            # GroundingProvenance, not PipelineRunProvenance. This path consults a
            # method registry; it runs nothing. It used to stamp
            # run_id="methods-graph-eval-<edge_id>" and the literal
            # data_accession="methods-graph" onto a type documented as "a
            # reproducible pipeline run on named data", which made that guarantee
            # unfalsifiable for every consumer downstream.
            provenance=GroundingProvenance(
                verdict=verdict,
                method_id=result.raw.get("method_id"),
            ),
        )
