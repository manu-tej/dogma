"""Explicit epistemic state for graph edges.

Keeps four things structurally distinct so the UI/API never conflate them:
  1. how an edge was *proposed* (`ProposalSource`),
  2. whether its *entities* are grounded (lives on the nodes, not here),
  3. whether the *relation* has been validated (`EdgeValidationStatus`),
  4. what actually *supports* it (`EdgeValidation.evidence` — KG/lit/dataset only).

`validation_status` is a single summary label derived from an append-only
`validations` audit list (the replayable artifact, alongside the SQLite event
trail). LLM rationale is never evidence.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from quration.hypothesis.provenance import Provenance


class ProposalSource(str, Enum):
    """Who/what proposed an edge or a validation."""

    USER = "user"
    LLM = "llm"
    KG = "kg"
    LITERATURE = "literature"
    DATASET = "dataset"
    SYSTEM = "system"


class EdgeValidationStatus(str, Enum):
    """The epistemic state of a mechanistic claim (an edge).

    ``ENTITY_GROUNDED_RELATION_UNCHECKED`` is *display-derived only* — it is never
    stored on an edge (grounding a node must not validate its edges); the API
    computes it from endpoint grounding via :func:`display_status`.
    """

    UNVALIDATED = "unvalidated"
    ENTITY_GROUNDED_RELATION_UNCHECKED = "entity_grounded_relation_unchecked"
    KG_SUPPORTED_DIRECT = "kg_supported_direct"
    KG_SUPPORTED_INDIRECT = "kg_supported_indirect"
    LITERATURE_SUPPORTED = "literature_supported"
    DATASET_SUPPORTED = "dataset_supported"
    CONTRADICTED = "contradicted"
    UNSUPPORTED = "unsupported"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"


class EdgeValidation(BaseModel):
    """One auditable validation attempt against an edge. Append-only.

    ``evidence`` is real provenance (KG edge / literature / pipeline run) — never
    an LLM's reasoning. ``rationale`` is a short human-readable note only.
    """

    status: EdgeValidationStatus
    source: ProposalSource
    evidence: Provenance | None = None
    rationale: str | None = None  # concise — never chain-of-thought
    kg_source: str | None = None
    kg_version: str | None = None
    event_id: str | None = None
    created_at: str
    # True when this record invalidates all prior validations (e.g. the edge's
    # claim changed). `summarize_status` only counts records from the most recent
    # such barrier onward, so prior support is preserved in the audit but never
    # summarizes the edited claim. Defaulted → old graphs deserialize unchanged.
    supersedes_prior: bool = False


# Strength order (index 0 = strongest / stickiest). A negative result
# (rejected/contradicted) outranks positive support so it stays visible.
_PRIORITY: list[EdgeValidationStatus] = [
    EdgeValidationStatus.REJECTED,
    EdgeValidationStatus.CONTRADICTED,
    EdgeValidationStatus.DATASET_SUPPORTED,
    EdgeValidationStatus.KG_SUPPORTED_DIRECT,
    EdgeValidationStatus.LITERATURE_SUPPORTED,
    EdgeValidationStatus.KG_SUPPORTED_INDIRECT,
    EdgeValidationStatus.AMBIGUOUS,
    EdgeValidationStatus.UNSUPPORTED,
    EdgeValidationStatus.UNVALIDATED,
]


def _rank(status: EdgeValidationStatus) -> int:
    return _PRIORITY.index(status) if status in _PRIORITY else len(_PRIORITY)


def summarize_status(validations: list[EdgeValidation]) -> EdgeValidationStatus:
    """Single summary label: the highest-priority status among the *latest*
    validation from each source channel. Idempotent — re-running a check from the
    same source overwrites that channel's prior result before the cross-channel
    priority is applied.

    Only validations at/after the most recent superseding barrier
    (``supersedes_prior``) are counted, so a claim-changing edit drops the summary to
    ``unvalidated`` while the prior support remains in the audit."""
    if not validations:
        return EdgeValidationStatus.UNVALIDATED
    start = 0
    for i, v in enumerate(validations):
        if v.supersedes_prior:
            start = i
    active = validations[start:]
    latest_per_source: dict[ProposalSource, EdgeValidation] = {}
    for v in active:  # chronological; last write per source wins
        latest_per_source[v.source] = v
    return min((v.status for v in latest_per_source.values()), key=_rank)


def display_status(
    validation_status: EdgeValidationStatus,
    *,
    src_grounded: bool,
    tgt_grounded: bool,
) -> EdgeValidationStatus:
    """Derive the *display* status. Only an otherwise-unvalidated edge whose two
    endpoints are both grounded is shown as ``entity_grounded_relation_unchecked``
    — surfacing the nuance without ever writing it to the edge."""
    if (
        validation_status == EdgeValidationStatus.UNVALIDATED
        and src_grounded
        and tgt_grounded
    ):
        return EdgeValidationStatus.ENTITY_GROUNDED_RELATION_UNCHECKED
    return validation_status


def record_validation(edge, validation: EdgeValidation) -> None:
    """Append a validation to an edge-like object and recompute its summary status.

    Duck-typed on ``.validations`` (list) and ``.validation_status`` so it works on
    the domain ``Edge`` without a circular import."""
    if validation.status == EdgeValidationStatus.ENTITY_GROUNDED_RELATION_UNCHECKED:
        raise ValueError(
            "entity_grounded_relation_unchecked is display-derived and must never be stored"
        )
    edge.validations.append(validation)
    edge.validation_status = summarize_status(edge.validations)


def reset_edge_validation(edge, reason: str, created_at: str) -> None:
    """Invalidate an edge's validations after its claim changed (relation or
    endpoints). Appends a superseding barrier (preserving the prior records as
    audit) and recomputes — so the edited claim reads ``unvalidated`` until it is
    re-validated against the new relation/endpoints, without overstating support.
    Does NOT touch node grounding, proposal_source, or proposed_test.

    No-op when the edge has nothing to invalidate — so editing a pristine draft edge
    doesn't litter the audit with empty barriers. "Nothing to invalidate" means no
    evidence ledger (state UNTESTED) AND no other-channel (KG/literature) validation.
    Pre-abolition the dataset channel set a DATASET_SUPPORTED validation that this
    guard keyed on; with verdicts abolished an examined edge carries no dataset
    validation, so we consult the ledger-derived ``edge.state`` directly. (EdgeState
    is a str-enum, compared by value here to avoid a circular import on graph.py.)"""
    has_evidence = getattr(edge, "state", "untested") != "untested"
    if not has_evidence and summarize_status(edge.validations) == EdgeValidationStatus.UNVALIDATED:
        return
    record_validation(edge, EdgeValidation(
        status=EdgeValidationStatus.UNVALIDATED,
        source=ProposalSource.SYSTEM,
        rationale=reason,
        created_at=created_at,
        supersedes_prior=True,
    ))
