"""Unified provenance model. Every claim the platform emits must carry one of these.

Provenance-or-silence: if a claim cannot be grounded in one of these sources,
it must not be asserted (enforced by callers, not by this module).
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class OntologyTermProvenance(BaseModel):
    """A canonical ontology term (used to ground a node's identity)."""

    kind: Literal["ontology_term"] = "ontology_term"
    ontology: str = Field(description='Ontology prefix, e.g. "EFO", "MONDO", "UBERON", "GO".')
    term_id: str = Field(description='Canonical term id, e.g. "EFO:0000305".')
    label: str | None = None


class ProteinModification(BaseModel):
    """A post-translational modification on a protein readout. Phosphorylation only, for now."""

    kind: Literal["phosphorylation"] = "phosphorylation"
    residues: list[str] = []  # e.g. ["S473", "T308"] as stated (canonical-isoform numbering)


class ProteinStateProvenance(BaseModel):
    """A protein FAMILY in a modified STATE — the faithful grounding for a phospho-readout.

    pAKT is AKT1/2/3 phosphorylated; *which* isoform is differentially active is an
    empirical question the data resolves, so the isoform is deferred (`resolved_to=None`)
    until the user picks one. Members are UniProt accessions (no new ontologies)."""

    kind: Literal["protein_state"] = "protein_state"
    family_label: str  # human label, e.g. "AKT (phospho-S473/T308)"
    members: list[OntologyTermProvenance] = []  # candidate isoforms (UniProt)
    modification: ProteinModification
    resolved_to: str | None = None  # UniProt id of the chosen isoform; None = unresolved


class KGEdgeProvenance(BaseModel):
    """A suggestion from a knowledge graph. Display-only — never a confidence prior."""

    kind: Literal["kg_edge"] = "kg_edge"
    source: str = Field(
        description='Knowledge-graph source, e.g. "open_targets", "signor", "indra".'
    )
    reference: str = Field(description="Source-specific id or URL.")
    statement_count: int | None = None


class LiteratureProvenance(BaseModel):
    """A literature citation."""

    kind: Literal["literature"] = "literature"
    pmid: str


class PipelineRunProvenance(BaseModel):
    """A reproducible pipeline run on named data. The only source of edge evidence."""

    kind: Literal["pipeline_run"] = "pipeline_run"
    run_id: str
    data_accession: str


Provenance = Annotated[
    OntologyTermProvenance
    | KGEdgeProvenance
    | LiteratureProvenance
    | PipelineRunProvenance,
    Field(discriminator="kind"),
]

# Node-identity grounding: a single ontology term, or a protein family in a modified
# state. Discriminated by `kind` so persisted `ontology_term` groundings deserialize
# unchanged and `protein_state` groundings round-trip cleanly.
NodeGrounding = Annotated[
    OntologyTermProvenance | ProteinStateProvenance,
    Field(discriminator="kind"),
]
