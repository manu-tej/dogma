# src/quration/hypothesis/connectors/path_suggester.py
"""PathEdgeSuggester: the seeded graph IS the judged shortest path(s) between seeds.

For >=2 seeds: pairwise shortest paths (directed, undirected fallback) over the
Network, with an LLM judge selecting the most query-relevant candidate per pair.
For 1 seed: a capped 1-hop. For nothing: empty (the loop's LLM-skeleton fallback
fires). Reuses each connector Edge's provenance.
"""

import logging
from itertools import combinations

from quration.hypothesis.connectors.base import SuggestionResult
from quration.hypothesis.graph import Edge, Node, NodeType
from quration.hypothesis.orchestrator.pathfinding import shortest_paths
from quration.hypothesis.provenance import OntologyTermProvenance

logger = logging.getLogger(__name__)


class PathEdgeSuggester:
    def __init__(self, network, judge=None, *, max_hops: int = 4, node_budget: int = 60,
                 max_candidates: int = 4, max_pairs: int = 15, onehop_cap: int = 20):
        self._net = network
        self._judge = judge
        self._max_hops = max_hops
        self._node_budget = node_budget
        self._max_candidates = max_candidates
        self._max_pairs = max_pairs
        self._onehop_cap = onehop_cap

    def expand(self, seeds: list[str], query: str | None = None) -> SuggestionResult:
        seeds = list(dict.fromkeys(seeds))   # dedupe, keep order
        if len(seeds) >= 2:
            return self._paths(seeds, query or "")
        if len(seeds) == 1:
            return self._one_hop(seeds[0])
        return SuggestionResult(nodes=[], edges=[])

    def _paths(self, seeds: list[str], query: str) -> SuggestionResult:
        candidates: dict[tuple[str, str], list[list[Edge]]] = {}
        for a, b in list(combinations(seeds, 2))[: self._max_pairs]:
            paths = self._between(a, b)
            if paths:
                candidates[(a, b)] = paths
        if not candidates:
            return SuggestionResult(nodes=[], edges=[])
        labels = {nid: self._net.label(nid) for pair in candidates for nid in pair}
        for cands in candidates.values():
            for path in cands:
                for e in path:
                    labels.setdefault(e.source_id, self._net.label(e.source_id))
                    labels.setdefault(e.target_id, self._net.label(e.target_id))
        shortest = {pair: cands[0] for pair, cands in candidates.items()}
        if self._judge is not None:
            try:
                chosen = self._judge.select(query, candidates, labels)
            except Exception:
                logger.warning("path judge raised; using shortest candidates", exc_info=True)
                chosen = shortest
        else:
            chosen = shortest
        return self._assemble([e for path in chosen.values() for e in path], labels)

    def _between(self, a: str, b: str) -> list[list[Edge]]:
        paths = shortest_paths(self._net, a, b, max_hops=self._max_hops, directed=True,
                               node_budget=self._node_budget, max_candidates=self._max_candidates)
        if not paths:
            paths = shortest_paths(
                self._net, a, b, max_hops=self._max_hops, directed=False,
                node_budget=self._node_budget, max_candidates=self._max_candidates,
            )
        return paths

    def _one_hop(self, seed: str) -> SuggestionResult:
        nbrs = self._net.out_edges(seed) + self._net.in_edges(seed)
        nbrs.sort(key=lambda nb: (-len(nb.edge.suggested_by), nb.edge.id))
        edges = [nb.edge for nb in nbrs[: self._onehop_cap]]
        labels = {seed: self._net.label(seed)}
        for nb in nbrs[: self._onehop_cap]:
            labels[nb.node_id] = nb.label
        return self._assemble(edges, labels)

    def _assemble(self, edges: list[Edge], labels: dict[str, str]) -> SuggestionResult:
        nodes: dict[str, Node] = {}
        out_edges: dict[tuple[str, str, str], Edge] = {}
        for e in edges:
            for nid in (e.source_id, e.target_id):
                nodes.setdefault(nid, Node(
                    id=nid, type=NodeType.TARGET, label=labels.get(nid, nid),
                    grounding=OntologyTermProvenance(ontology="UniProt", term_id=nid)))
            key = (e.source_id, e.target_id, e.relation)
            existing = out_edges.get(key)
            if existing is None:
                out_edges[key] = e
            else:
                out_edges[key] = existing.model_copy(
                    update={"suggested_by": existing.suggested_by + e.suggested_by})
        return SuggestionResult(nodes=list(nodes.values()), edges=list(out_edges.values()))

    def check_pair(self, source: str, target: str) -> Edge | None:
        """Directed 1-hop check (source -> target only); for EdgeSuggester protocol
        completeness. Unlike path expansion, it does NOT fall back to undirected."""
        for nb in self._net.out_edges(source):
            if nb.node_id == target:
                return nb.edge
        return None
