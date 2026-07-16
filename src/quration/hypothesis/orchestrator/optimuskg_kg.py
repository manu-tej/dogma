"""OptimusKG edge knowledge: real "what's known" provenance + KG neighbor expansion.

Reuses the OptimusKG node tables (for label->id resolution) and reads its per-pair
edge Parquets (partitioned and small: gene_gene ~1.7MB). Best-effort throughout —
any missing file / schema mismatch / null degrades to an empty result, never raises.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import polars as pl

from quration.hypothesis.graph import Node, NodeType
from quration.hypothesis.orchestrator.kg_knowledge import EdgeKnowledge, Neighbor
from quration.hypothesis.orchestrator.optimuskg_grounding import (
    _default_loader,
    _match_row,
    candidate_labels,
)

logger = logging.getLogger(__name__)

_GENE_TABLE = "nodes/gene.parquet"
_DISEASE_TABLE = "nodes/disease.parquet"
_DRUG_TABLE = "nodes/drug.parquet"
_KIND_OF = {_GENE_TABLE: "gene", _DISEASE_TABLE: "disease", _DRUG_TABLE: "drug"}

# Probe order per node type; gene is always a fallback (type-agnostic resolution).
_PROBE_ORDER: dict[NodeType, list[str]] = {
    NodeType.TARGET: [_GENE_TABLE],
    NodeType.DISEASE: [_DISEASE_TABLE, _GENE_TABLE],
    NodeType.PHENOTYPE: [_DISEASE_TABLE, _GENE_TABLE],
    NodeType.COMPOUND: [_DRUG_TABLE, _GENE_TABLE],
}
_DEFAULT_ORDER = [_GENE_TABLE, _DISEASE_TABLE, _DRUG_TABLE]

# Unordered entity-kind pair -> OptimusKG edge file.
EDGE_FILES: dict[frozenset[str], str] = {
    frozenset({"gene"}): "edges/gene_gene.parquet",
    frozenset({"gene", "disease"}): "edges/disease_gene.parquet",
    frozenset({"gene", "drug"}): "edges/drug_gene.parquet",
    frozenset({"disease", "drug"}): "edges/drug_disease.parquet",
    frozenset({"disease"}): "edges/disease_disease.parquet",
    frozenset({"drug"}): "edges/drug_drug.parquet",
}


@dataclass
class NodeRef:
    kind: str
    id: str
    name: str


class OptimusKGKnowledgeService:
    def __init__(self, loader=None):
        self._loader = loader or _default_loader
        self._cache: dict[str, pl.DataFrame] = {}
        self._gene_index: dict[str, tuple[str, str]] | None = None

    def _table(self, path: str) -> pl.DataFrame:
        if path not in self._cache:
            self._cache[path] = self._loader(path)
        return self._cache[path]

    def resolve_ref(self, label: str, node_type: NodeType) -> NodeRef | None:
        # Same candidate widening as grounding: descriptive labels and
        # parenthetical names still resolve, so expand/known work on them too.
        for cand in candidate_labels(label, node_type):
            for path in _PROBE_ORDER.get(node_type, _DEFAULT_ORDER):
                try:
                    row = _match_row(self._table(path), cand, path)
                except Exception as exc:
                    logger.warning("OptimusKG resolve probe %s failed: %s", path, exc)
                    continue
                if row is not None:
                    props = row.get("properties") or {}
                    return NodeRef(kind=_KIND_OF[path], id=row["id"], name=props.get("name") or cand)
        return None

    def edge_knowledge(self, a: NodeRef, b: NodeRef) -> EdgeKnowledge:
        if a.id == b.id:  # both graph nodes resolved to the same KG entity
            return EdgeKnowledge(
                found=False, summary=f"{a.name} and {b.name} resolve to the same KG entity.")
        path = EDGE_FILES.get(frozenset({a.kind, b.kind}))
        if path is None:
            return EdgeKnowledge(found=False, summary=f"OptimusKG has no {a.kind}-{b.kind} edge table.")
        try:
            rows = self._incident_pair(self._table(path), a.id, b.id)
        except Exception as exc:
            logger.warning("OptimusKG edge_knowledge %s failed: %s", path, exc)
            return EdgeKnowledge(found=False, summary="OptimusKG edge lookup failed.")
        if not rows:
            return EdgeKnowledge(
                found=False, summary=f"No direct OptimusKG edge between {a.name} and {b.name}.")
        relations = sorted({r["relation"] for r in rows if r.get("relation")})
        sources = sorted({s for r in rows for s in _row_sources(r)})
        rel = relations[0] if relations else "linked"
        return EdgeKnowledge(
            found=True, relations=relations, sources=sources,
            summary=f"{a.name} {rel} {b.name} in OptimusKG ({len(sources)} source(s)).")

    # --- graph-node-facing wrappers (used by the API) ---
    def known(self, src: Node, tgt: Node) -> EdgeKnowledge:
        a = self.resolve_ref(src.label, src.type)
        b = self.resolve_ref(tgt.label, tgt.type)
        if a is None or b is None:
            missing = src.label if a is None else tgt.label
            return EdgeKnowledge(found=False, summary=f"Couldn't resolve '{missing}' in OptimusKG.")
        return self.edge_knowledge(a, b)

    def expand(self, node: Node, limit: int = 8) -> list[Neighbor]:
        ref = self.resolve_ref(node.label, node.type)
        return self.neighbors(ref, limit) if ref else []

    def neighbors(self, ref: NodeRef, limit: int = 8) -> list[Neighbor]:
        if ref.kind != "gene":
            return []  # v1: gene neighbors only
        try:
            e = self._table("edges/gene_gene.parquet")
            inc = e.filter((pl.col("from") == ref.id) | (pl.col("to") == ref.id))
            index = self._gene_id_index()  # also best-effort: a missing gene table must not raise
        except Exception as exc:
            logger.warning("OptimusKG neighbors failed: %s", exc)
            return []
        scored: list[tuple[int, Neighbor]] = []
        for r in inc.iter_rows(named=True):
            other = r["to"] if r["from"] == ref.id else r["from"]
            if other == ref.id or other not in index:
                continue
            symbol, name = index[other]
            srcs = _row_sources(r)
            scored.append((len(srcs), Neighbor(
                id=other, symbol=symbol, name=name, relation=r.get("relation") or "linked",
                sources=sorted(set(srcs)))))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [n for _, n in scored[:limit]]

    # --- helpers ---
    def _incident_pair(self, edges: pl.DataFrame, id_a: str, id_b: str) -> list[dict]:
        ids = [id_a, id_b]
        hit = edges.filter(
            pl.col("from").is_in(ids) & pl.col("to").is_in(ids) & (pl.col("from") != pl.col("to"))
        )
        return hit.to_dicts()

    def _gene_id_index(self) -> dict[str, tuple[str, str]]:
        if self._gene_index is None:
            g = self._table(_GENE_TABLE)
            self._gene_index = {
                row["id"]: (
                    (row.get("properties") or {}).get("symbol") or row["id"],
                    (row.get("properties") or {}).get("name") or "",
                )
                for row in g.iter_rows(named=True)
            }
        return self._gene_index


def _row_sources(row: dict) -> list[str]:
    props = row.get("properties") or {}
    src = props.get("sources") or {}
    return list(src.get("direct") or []) + list(src.get("indirect") or [])
