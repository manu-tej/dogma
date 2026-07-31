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
    """A reproducible pipeline run on named data.

    Construct this ONLY where a pipeline actually ran. It is the type that makes
    "this evidence came from a real computation" checkable, and it is worth nothing
    if anything else mints one.

    It was being minted by the methods-graph evaluator, which runs no pipeline: it
    passed `run_id="methods-graph-eval-<edge_id>"` and the literal string
    `data_accession="methods-graph"` — a fabricated run against a fabricated
    accession. Use `GroundingProvenance` for that; see EvidenceEntry, which now
    enforces the pairing.
    """

    kind: Literal["pipeline_run"] = "pipeline_run"
    run_id: str
    data_accession: str


class GroundingProvenance(BaseModel):
    """A methods-graph consultation: did a method exist for this claim's readout?

    Answers "can this be measured", never "what was measured". No run id and no data
    accession, because neither exists — a consultation reads a method registry, it
    does not touch data. Inventing placeholders for those fields is precisely what
    this type is here to stop.
    """

    kind: Literal["grounding"] = "grounding"
    #: One of GROUNDED / PARTIALLY_GROUNDED / COVERAGE_GAP / NOT_EVALUABLE.
    verdict: str
    #: The method the registry resolved, when it resolved one.
    method_id: str | None = None
    #: What was consulted, e.g. "methods-graph".
    source: str = "methods-graph"


Provenance = Annotated[
    OntologyTermProvenance
    | KGEdgeProvenance
    | LiteratureProvenance
    | PipelineRunProvenance
    | GroundingProvenance,
    Field(discriminator="kind"),
]

#: What may back an entry in the edge evidence ledger. Discriminated on `kind`, so
#: rows persisted before `grounding` existed still deserialize as `pipeline_run`.
#: `EvidenceEntry` enforces which of the two each kind of entry may carry.
EvidenceProvenance = Annotated[
    PipelineRunProvenance | GroundingProvenance,
    Field(discriminator="kind"),
]

# Node-identity grounding: a single ontology term, or a protein family in a modified
# state. Discriminated by `kind` so persisted `ontology_term` groundings deserialize
# unchanged and `protein_state` groundings round-trip cleanly.
NodeGrounding = Annotated[
    OntologyTermProvenance | ProteinStateProvenance,
    Field(discriminator="kind"),
]
