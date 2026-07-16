"""On-demand ontology grounding for graph nodes.

A node carries a free-text ``label`` and a ``NodeType``. Grounding routes the
label to the canonical ontology for that type (UniProt for targets, GO for
pathways, HP for phenotypes, CL/UBERON/MONDO/ChEBI for the rest) via a live
lookup and proposes a ``set_grounding`` edit the user reviews before applying.

Everything degrades to "no match" rather than raising: ontology services are
best-effort, and a wrong silent grounding is worse than none.
"""

from __future__ import annotations

import logging
import re
from typing import Protocol

from pydantic import BaseModel

from quration.hypothesis.graph import Node, NodeType
from quration.hypothesis.orchestrator.edge_chat import (
    GraphEdit,
    SetGrounding,
    SetProteinStateGrounding,
)
from quration.hypothesis.orchestrator.labels import (
    candidate_labels,
    phospho_residues,
    protein_base,
)
from quration.hypothesis.provenance import OntologyTermProvenance

logger = logging.getLogger(__name__)


class GroundingProposal(BaseModel):
    """Result of a grounding lookup: a reviewable proposal, or a not-found note."""

    found: bool
    summary: str
    proposed_edit: GraphEdit | None = None


class GroundingService(Protocol):
    def ground(self, node: Node) -> GroundingProposal: ...


class FallbackGroundingService:
    """Try each backend in order; return the first ``found`` grounding.

    Chains a precise local KG (OptimusKG: gene/disease/drug) with a public
    ontology lookup (OLS/UniProt) so pathway/phenotype nodes the local KG can't
    ground still resolve to a public ontology term. Best-effort: a backend that
    raises is skipped, never propagated."""

    def __init__(self, services: list[GroundingService]):
        self._services = services

    def ground(self, node: Node) -> GroundingProposal:
        last: GroundingProposal | None = None
        for svc in self._services:
            try:
                proposal = svc.ground(node)
            except Exception as exc:  # a backend outage must not break grounding
                logger.warning("grounding backend %s failed: %s", type(svc).__name__, exc)
                continue
            if proposal.found:
                return proposal
            last = proposal
        return last or GroundingProposal(
            found=False, summary=f"No grounding for '{node.label}'."
        )


# NodeType -> the OLS ontology to search. TARGET is handled separately (UniProt);
# the *_via_mapper helpers (disease/cell_type/tissue) have dedicated resolvers.
_OLS_ONTOLOGY = {
    NodeType.PATHWAY: "go",
    NodeType.PHENOTYPE: "hp",
    NodeType.COMPOUND: "chebi",
}


def _normalize_curie(term_id: str) -> str:
    """OLS returns short-forms like 'GO_0046427'; normalize to the CURIE 'GO:0046427'."""
    if ":" in term_id or "_" not in term_id:
        return term_id
    return term_id.replace("_", ":", 1)


def _ontology_label(term_id: str, ontology_name: str | None) -> str:
    """Derive a clean ontology label: prefer the term-id prefix (GO:123 -> GO)."""
    if ":" in term_id:
        return term_id.split(":", 1)[0]
    return (ontology_name or "").upper()


def _edit_from_term(node_id: str, term_id: str, ontology_name: str | None, label: str) -> SetGrounding:
    curie = _normalize_curie(term_id)
    return SetGrounding(
        node_id=node_id,
        ontology=_ontology_label(curie, ontology_name),
        term_id=curie,
        label=label,
    )


class OntologyGroundingService:
    """Routes a node to a live ontology lookup (OLS for most, UniProt for targets)."""

    def __init__(self, mapper, uniprot):
        self._mapper = mapper
        self._uniprot = uniprot

    def ground(self, node: Node) -> GroundingProposal:
        if node.type == NodeType.TARGET:
            return self._ground_target(node)

        candidates = candidate_labels(node.label, node.type) or [node.label]

        # Molecular readouts (phospho-proteins like pAKT/pS6/pERK) are routinely
        # mistyped as phenotype/pathway but ARE proteins — ground them to their base
        # protein via UniProt (pAKT -> AKT1) instead of fuzzing a clinical ontology.
        for cand in candidates:
            base = protein_base(cand)
            if base:
                state = self._ground_phospho_state(node, base)
                if state.found:
                    return state

        ontology = _OLS_ONTOLOGY.get(node.type)
        if ontology is None and node.type not in (
            NodeType.DISEASE, NodeType.CELL_TYPE, NodeType.TISSUE,
        ):
            return GroundingProposal(
                found=False, summary=f"{node.type.value} nodes have no canonical ontology to ground to."
            )

        for query in candidates:
            if node.type == NodeType.DISEASE:
                term = self._mapper.map_disease(query)
            elif node.type == NodeType.CELL_TYPE:
                term = self._mapper.map_cell_type(query)
            elif node.type == NodeType.TISSUE:
                term = self._mapper.map_tissue(query)
            else:
                # Exact match only: a blind fuzzy top-hit grounds garbage — e.g.
                # "phospho-AKT" matched HP:0003240 "Increased phosphoribosylpyrophosphate
                # synthetase level" on the "phospho" substring. A confidently-wrong
                # grounding is worse than none, so reject weak (non-exact) matches.
                hits = self._mapper.search_term(
                    query, ontologies=[ontology], exact=True, limit=1
                )
                term = hits[0] if hits else None
            if term is not None and term.ontology_id:
                return self._from_term(node, term)
        return self._from_term(node, None)

    def _ground_target(self, node: Node) -> GroundingProposal:
        return self._ground_protein(node, node.label)

    def _ground_protein(self, node: Node, symbol: str) -> GroundingProposal:
        # Prefer the reviewed (Swiss-Prot) canonical entry for an exact gene symbol
        # (EGFR -> P00533), then any reviewed match, then anything at all. `symbol`
        # is the query (the node label, or a phospho-readout's base like AKT).
        protein = None
        for query in (f"gene_exact:{symbol} AND reviewed:true",
                      f"{symbol} AND reviewed:true",
                      symbol):
            hits = self._uniprot.search(query, organism="human", limit=1)
            if hits:
                protein = hits[0]
                break
        if protein is None:
            return GroundingProposal(
                found=False, summary=f"No UniProt protein matched '{symbol}'."
            )
        edit = SetGrounding(
            node_id=node.id, ontology="UniProt", term_id=protein.uniprot_id,
            label=protein.protein_name or node.label,
        )
        return GroundingProposal(
            found=True,
            summary=f"Matched '{node.label}' to UniProt {protein.uniprot_id}.",
            proposed_edit=edit,
        )

    def _ground_phospho_state(self, node: Node, base: str) -> GroundingProposal:
        """Ground a phospho-readout to its protein FAMILY in a phospho state.

        Members are the reviewed-human UniProt entries whose gene symbol equals or
        starts with `base` (AKT -> AKT1/AKT2/AKT3) — never an unrelated full-text hit
        (UniProt's free-text ranking once put IKBKE atop "AKT"). The isoform is deferred
        (`resolved_to=None`): which one is differentially active is for the data to say."""
        bl = base.upper()
        hits = self._uniprot.search(f"{base} AND reviewed:true", organism="human", limit=25)

        members: list[OntologyTermProvenance] = []
        seen: set[str] = set()
        for h in hits:
            names = [g.upper() for g in (h.gene_names or [])]
            # A family member's symbol is the base itself or base + isoform number
            # (AKT -> AKT1/AKT2/AKT3); this excludes look-alikes like AKTIP / IKBKE
            # whose symbol merely starts with the base.
            if not any(n == bl or re.fullmatch(rf"{re.escape(bl)}\d+", n) for n in names):
                continue
            if h.uniprot_id in seen:
                continue
            seen.add(h.uniprot_id)
            members.append(OntologyTermProvenance(
                ontology="UniProt", term_id=h.uniprot_id, label=h.protein_name or h.uniprot_id,
            ))
        if not members:
            return GroundingProposal(
                found=False, summary=f"No UniProt family matched the base symbol '{base}'."
            )
        members.sort(key=lambda m: m.label or m.term_id)  # deterministic order

        # Drop a residue equal to the base so a protein named like a site (e.g. "S6")
        # is not read as its own phospho-residue.
        residues = [r for r in phospho_residues(node.label) if r.upper() != bl]
        family_label = (
            f"{base} (phospho-{'/'.join(residues)})" if residues else f"{base} (phospho)"
        )
        edit = SetProteinStateGrounding(
            node_id=node.id, family_label=family_label, members=members,
            residues=residues, resolved_to=None,
        )
        return GroundingProposal(
            found=True,
            summary=(f"Matched '{node.label}' to the {base} family in a phospho state "
                     f"({len(members)} isoform(s))."),
            proposed_edit=edit,
        )

    def _from_term(self, node: Node, term) -> GroundingProposal:
        if term is None or not term.ontology_id:
            return GroundingProposal(
                found=False, summary=f"No ontology term matched '{node.label}'."
            )
        edit = _edit_from_term(node.id, term.ontology_id, term.ontology_name, term.term)
        return GroundingProposal(
            found=True,
            summary=f"Matched '{node.label}' to {edit.ontology} {edit.term_id}.",
            proposed_edit=edit,
        )


# A small offline lookup table so the demo (and tests) ground deterministically
# without touching OLS/UniProt.
_DEMO_TERMS = {
    "egfr": ("UniProt", "P00533", "Epidermal growth factor receptor"),
    "kras": ("UniProt", "P01116", "GTPase KRas"),
    "jak/stat3 signaling": ("GO", "GO:0007259", "JAK-STAT cascade"),
    "heart failure": ("MONDO", "MONDO:0005252", "heart failure"),
    "drug resistance": ("HP", "HP:0020110", "Drug resistance"),
}


class DemoGroundingService:
    """Deterministic, offline grounding for the demo seam and tests."""

    def ground(self, node: Node) -> GroundingProposal:
        hit = _DEMO_TERMS.get(node.label.strip().lower())
        if hit is None:
            return GroundingProposal(
                found=False, summary=f"No demo grounding for '{node.label}'."
            )
        ontology, term_id, label = hit
        return GroundingProposal(
            found=True,
            summary=f"Matched '{node.label}' to {ontology} {term_id}.",
            proposed_edit=SetGrounding(
                node_id=node.id, ontology=ontology, term_id=term_id, label=label
            ),
        )
