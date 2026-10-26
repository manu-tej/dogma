"""Edge evidence and the evidence-ledger rollup.

rollup_edge determines only WHETHER evidence exists (EXAMINED) or not (UNTESTED).
It no longer computes a confidence score or emits verdict states (north-star §2.2).
KG provenance never participates here — only the user's pipeline runs do.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from quration.hypothesis.epistemics import (
    EdgeValidation,
    ProposalSource,
    summarize_status,
)
from quration.hypothesis.graph import EdgeState
from quration.hypothesis.provenance import (
    EvidenceProvenance,
    GroundingProvenance,
    PipelineRunProvenance,
)


class EvidenceDirection(str, Enum):
    """Whether a pipeline result supports, refutes, or is inconclusive for an edge."""

    SUPPORTS = "supports"
    REFUTES = "refutes"
    INCONCLUSIVE = "inconclusive"


class EvidenceKind(str, Enum):
    """Whether an entry records a measurement or only an assessment of one.

    The distinction is load-bearing: `rollup_edge` used to mark an edge EXAMINED for
    *any* entry, and the only runner wired into the loop emits an entry for every
    edge it inspects — including one meaning "no method exists for this readout". So
    edges reported as examined had never been measured.

    See docs/decisions/2026-07-30-what-a-measurement-may-change-on-an-edge.md
    """

    #: A pipeline ran and produced a result bearing on the claim.
    MEASUREMENT = "measurement"
    #: A pre-execution judgement about whether the claim *can* be measured —
    #: GROUNDED / PARTIALLY_GROUNDED / COVERAGE_GAP / NOT_EVALUABLE. Not a result.
    FEASIBILITY = "feasibility"


class EvidenceEntry(BaseModel):
    """One record bearing on one edge: either a measurement or an assessment of one.

    `provenance` is constrained by `kind`, and the pairing is enforced below rather
    than left to convention — a MEASUREMENT must carry `PipelineRunProvenance`, and a
    FEASIBILITY entry must not. That is what makes "this evidence came from a real
    computation" a checkable property instead of a naming habit.

    `weight` is the quality weight in (0, 1].
    """

    edge_id: str
    # Defaults to FEASIBILITY, not MEASUREMENT, on purpose. Every entry any
    # production path has ever written is a feasibility assessment, so this is
    # accurate for existing rows; and it makes "this is a measurement" something a
    # producer has to assert rather than inherit.
    kind: EvidenceKind = EvidenceKind.FEASIBILITY
    direction: EvidenceDirection
    weight: float = Field(default=1.0, gt=0.0, le=1.0)
    magnitude: str | None = None  # effect size / statistic summary from the pipeline
    rationale: str | None = None
    provenance: EvidenceProvenance
    # The (source_id, target_id, relation) the evidence was gathered against, stamped
    # at ingestion. If the edge's claim signature later changes, this evidence stays in
    # the ledger but no longer supports the edited claim. None = legacy row (assumed
    # to apply to the current claim, preserving pre-existing graphs).
    claim_signature: tuple[str, str, str] | None = None
    execution_context_digest: str | None = None
    execution_receipt: str | None = None
    execution_context: dict | None = None
    execution_receipt_hash: str | None = None

    @model_validator(mode="after")
    def _provenance_matches_kind(self) -> "EvidenceEntry":
        """A MEASUREMENT must be backed by a real run; an assessment must not claim one.

        This is the firewall the epistemics layer exists to provide, made checkable
        rather than conventional. Without it, `PipelineRunProvenance` means only
        "somebody constructed this object" — which is how the methods-graph
        evaluator came to stamp `run_id="methods-graph-eval-<edge>"` and
        `data_accession="methods-graph"` on evidence for a pipeline that never ran.
        """
        if self.kind is EvidenceKind.MEASUREMENT and not isinstance(
            self.provenance, PipelineRunProvenance
        ):
            raise ValueError(
                "a MEASUREMENT entry requires PipelineRunProvenance; got "
                f"{type(self.provenance).__name__}"
            )
        if self.kind is EvidenceKind.FEASIBILITY and isinstance(
            self.provenance, PipelineRunProvenance
        ):
            raise ValueError(
                "a FEASIBILITY entry must not carry PipelineRunProvenance — no "
                "pipeline ran. Use GroundingProvenance."
            )
        return self


def rollup_edge(entries: list[EvidenceEntry]) -> tuple[EdgeState, float]:
    """The edge's state IS its ledger. There is still no verdict (north-star §2.2) —
    this reports only what kind of work happened, which is a fact about the system,
    not a claim about the biology:

        no entries                  -> UNTESTED
        at least one MEASUREMENT    -> EXAMINED
        otherwise (assessments only) -> ASSESSED

    Previously any entry at all produced EXAMINED, so an edge whose only record said
    "no method exists for this readout" was reported as examined, and the loop
    declared itself finished having measured nothing.

    The second element (a deprecated `confidence`) is always 0.0; it is kept only so
    callers and serialization that still read a float keep working until they are
    removed.

    See docs/decisions/2026-07-30-what-a-measurement-may-change-on-an-edge.md
    """
    if not entries:
        return EdgeState.UNTESTED, 0.0
    if any(e.kind == EvidenceKind.MEASUREMENT for e in entries):
        return EdgeState.EXAMINED, 0.0
    return EdgeState.ASSESSED, 0.0


def dataset_validation_for(
    entries: list[EvidenceEntry], created_at: str
) -> EdgeValidation | None:
    """The dataset channel no longer renders a verdict (north-star §2.2): support and
    contradiction are abolished, so it contributes no `EdgeValidation`. The per-run
    facts live in the evidence ledger; the agent/human read them there. Returns None
    always. (Kept as a function so `sync_dataset_validation` — which strips any *prior*
    dataset validation — needs no change.)"""
    return None


def edge_claim_signature(edge) -> tuple[str, str, str]:
    """The claim an edge asserts: (source_id, target_id, relation). Dataset evidence
    is only valid for the signature it was gathered against."""
    return (edge.source_id, edge.target_id, edge.relation)


def execution_context_current(entry):
    if entry.execution_context is None:
        return True  # legacy rows are retained as unverified; no receipt is invented
    from quration.pipelines.execution_contract import file_digest, digest
    context = entry.execution_context
    try:
        import os
        from pathlib import Path
        import hashlib
        binding = context.get('methods_graph_binding')
        if not binding:
            return False
        method_path = Path(binding['path'])
        configured_path = next((os.environ[name] for name in ('DOGMA_METHODS_GRAPH_DB', 'METHODS_GRAPH_DB', 'BIOCURSOR_METHODS_GRAPH_DB', 'QURATION_METHODS_GRAPH_DB') if os.environ.get(name)), None)
        if configured_path is not None and Path(configured_path).resolve() != method_path.resolve():
            return False
        if not method_path.resolve().is_relative_to(Path(context['workspace_root']).resolve()):
            if configured_path is None or Path(configured_path).resolve() != method_path.resolve():
                return False  # external authority requires current trusted configuration
        if method_path.suffix != '.kuzu' or method_path.is_symlink() or 'sha256:' + hashlib.sha256(method_path.read_bytes()).hexdigest() != binding['sha256']:
            return False
        if binding.get('lock'):
            lock = Path(binding['lock'])
            if lock.name not in ('ingest.lock.json', 'methods.lock.json') or lock.parent != method_path.parent or lock.is_symlink():
                return False
            if 'sha256:' + hashlib.sha256(lock.read_bytes()).hexdigest() != binding['lock_hash']:
                return False
        if digest(context) != entry.execution_context_digest:
            return False
        if entry.execution_receipt is not None:
            import json
            from quration.pipelines.execution_contract import contained
            if file_digest(context['workspace_root'], entry.execution_receipt) != entry.execution_receipt_hash:
                return False
            receipt = json.loads(contained(context['workspace_root'], entry.execution_receipt).read_text())
            if receipt.get('status') != 'completed' or receipt.get('measurement') is None:
                return False
            directory = contained(context['workspace_root'], entry.execution_receipt).parent
            if any(file_digest(context['workspace_root'], contained(directory, path)) != expected
                   for path, expected in receipt.get('artifacts', {}).items()):
                return False
        return all(file_digest(context['workspace_root'], path) == expected
                   for path, expected in context['file_pins'].items())
    except (ValueError, OSError, KeyError):
        return False


def context_claim_identity(context):
    from quration.pipelines.execution_contract import digest
    return digest({key: context[key] for key in ('endpoint_grounding', 'claim_signature', 'proposed_test')})


def relevant_evidence(edge, entries: list[EvidenceEntry]) -> list[EvidenceEntry]:
    """Evidence rows that apply to the edge's CURRENT claim signature. A row whose
    signature differs (the claim was edited after it was gathered) is excluded so it
    can't support the edited claim.

    Legacy rows (signature ``None``) predate claim signatures. They are assumed to
    apply to the current claim ONLY while the edge has never had a claim-changing
    edit — i.e. no superseding barrier in its validations. Once such a barrier
    exists we can't assume an unsigned row was gathered for the edited claim, so it
    stops counting (matching the signed-evidence behaviour); the row stays in the
    ledger and any new signed evidence for the edited claim counts normally."""
    sig = edge_claim_signature(edge)
    superseded = any(v.supersedes_prior for v in edge.validations)
    return [
        e for e in entries
        if execution_context_current(e)
        and (e.execution_context is None or context_claim_identity(e.execution_context) == edge.execution_claim_identity)
        and (e.execution_context_digest is None or e.execution_context_digest == edge.execution_context_digest)
        and (tuple(e.claim_signature) == sig if e.claim_signature is not None
            else not superseded)
    ]


def refresh_execution_identity(graph, edge, entries):
    """Refresh claim grounding/test identity without rebinding any historical row."""
    from quration.pipelines.execution_contract import digest
    import copy
    contextual = [entry for entry in entries if entry.execution_context is not None]
    if not contextual:
        return
    context = copy.deepcopy(contextual[-1].execution_context)
    endpoints = [graph.get_node(node) for node in (edge.source_id, edge.target_id)]
    context['endpoint_grounding'] = [{k: v for k, v in node.model_dump(mode='json').items()
        if k in ('id', 'grounding', 'type')} if node is not None else None for node in endpoints]
    context['claim_signature'] = list(edge_claim_signature(edge))
    context['proposed_test'] = edge.proposed_test.model_dump(mode='json') if edge.proposed_test else None
    edge.execution_claim_identity = context_claim_identity(context)


def recompute_edge_evidence(edge, entries: list[EvidenceEntry], created_at: str) -> None:
    """Recompute an edge's dataset-derived state from ONLY the evidence that applies to
    its current claim signature: both the `state`/`confidence` rollup and the dataset
    `validation_status` reflect the current claim. After a relation/endpoint edit, stale
    evidence (gathered under the old signature) stops supporting the edge until new
    evidence is added for the edited claim. The evidence ledger itself is untouched."""
    relevant = relevant_evidence(edge, entries)
    edge.state, edge.confidence = rollup_edge(relevant)
    sync_dataset_validation(edge, relevant, created_at)


def sync_dataset_validation(edge, entries: list[EvidenceEntry], created_at: str) -> None:
    """Make the edge's DATASET-channel validation reflect the current rollup,
    idempotently: drop any prior dataset validation, append the current one (if the
    evidence is conclusive), then recompute `validation_status`. The granular per-run
    audit lives in the evidence ledger, so the dataset *validation* is a single
    derived summary — never a growing pile of duplicates. Other channels (KG /
    literature) are left untouched (they record genuine, distinct events)."""
    edge.validations = [v for v in edge.validations if v.source != ProposalSource.DATASET]
    validation = dataset_validation_for(entries, created_at)
    if validation is not None:
        edge.validations.append(validation)
    edge.validation_status = summarize_status(edge.validations)


# --- The ledger record (north-star §2): facts, no verdict. Coexists with EvidenceEntry. ---
from quration.hypothesis.orchestrator.evaluation_plan import AssumptionOutcome, Directness
from quration.hypothesis.orchestrator.checkpoint import MethodChoice


class ResolverProvenance(BaseModel):
    """The agentic decision trail behind a resolution/grounding fact."""

    kind: Literal["resolver"] = "resolver"
    model: str | None = None
    queries_tried: list[str] = Field(default_factory=list)
    sources_searched: list[str] = Field(default_factory=list)
    n_candidates: int = 0


class EvidenceRecord(BaseModel):
    """One durable FACT bearing on one edge: what was measured vs claimed, the
    method + per-assumption preconditions, the directness descriptor, caveats, and
    provenance. `raw_result` is None until slice-2 execution. There is NO verdict,
    weight, or score — the edge's state is unaffected by these records.
    """

    edge_id: str
    claim_signature: tuple[str, str, str]
    measured_vs_claimed: str
    method: "MethodChoice | None" = None
    dataset_context: dict = Field(default_factory=dict)
    raw_result: dict | None = None
    per_assumption_outcomes: list[AssumptionOutcome] = Field(default_factory=list)
    directness: Directness
    caveats: list[str] = Field(default_factory=list)
    provenance: ResolverProvenance
    created_at: str | None = None


EvidenceRecord.model_rebuild()
