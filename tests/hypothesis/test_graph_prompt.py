# tests/hypothesis/test_graph_prompt.py
"""Tests for serialize_graph_for_llm (pure graph -> prompt text)."""

from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
from quration.hypothesis.graph_prompt import serialize_graph_for_llm
from quration.hypothesis.provenance import (
    KGEdgeProvenance,
    OntologyTermProvenance,
    ProteinModification,
    ProteinStateProvenance,
)


def _kg(source, ref=""):
    return KGEdgeProvenance(source=source, reference=ref)


def _small_graph():
    g = CausalGraph(id="g", query="does EGFR drive resistance?")
    g.add_node(Node(id="P00533", type=NodeType.TARGET, label="EGFR",
                    grounding=OntologyTermProvenance(ontology="UniProt", term_id="P00533")))
    g.add_node(Node(id="P01116", type=NodeType.TARGET, label="KRAS",
                    grounding=OntologyTermProvenance(ontology="UniProt", term_id="P01116")))
    g.add_node(Node(id="RESIST", type=NodeType.PHENOTYPE, label="drug resistance"))
    g.add_edge(Edge(id="e12", source_id="P00533", target_id="P01116", relation="activates",
                    suggested_by=[_kg("signor", "12345678")]))
    g.add_edge(Edge(id="e31", source_id="P01116", target_id="RESIST", relation="drives"))
    return g


def test_header_includes_query_and_counts():
    out = serialize_graph_for_llm(_small_graph(), focus_edge_ids=("e12",))
    assert 'Hypothesis: "does EGFR drive resistance?"' in out
    assert "Graph: 3 nodes, 2 edges" in out


def test_arrows_use_labels_not_accessions():
    out = serialize_graph_for_llm(_small_graph(), focus_edge_ids=("e12",))
    assert "EGFR --activates--> KRAS" in out
    assert "P00533 --activates" not in out


def test_focal_edge_marked_and_first():
    out = serialize_graph_for_llm(_small_graph(), focus_edge_ids=("e12",))
    edge_lines = [ln for ln in out.splitlines() if "-->" in ln]
    assert edge_lines[0].lstrip().startswith("FOCUS [e12]")


def test_edge_and_node_ids_are_handles():
    out = serialize_graph_for_llm(_small_graph(), focus_edge_ids=("e12",))
    assert "[e12]" in out and "[e31]" in out
    assert "[P00533]" in out and "[RESIST]" in out


def test_provenance_and_state_tags():
    out = serialize_graph_for_llm(_small_graph(), focus_edge_ids=("e12",))
    assert "(untested · signor:PMID:12345678)" in out
    assert "(untested · llm)" in out


def test_multi_source_provenance_merges():
    g = _small_graph()
    g.get_edge("e31").suggested_by = [_kg("signor"), _kg("collectri")]
    out = serialize_graph_for_llm(g, focus_edge_ids=("e12",))
    assert "signor,collectri" in out


def test_edge_focus_does_not_mark_nodes():
    out = serialize_graph_for_llm(_small_graph(), focus_edge_ids=("e12",))
    assert "FOCUS [e12]" in out
    assert "FOCUS [P00533]" not in out and "FOCUS [P01116]" not in out


def test_node_focus_marks_node_not_edge():
    out = serialize_graph_for_llm(_small_graph(), focus_node_ids=("P01116",))
    assert "FOCUS [P01116] KRAS" in out
    assert "FOCUS [e" not in out
    assert "[e12]" in out and "[e31]" in out


def test_ungrounded_and_protein_state_render():
    g = _small_graph()
    g.add_node(Node(id="pAKT", type=NodeType.TARGET, label="pAKT",
                    grounding=ProteinStateProvenance(
                        family_label="AKT (phospho)",
                        modification=ProteinModification(residues=["S473"]))))
    g.add_edge(Edge(id="e99", source_id="P01116", target_id="pAKT", relation="activates"))
    out = serialize_graph_for_llm(g, focus_node_ids=("P01116",))
    assert "drug resistance (phenotype, ungrounded)" in out
    assert "protein-state:AKT (phospho)" in out


def test_small_graph_renders_fully():
    out = serialize_graph_for_llm(_small_graph())
    assert "showing the full graph" in out
    assert "[e12]" in out and "[e31]" in out


def test_unknown_focus_id_is_ignored():
    out = serialize_graph_for_llm(_small_graph(), focus_edge_ids=("nope",))
    assert "Graph: 3 nodes, 2 edges" in out


def _hub_graph(n_spokes=60):
    g = CausalGraph(id="g", query="hub")
    g.add_node(Node(id="HUB", type=NodeType.TARGET, label="EGFR"))
    for i in range(n_spokes):
        sid = f"S{i:02d}"
        g.add_node(Node(id=sid, type=NodeType.TARGET, label=f"GENE{i:02d}"))
        prov = [_kg("signor")] if i < 5 else []
        g.add_edge(Edge(id=f"h{i:02d}", source_id="HUB", target_id=sid,
                        relation="activates", suggested_by=prov))
    return g


def test_hub_is_trimmed_with_omitted_note():
    out = serialize_graph_for_llm(_hub_graph(60), focus_node_ids=("HUB",), max_edges=40)
    edge_lines = [ln for ln in out.splitlines() if "-->" in ln]
    assert len(edge_lines) == 40
    assert "… 20 more edges on EGFR omitted." in out


def test_hub_ranking_more_cited_first():
    out = serialize_graph_for_llm(_hub_graph(60), focus_node_ids=("HUB",), max_edges=40)
    edge_lines = [ln for ln in out.splitlines() if "-->" in ln]
    shown_ids = {ln.split("[")[1].split("]")[0] for ln in edge_lines}
    assert {f"h{i:02d}" for i in range(5)}.issubset(shown_ids)


def test_deterministic():
    g = _hub_graph(60)
    a = serialize_graph_for_llm(g, focus_node_ids=("HUB",), max_edges=40)
    b = serialize_graph_for_llm(g, focus_node_ids=("HUB",), max_edges=40)
    assert a == b


def test_large_no_focus_shows_most_cited():
    g = _hub_graph(60)
    out = serialize_graph_for_llm(g, max_edges=10)
    assert "the highest-provenance edges" in out
    edge_lines = [ln for ln in out.splitlines() if "-->" in ln]
    shown_ids = {ln.split("[")[1].split("]")[0] for ln in edge_lines}
    assert {f"h{i:02d}" for i in range(5)}.issubset(shown_ids)
