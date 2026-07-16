"""Shared connector contracts: the suggestion result, the suggester protocol, errors."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from quration.hypothesis.graph import Edge, Node


class SignorConnectorError(RuntimeError):
    """Raised when a connector cannot retrieve or parse upstream data."""


class SuggestionResult(BaseModel):
    """Candidate nodes + edges to merge (as pending proposals) into a graph."""

    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)


@runtime_checkable
class EdgeSuggester(Protocol):
    """Suggests candidate graph structure from a knowledge graph.

    Implementations never set edge confidence; suggested edges are UNTESTED and
    carry their source only in `Edge.suggested_by` (display-only).
    """

    def expand(self, seeds: list[str], query: str | None = None) -> SuggestionResult: ...

    def check_pair(self, source: str, target: str) -> Edge | None: ...
