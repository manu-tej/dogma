"""Per-edge evaluation plan contracts (north-star §2: facts, no verdict).

The plan is the unit the workflow UI renders: the biologically-IDEAL readout
(derived from the edge, not softenable by the agent), the RESOLVED readout the
agent found in public data, the factual `directness` gap between them, the
methods-graph method + per-assumption preconditions, and provenance. None of
these is a grade.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from quration.hypothesis.orchestrator.checkpoint import MethodChoice
from quration.hypothesis.orchestrator.dataset_search import DatasetCandidate

Modality = Literal[
    "transcript", "protein", "phospho", "activity",
    "binding", "methylation", "phenotype", "unknown",
]

# A FACTUAL descriptor of the gap between the ideal and the resolved readout.
# Never a score, never ranked across edges.
Directness = Literal[
    "direct", "proxy_modality", "proxy_correlation", "wrong_assay", "not_evaluable",
]

ExpectedDirection = Literal["increase", "decrease", "none", "unknown"]


class ReadoutSpec(BaseModel):
    """The biologically-correct measurement for the claim. From biology; fixed."""

    claimed_entity: str
    modality: Modality
    ideal_assay_class: str


class ResolvedReadout(BaseModel):
    """What the agent's chosen dataset actually measures."""

    measured_entity: str
    measured_modality: Modality
    assay: str
    source: Literal["geo", "pride"]
    accession: str
    feature_present: bool | None = None  # None = unverified in this slice


class AssumptionOutcome(BaseModel):
    """One methods-graph assumption for the chosen method (from method_preconditions).

    `checkable` is the graph's machine-readable flag ("pre_run"/"post_run"/"").
    `status` stays "unchecked" until slice-2 execution checks it against a dataset.
    """

    name: str
    checkable: str = ""
    threshold: dict | None = None
    via: list[dict] = Field(default_factory=list)
    status: Literal["unchecked", "holds", "violated", "unknown"] = "unchecked"


class Claim(BaseModel):
    source_symbol: str
    target_symbol: str
    relation: str


class EvaluationPlan(BaseModel):
    """The per-edge plan the workflow UI renders. Addressed at the clicked edge."""

    edge_id: str
    claim: Claim
    ideal_readout: ReadoutSpec
    resolved_readout: ResolvedReadout | None = None
    directness: Directness | None = None  # None until a dataset is resolved
    proxy_rationale: str = ""
    dataset: DatasetCandidate | None = None
    alternatives: list[DatasetCandidate] = Field(default_factory=list)
    method: MethodChoice | None = None
    assumptions: list[AssumptionOutcome] = Field(default_factory=list)
    expected_direction: ExpectedDirection = "unknown"
    not_evaluable: bool = False
    resolver_provenance: dict = Field(default_factory=dict)
