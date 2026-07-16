"""Tests for per-edge dataset discovery (GEO only) and attach-ready candidates."""

from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
from quration.hypothesis.orchestrator.dataset_search import (
    DatasetCandidate,
    DemoDatasetSearchService,
    RealDatasetSearchService,
    suggest_pipeline,
)
from quration.models.geo_search import ExperimentalDesign, GeoDatasetCandidate


def _graph() -> CausalGraph:
    g = CausalGraph(id="g", query="does EGFR drive resistance?")
    g.add_node(Node(id="egfr", type=NodeType.TARGET, label="EGFR"))
    g.add_node(Node(id="kras", type=NodeType.TARGET, label="KRAS"))
    g.add_node(Node(id="res", type=NodeType.PHENOTYPE, label="drug resistance"))
    g.add_edge(Edge(id="e1", source_id="egfr", target_id="res", relation="drives"))
    return g


def _geo_cand(gse, n=10, reasons=1):
    return GeoDatasetCandidate(
        gse_id=gse, title=f"{gse} title", summary="s",
        experimental_design=ExperimentalDesign(conditions=None, design_type="case-control",
                                               tech="RNA-Seq", notes="", is_partial=False),
        n_samples=n, organism="Homo sapiens", platforms=["GPL"], primary_pmid="111",
        maybe_has_survival_data=False, match_reasons=["r"] * reasons, raw_metadata={})


def test_suggest_pipeline_geo_rnaseq_defaults_to_differentialabundance():
    # A quantitative causal-claim test wants the DE pipeline, not bare alignment.
    assert suggest_pipeline("geo", "RNA-Seq") == "nf-core/differentialabundance"
    assert suggest_pipeline("geo", None) == "nf-core/differentialabundance"


def test_real_search_returns_geo_only_with_pipeline():
    geo_fn = lambda spec, max_results=8: [_geo_cand("GSE1", n=5, reasons=2)]
    svc = RealDatasetSearchService(geo_search_fn=geo_fn)
    out = svc.find(_graph(), "e1")
    assert [c.accession for c in out] == ["GSE1"]
    assert out[0].source == "geo"
    assert out[0].suggested_pipeline == "nf-core/differentialabundance"


def test_real_search_ranks_by_match_reasons_then_samples():
    geo_fn = lambda spec, max_results=8: [_geo_cand("GSE_low", n=2, reasons=1),
                                          _geo_cand("GSE_high", n=99, reasons=3)]
    svc = RealDatasetSearchService(geo_search_fn=geo_fn)
    out = svc.find(_graph(), "e1")
    assert [c.accession for c in out] == ["GSE_high", "GSE_low"]


def test_real_search_caps_geo_results():
    geo_fn = lambda spec, max_results=8: [_geo_cand(f"GSE{i}", n=100, reasons=3) for i in range(8)]
    svc = RealDatasetSearchService(geo_search_fn=geo_fn, max_results=4)
    out = svc.find(_graph(), "e1")
    assert len(out) == 4
    assert all(c.source == "geo" for c in out)


def test_real_search_returns_empty_when_geo_fails():
    def boom(spec, max_results=8):
        raise RuntimeError("GEO down")
    svc = RealDatasetSearchService(geo_search_fn=boom)
    assert svc.find(_graph(), "e1") == []


def test_real_search_builds_spec_from_edge_endpoints():
    captured = {}
    def geo_fn(spec, max_results=8):
        captured["spec"] = spec
        return []
    svc = RealDatasetSearchService(geo_search_fn=geo_fn)
    svc.find(_graph(), "e1")
    spec = captured["spec"]
    assert "EGFR" in spec.targets_or_genes              # TARGET endpoint -> gene
    assert "drug resistance" in spec.disease_terms      # PHENOTYPE endpoint -> disease term
    assert any("EGFR drive resistance" in k for k in spec.study_keywords)  # graph query -> keywords


def test_demo_search_is_offline_and_deterministic_geo_only():
    out = DemoDatasetSearchService().find(_graph(), "e1")
    assert len(out) == 1
    assert out[0].source == "geo"
    assert out[0].accession == "GSE-DEMO"
    assert out[0].n_samples is None
    assert any("synthetic demo" in reason for reason in out[0].match_reasons)
    assert out[0].suggested_pipeline
    assert all(isinstance(c, DatasetCandidate) for c in out)
