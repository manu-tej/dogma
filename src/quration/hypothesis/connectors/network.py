# src/quration/hypothesis/connectors/network.py
"""Adapt the SIGNOR + CollecTRI connectors into a traversable directed graph.

A `Network` exposes `out_edges`/`in_edges` (and `label`) so a pure path-finder can
walk SIGNOR (cached HTTP, one fetch yields both directions) and CollecTRI
(in-memory) without knowing their formats. Adapters memoize accession->symbol from
the rows they parse, so `label` never re-fetches.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from quration.hypothesis.connectors.collectri import _row_to_edge as _collectri_edge
from quration.hypothesis.connectors.signor import _record_to_edge as _signor_edge
from quration.hypothesis.graph import Edge


@dataclass(frozen=True)
class Neighbor:
    node_id: str   # UniProt accession of the adjacent node
    label: str     # gene symbol
    edge: Edge     # the connector Edge (keeps its original causal direction + provenance)


@runtime_checkable
class Network(Protocol):
    def out_edges(self, node_id: str) -> list[Neighbor]: ...   # node is the source
    def in_edges(self, node_id: str) -> list[Neighbor]: ...    # node is the target
    def label(self, node_id: str) -> str: ...


class SignorNetwork:
    """SIGNOR as a Network. One `fetch_interactions(acc)` returns all rows touching
    `acc`, so out/in edges both come from a single (cached) call."""

    def __init__(self, client):
        self._client = client
        self._labels: dict[str, str] = {}

    def _records(self, node_id: str):
        try:
            return self._client.fetch_interactions(node_id)
        except Exception:
            return []

    def out_edges(self, node_id: str) -> list[Neighbor]:
        result = []
        for r in self._records(node_id):
            self._labels[r.regulator_id] = r.regulator_label or r.regulator_id
            self._labels[r.target_id] = r.target_label or r.target_id
            if r.regulator_id == node_id:
                result.append(Neighbor(r.target_id, r.target_label, _signor_edge(r)))
        return result

    def in_edges(self, node_id: str) -> list[Neighbor]:
        result = []
        for r in self._records(node_id):
            self._labels[r.regulator_id] = r.regulator_label or r.regulator_id
            self._labels[r.target_id] = r.target_label or r.target_id
            if r.target_id == node_id:
                result.append(Neighbor(r.regulator_id, r.regulator_label, _signor_edge(r)))
        return result

    def label(self, node_id: str) -> str:
        return self._labels.get(node_id, node_id)


class CollecTRINetwork:
    """CollecTRI as a Network, over the in-memory index."""

    def __init__(self, client):
        self._client = client
        self._labels: dict[str, str] = {}

    def _index(self) -> dict[str, list[dict]]:
        try:
            return self._client.index()
        except Exception:
            return {}

    def _learn(self, row: dict) -> None:
        self._labels[row["source"]] = row.get("source_genesymbol") or row["source"]
        self._labels[row["target"]] = row.get("target_genesymbol") or row["target"]

    def out_edges(self, node_id: str) -> list[Neighbor]:
        result = []
        for row in self._index().get(node_id, []):
            self._learn(row)
            if row["source"] == node_id:
                result.append(
                    Neighbor(row["target"], self._labels[row["target"]], _collectri_edge(row))
                )
        return result

    def in_edges(self, node_id: str) -> list[Neighbor]:
        result = []
        for row in self._index().get(node_id, []):
            self._learn(row)
            if row["target"] == node_id:
                result.append(
                    Neighbor(row["source"], self._labels[row["source"]], _collectri_edge(row))
                )
        return result

    def label(self, node_id: str) -> str:
        return self._labels.get(node_id, node_id)


class CombinedNetwork:
    """Union of several Networks. Dedupes neighbors by (source, target, relation)."""

    def __init__(self, networks: list[Network]):
        self._networks = networks

    def out_edges(self, node_id: str) -> list[Neighbor]:
        return self._merge(n.out_edges(node_id) for n in self._networks)

    def in_edges(self, node_id: str) -> list[Neighbor]:
        return self._merge(n.in_edges(node_id) for n in self._networks)

    def label(self, node_id: str) -> str:
        for n in self._networks:
            lbl = n.label(node_id)
            if lbl != node_id:
                return lbl
        return node_id

    @staticmethod
    def _merge(neighbor_lists) -> list[Neighbor]:
        seen: dict[tuple, Neighbor] = {}
        for lst in neighbor_lists:
            for nb in lst:
                key = (nb.edge.source_id, nb.edge.target_id, nb.edge.relation)
                seen.setdefault(key, nb)
        return list(seen.values())
