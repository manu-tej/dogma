"""Derive the biologically-IDEAL readout for an edge from its relation + target.

The TARGET node's grounding takes precedence over the relation verb: a phospho-state
target needs a phospho assay even when the verb is "activates" (mRNA cannot test a
phosphorylation). This is the biology contract; the agent may not soften it.
"""

from __future__ import annotations

from quration.hypothesis.graph import Edge, Node
from quration.hypothesis.orchestrator.evaluation_plan import Modality, ReadoutSpec
from quration.hypothesis.orchestrator.relation_method_map import (
    _NON_MEASURABLE, keywords_for_relation,
)
from quration.hypothesis.provenance import ProteinStateProvenance

_IDEAL_ASSAY: dict[Modality, str] = {
    "phospho": "phosphoproteomics / phospho-Western",
    "transcript": "RNA-seq differential expression",
    "protein": "proteomics (total abundance)",
    "binding": "co-IP / interaction assay",
    "methylation": "bisulfite-seq",
    "activity": "activity assay",
    "phenotype": "phenotypic readout",
    "unknown": "unspecified assay",
}


def is_not_evaluable(relation: str | None) -> bool:
    r = (relation or "").lower()
    return any(tok in r for tok in _NON_MEASURABLE)


def derive_ideal_readout(edge: Edge, target_node: Node | None) -> ReadoutSpec:
    modality = _modality_for(edge, target_node)
    entity = target_node.label if target_node is not None else edge.target_id
    return ReadoutSpec(
        claimed_entity=entity, modality=modality,
        ideal_assay_class=_IDEAL_ASSAY[modality],
    )


def _modality_for(edge: Edge, target_node: Node | None) -> Modality:
    if isinstance(getattr(target_node, "grounding", None), ProteinStateProvenance):
        return "phospho"
    kws = keywords_for_relation(edge.relation)
    if any("phospho" in k for k in kws):
        return "phospho"
    if any(k in ("interaction", "co-immunoprecipitation") for k in kws):
        return "binding"
    if any(k in ("bisulfite-seq", "wgbs", "methylation") for k in kws):
        return "methylation"
    if any(k in ("differential expression", "rna-seq", "expression") for k in kws):
        return "transcript"
    return "transcript"
