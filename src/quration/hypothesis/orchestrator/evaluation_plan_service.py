"""Compose ideal-readout + methods-graph grounding + agentic resolution into a
per-edge EvaluationPlan, and persist the resolution as an EvidenceRecord fact."""

from __future__ import annotations

from datetime import datetime, timezone

from quration.hypothesis.evidence import EvidenceRecord, ResolverProvenance, edge_claim_signature
from quration.hypothesis.graph import CausalGraph
from quration.hypothesis.orchestrator.checkpoint import MethodChoice
from quration.hypothesis.orchestrator.dataset_search import DatasetCandidate
from quration.hypothesis.orchestrator.evaluation_plan import Claim, EvaluationPlan
from quration.hypothesis.orchestrator.grounding_eval import ground_edge
from quration.hypothesis.orchestrator.ideal_readout import derive_ideal_readout, is_not_evaluable
from quration.hypothesis.orchestrator.relation_method_map import expected_direction_for


class EvaluationPlanService:
    def __init__(self, resolver, grounding_provider=None):
        self._resolver = resolver
        self._provider = grounding_provider

    def build_skeleton(self, graph: CausalGraph, edge_id: str) -> EvaluationPlan:
        edge = graph.get_edge(edge_id)
        if edge is None:
            raise KeyError(f"edge {edge_id!r} not in graph {graph.id!r}")
        src = graph.get_node(edge.source_id)
        tgt = graph.get_node(edge.target_id)
        ideal = derive_ideal_readout(edge, tgt)
        not_evaluable = is_not_evaluable(edge.relation)
        grounding = ground_edge(self._provider, edge.relation)
        method = (MethodChoice(method_id=grounding.method_id, name=grounding.method_id,
                               score=0.0, source="structural", rationale=grounding.summary)
                  if grounding.method_id else None)
        return EvaluationPlan(
            edge_id=edge_id,
            claim=Claim(source_symbol=(src.label if src else edge.source_id),
                        target_symbol=(tgt.label if tgt else edge.target_id),
                        relation=edge.relation),
            ideal_readout=ideal,
            method=method,
            assumptions=grounding.assumptions,
            expected_direction=expected_direction_for(edge.relation),
            not_evaluable=not_evaluable,
            directness="not_evaluable" if not_evaluable else None,
        )

    def resolve(self, graph: CausalGraph, edge_id: str,
                candidates: list[DatasetCandidate], repo) -> EvaluationPlan:
        plan = self.build_skeleton(graph, edge_id)
        if plan.not_evaluable:
            return plan
        outcome = self._resolver.resolve(plan.ideal_readout, candidates)
        plan.resolved_readout = outcome.resolved_readout
        plan.directness = outcome.directness
        plan.dataset = outcome.dataset
        plan.alternatives = outcome.alternatives
        plan.proxy_rationale = outcome.proxy_rationale
        plan.resolver_provenance = outcome.resolver_provenance
        edge = graph.get_edge(edge_id)
        record = EvidenceRecord(
            edge_id=edge_id, claim_signature=edge_claim_signature(edge),
            measured_vs_claimed=(f"measured {outcome.resolved_readout.measured_entity} "
                                 f"({outcome.resolved_readout.measured_modality}); claim ideal is "
                                 f"{plan.ideal_readout.modality}") if outcome.resolved_readout
                                else "no dataset resolved",
            method=plan.method, dataset_context=(outcome.dataset.model_dump() if outcome.dataset else {}),
            per_assumption_outcomes=plan.assumptions, directness=outcome.directness,
            caveats=[outcome.proxy_rationale] if outcome.directness != "direct" else [],
            provenance=ResolverProvenance(**{k: v for k, v in outcome.resolver_provenance.items()
                                             if k in {"model", "queries_tried", "sources_searched", "n_candidates"}}),
        )
        record.created_at = datetime.now(timezone.utc).isoformat()
        repo.add_evidence_record(graph.id, record)
        return plan
