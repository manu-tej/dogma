"""Polars-free KG-knowledge types + the deterministic demo service.

Kept separate from `optimuskg_kg` (which imports polars/optimuskg) so the API and
demo mode never require the optional `optimuskg` dependency.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from quration.hypothesis.graph import Node


class EdgeKnowledge(BaseModel):
    """What a knowledge graph knows about an edge between two entities."""

    found: bool
    relations: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    summary: str


class Neighbor(BaseModel):
    """A real KG neighbor of a node, offerable as a new connected node — or, when
    already in the graph (`existing_node_id` set), as a provenance edge to it."""

    id: str
    symbol: str
    name: str
    relation: str
    sources: list[str] = Field(default_factory=list)
    existing_node_id: str | None = None  # set by the route if already in the graph


class KGService(Protocol):
    def known(self, src: Node, tgt: Node) -> EdgeKnowledge: ...
    def expand(self, node: Node, limit: int = 8) -> list[Neighbor]: ...


class DemoKGService:
    """Deterministic, offline KG knowledge for demo mode and tests."""

    def known(self, src: Node, tgt: Node) -> EdgeKnowledge:
        return EdgeKnowledge(
            found=True, relations=["INTERACTS_WITH"], sources=["DEMO-KG"],
            summary=f"{src.label} interacts with {tgt.label} (demo knowledge graph).")

    def expand(self, node: Node, limit: int = 8) -> list[Neighbor]:
        return [Neighbor(id="demo-grb2", symbol="GRB2",
                         name="growth factor receptor bound protein 2",
                         relation="INTERACTS_WITH", sources=["DEMO-KG"])]
