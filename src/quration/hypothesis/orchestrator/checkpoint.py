"""Data types exchanged at the loop's checkpoints."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class QueryKind(str, Enum):
    """Triage outcome for an incoming query."""

    SIMPLE = "simple"
    INVESTIGATIVE = "investigative"


class MethodChoice(BaseModel):
    """The broker's advisory recommendation of which method fits a proposed test.

    Advisory only: it does NOT drive execution. `source` is how the pick was made
    ("structural" = deterministic request; "fallback" = enriched-query retry).
    `grounding` is the methods-graph neighborhood RAG text for the chosen method
    (verbatim, opaque), or None when no graph provider is configured.
    """

    method_id: str
    name: str
    score: float
    source: Literal["structural", "fallback"]
    rationale: str
    grounding: str | None = None


class ProposedTest(BaseModel):
    """A checkpoint card: the supervisor's proposal to test one edge.

    Nothing runs until the caller approves this. `gap` is the rationale
    (why this edge, why now). `pipeline`/`data_accession` say how to test it.
    """

    edge_id: str
    gap: str
    pipeline: str
    data_accession: str
    est_cost: float | None = None
    est_time: str | None = None
    # Endpoint gene symbols + the claim's relation, so a real runner can compute
    # a correlation verdict from the dataset. Populated by propose_test; optional
    # so the demo path and existing callers are unaffected.
    source_symbol: str | None = None
    target_symbol: str | None = None
    relation: str | None = None
    # Advisory broker recommendation (which method fits this edge). Attached by
    # next_proposal; None when no selector is wired or nothing matched.
    method: MethodChoice | None = None


class PipelineResult(BaseModel):
    """The raw outcome of a pipeline run, to be interpreted into evidence."""

    run_id: str
    data_accession: str
    summary: str
    raw: dict = Field(default_factory=dict)


class StartResult(BaseModel):
    """The outcome of starting a query: its kind, and the graph id if investigative."""

    kind: QueryKind
    graph_id: str | None = None
