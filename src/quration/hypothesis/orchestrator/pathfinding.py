# src/quration/hypothesis/orchestrator/pathfinding.py
"""Bounded bidirectional BFS over a Network -> near-shortest candidate paths.

Pure: all I/O is behind the injected Network. Returns up to `max_candidates`
shortest paths (diverse by meeting node) as ordered ``list[Edge]`` from source to
target. The cheap 2-hop case (A->C->B) is found from the source and target fetches
alone (their neighbor sets intersect) — C is never expanded.
"""

from quration.hypothesis.graph import Edge


def shortest_paths(
    net, source: str, target: str, *,
    max_hops: int = 4, directed: bool = True,
    node_budget: int = 60, max_candidates: int = 4,
) -> list[list[Edge]]:
    if source == target:
        return []

    def fwd_nbrs(node):
        nbrs = list(net.out_edges(node))
        if not directed:
            nbrs += list(net.in_edges(node))
        return nbrs

    def bwd_nbrs(node):
        nbrs = list(net.in_edges(node))
        if not directed:
            nbrs += list(net.out_edges(node))
        return nbrs

    # node -> (parent_node, incoming_edge)
    fwd_parent: dict[str, tuple[str, Edge] | None] = {source: None}
    # node -> (child_node, outgoing_edge)
    bwd_parent: dict[str, tuple[str, Edge] | None] = {target: None}
    fwd_frontier = [source]
    bwd_frontier = [target]
    expanded = 0   # node expansions performed; node_budget caps these, not raw network fetches

    def path_for(meet: str) -> list[Edge]:
        fwd: list[Edge] = []
        cur = meet
        while fwd_parent[cur] is not None:
            prev, edge = fwd_parent[cur]
            fwd.append(edge)
            cur = prev
        fwd.reverse()
        bwd: list[Edge] = []
        cur = meet
        while bwd_parent[cur] is not None:
            nxt, edge = bwd_parent[cur]
            bwd.append(edge)
            cur = nxt
        return fwd + bwd

    def finish(meets: list[str]) -> list[list[Edge]]:
        out: list[list[Edge]] = []
        seen: set[tuple] = set()
        for m in sorted(set(meets)):
            path = path_for(m)
            key = tuple(e.id for e in path)
            if path and len(path) <= max_hops and key not in seen:
                seen.add(key)
                out.append(path)
        out.sort(key=lambda p: (len(p), tuple(e.id for e in p)))
        return out[:max_candidates]

    def expand_fwd() -> tuple[list[str], list[str]]:
        """Expand one layer of fwd_frontier. Returns (new_frontier, meets)."""
        nonlocal expanded
        nxt, meets = [], []
        for node in fwd_frontier:
            if expanded >= node_budget:
                break
            expanded += 1
            for nb in fwd_nbrs(node):
                if nb.node_id in bwd_parent:
                    fwd_parent.setdefault(nb.node_id, (node, nb.edge))
                    meets.append(nb.node_id)
                elif nb.node_id not in fwd_parent:
                    fwd_parent[nb.node_id] = (node, nb.edge)
                    nxt.append(nb.node_id)
        return nxt, meets

    def expand_bwd() -> tuple[list[str], list[str]]:
        """Expand one layer of bwd_frontier. Returns (new_frontier, meets)."""
        nonlocal expanded
        nxt, meets = [], []
        for node in bwd_frontier:
            if expanded >= node_budget:
                break
            expanded += 1
            for nb in bwd_nbrs(node):
                if nb.node_id in fwd_parent:
                    bwd_parent.setdefault(nb.node_id, (node, nb.edge))
                    meets.append(nb.node_id)
                elif nb.node_id not in bwd_parent:
                    bwd_parent[nb.node_id] = (node, nb.edge)
                    nxt.append(nb.node_id)
        return nxt, meets

    while fwd_frontier and bwd_frontier and expanded < node_budget:
        # Expand the smaller frontier first within a round to bias toward meeting.
        if len(fwd_frontier) <= len(bwd_frontier):
            # Expand fwd, then bwd in the same round.
            fwd_nxt, fwd_meets = expand_fwd()
            if fwd_meets:
                return finish(fwd_meets)
            fwd_frontier[:] = fwd_nxt

            if bwd_frontier and expanded < node_budget:
                bwd_nxt, bwd_meets = expand_bwd()
                if bwd_meets:
                    return finish(bwd_meets)
                bwd_frontier[:] = bwd_nxt
        else:
            # Expand bwd, then fwd in the same round.
            bwd_nxt, bwd_meets = expand_bwd()
            if bwd_meets:
                return finish(bwd_meets)
            bwd_frontier[:] = bwd_nxt

            if fwd_frontier and expanded < node_budget:
                fwd_nxt, fwd_meets = expand_fwd()
                if fwd_meets:
                    return finish(fwd_meets)
                fwd_frontier[:] = fwd_nxt

    return []
