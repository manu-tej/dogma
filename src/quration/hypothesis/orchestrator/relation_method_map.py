"""Map an authored edge's causal relation to method-class search keywords.

The causal-readout semantics (what assay measures a given relation) live here in
quration, not in the methods graph. This is a hand-rolled heuristic over relation
phrases; it is the PRIMARY resolver for methods-graph grounding (`resolve_method_ids`)
— grounding is a relation->readout->method match, not the broker's keyword score.
Returns [] for definitional/non-measurable relations.
"""

from __future__ import annotations

# (substring trigger -> method-class keywords). First match wins; ORDER MATTERS:
# most-specific readouts first, generic expression/activation LAST, so e.g.
# "binds and activates" resolves to interaction (binds) not expression (activat).
_RULES: list[tuple[tuple[str, ...], list[str]]] = [
    (("phosphoryl", "phospho"), ["phosphoproteomics", "phospho", "kinase activity"]),
    (("binds", "interact"), ["interaction", "co-immunoprecipitation"]),
    (("methylat",), ["bisulfite-seq", "wgbs", "methylation"]),
    (("up-regulat", "upregulat", "down-regulat", "downregulat", "expression"),
     ["differential expression", "rna-seq", "expression"]),
    (("activat", "inhibit", "suppress", "drives"), ["differential expression", "expression"]),
]

# relations that are definitional / non-measurable -> never evaluable.
_NON_MEASURABLE = ("manifests as", "is expressed by", "defines", "does not")


def keywords_for_relation(relation: str | None) -> list[str]:
    if not relation:
        return []
    r = relation.lower()
    if any(tok in r for tok in _NON_MEASURABLE):
        return []
    for triggers, kws in _RULES:
        if any(t in r for t in triggers):
            return kws
    return []


_ACTIVATING = ("up-regulat", "activat", "drives", "drive", "promot", "induc", "increas", "enhanc")
_INHIBITORY = ("inhibit", "repress", "down-regulat", "suppress", "decreas", "reduc", "block")


def relation_polarity(relation: str | None) -> int:
    """+1 activating, -1 inhibitory, 0 unknown — from the edge's relation text."""
    r = (relation or "").lower()
    if any(tok in r for tok in _INHIBITORY):
        return -1
    if any(tok in r for tok in _ACTIVATING):
        return 1
    return 0


def expected_direction_for(relation: str | None) -> str:
    """Expected direction of the target readout under the claim."""
    return {1: "increase", -1: "decrease"}.get(relation_polarity(relation), "unknown")
