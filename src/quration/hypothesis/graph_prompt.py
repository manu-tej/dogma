# src/quration/hypothesis/graph_prompt.py
"""Render a bounded, labeled neighborhood of a CausalGraph as LLM prompt text.

Pure: no I/O, no LLM. Node *labels* drive the arrows (the model reasons in gene
symbols), while the bracketed ``[id]`` handles let the model reference nodes and
edges in structured edit ops. Large hubs are trimmed to ``max_edges`` (focal edge
first, then more-cited edges) with an explicit "N more omitted" line so the model
never assumes the view is complete.
"""

from quration.hypothesis.graph import CausalGraph, Edge, Node
from quration.hypothesis.provenance import OntologyTermProvenance, ProteinStateProvenance


def _grounding_str(node: Node) -> str:
    g = node.grounding
    if isinstance(g, OntologyTermProvenance):
        return f"{g.ontology}:{g.term_id}"
    if isinstance(g, ProteinStateProvenance):
        return f"protein-state:{g.family_label}"
    return "ungrounded"


def _provenance_str(edge: Edge) -> str:
    if not edge.suggested_by:
        return "llm"
    sources: list[str] = []
    for prov in edge.suggested_by:
        if prov.source not in sources:
            sources.append(prov.source)
    first_ref = edge.suggested_by[0].reference
    head = f"{sources[0]}:PMID:{first_ref}" if first_ref.isdigit() else sources[0]
    return ",".join([head, *sources[1:]])


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def serialize_graph_for_llm(
    graph: CausalGraph,
    *,
    focus_node_ids: tuple[str, ...] = (),
    focus_edge_ids: tuple[str, ...] = (),
    max_edges: int = 40,
) -> str:
    """Render a focused neighborhood of ``graph`` as prompt text (see module docstring)."""
    label_by_id = {n.id: n.label for n in graph.nodes}

    def lbl(node_id: str) -> str:
        return label_by_id.get(node_id, node_id)

    # Explicit focus nodes mark the node block; focus edges mark the edge block.
    # The neighborhood (which edges to show) is anchored on both.
    explicit_focus_nodes = {nid for nid in focus_node_ids if graph.get_node(nid) is not None}
    focus_edges = tuple(eid for eid in focus_edge_ids if graph.get_edge(eid) is not None)
    focus_edge_set = set(focus_edges)
    neighborhood_nodes = set(explicit_focus_nodes)
    for eid in focus_edges:
        e = graph.get_edge(eid)
        neighborhood_nodes.update((e.source_id, e.target_id))

    total_nodes, total_edges = len(graph.nodes), len(graph.edges)

    # Choose the in-view edges + a human scope description.
    if total_edges <= max_edges:
        in_view, scope = list(graph.edges), "the full graph"
    elif neighborhood_nodes:
        seen: dict[str, Edge] = {}
        for nid in sorted(neighborhood_nodes):
            for e in graph.edges_incident(nid):
                seen.setdefault(e.id, e)
        in_view = list(seen.values())
        if focus_edge_set:
            scope = f"the neighborhood of edge [{sorted(focus_edge_set)[0]}]"
        else:
            scope = f"the neighborhood of node [{sorted(explicit_focus_nodes)[0]}]"
    else:
        in_view, scope = list(graph.edges), "the highest-provenance edges"

    # Focal edges first, then more-cited first, then id (deterministic). Cap.
    in_view.sort(key=lambda e: (e.id not in focus_edge_set, -len(e.suggested_by), e.id))
    shown = in_view[:max_edges]
    omitted = len(in_view) - len(shown)

    # Nodes to render: explicit focus nodes first, then endpoints of shown edges.
    node_ids: list[str] = []
    seen_n: set[str] = set()
    endpoint_ids = (x for e in shown for x in (e.source_id, e.target_id))
    for nid in [*sorted(explicit_focus_nodes), *endpoint_ids]:
        if nid not in seen_n:
            seen_n.add(nid)
            node_ids.append(nid)

    lines = [
        f'Hypothesis: "{graph.query}"',
        f"Graph: {_plural(total_nodes, 'node')}, {_plural(total_edges, 'edge')} — showing {scope}.",
        "",
        "Edges (FOCUS marked; [id] is the handle for edits):",
    ]
    epad = "FOCUS " if focus_edge_set else ""
    for e in shown:
        marker = "FOCUS " if e.id in focus_edge_set else " " * len(epad)
        lines.append(
            f"  {marker}[{e.id}] {lbl(e.source_id)} --{e.relation}--> {lbl(e.target_id)}"
            f"  ({e.state.value} · {_provenance_str(e)})"
        )
    if omitted:
        on = ", ".join(lbl(nid) for nid in sorted(neighborhood_nodes)) or "the graph"
        lines.append(f"  … {omitted} more edges on {on} omitted.")

    lines += ["", "Nodes:"]
    npad = "FOCUS " if explicit_focus_nodes else ""
    for nid in node_ids:
        node = graph.get_node(nid)
        marker = "FOCUS " if nid in explicit_focus_nodes else " " * len(npad)
        if node is None:
            lines.append(f"  {marker}[{nid}] {nid} (?, ungrounded)")
        else:
            lines.append(
                f"  {marker}[{nid}] {node.label} ({node.type.value}, {_grounding_str(node)})"
            )
    return "\n".join(lines)
