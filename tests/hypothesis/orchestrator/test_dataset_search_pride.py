"""Tests for find_multi (GEO + PRIDE) on RealDatasetSearchService."""

import types

import pytest

from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
from quration.hypothesis.orchestrator.dataset_search import (
    DatasetCandidate,
    RealDatasetSearchService,
)
from quration.models.proteomics_search import (
    ProteomicsDatasetCandidate,
    ProteomicsExperimentalDesign,
    ProteomicsSearchResult,
)


def _graph() -> CausalGraph:
    g = CausalGraph(id="g-pride", query="does EGFR drive resistance?")
    g.add_node(Node(id="egfr", type=NodeType.TARGET, label="EGFR"))
    g.add_node(Node(id="kras", type=NodeType.TARGET, label="KRAS"))
    g.add_edge(Edge(id="e1", source_id="egfr", target_id="kras", relation="up-regulates activity"))
    return g


def _fake_pride_candidate(accession: str = "PXD012345") -> ProteomicsDatasetCandidate:
    design = ProteomicsExperimentalDesign(
        conditions=None, design_type="case-control",
        instrument="Orbitrap", quantification_method="TMT",
        acquisition_strategy="DDA", notes="", is_partial=False,
    )
    return ProteomicsDatasetCandidate(
        accession=accession,
        title="Phosphoproteomics EGFR KRAS",
        description="EGFR KRAS phospho study",
        experimental_design=design,
        n_assays=12,
        organism="Homo sapiens",
        instruments=["Orbitrap"],
        experiment_types=["Phosphoproteomics"],
        quantification_methods=["TMT"],
        tissues=["lung"],
        diseases=["lung cancer"],
        cell_types=["A549"],
        primary_doi=None,
        primary_pmid="12345678",
        has_protein_data=True,
        has_peptide_data=True,
        has_quantification_data=True,
        match_reasons=["EGFR", "KRAS"],
        raw_metadata={},
    )


def _fake_proteomics_search_fn(spec, max_results=8):
    result = types.SimpleNamespace()
    result.candidates = [_fake_pride_candidate("PXD012345")]
    return result


def _geo_search_fn_empty(spec, max_results=8):
    return []


def test_find_multi_includes_pride_candidate():
    svc = RealDatasetSearchService(
        geo_search_fn=_geo_search_fn_empty,
        proteomics_search_fn=_fake_proteomics_search_fn,
    )
    results = svc.find_multi(_graph(), "e1")
    pride_hits = [c for c in results if c.source == "pride"]
    assert pride_hits, "expected at least one PRIDE candidate"
    assert pride_hits[0].accession == "PXD012345"


def test_find_multi_pride_has_correct_fields():
    svc = RealDatasetSearchService(
        geo_search_fn=_geo_search_fn_empty,
        proteomics_search_fn=_fake_proteomics_search_fn,
    )
    results = svc.find_multi(_graph(), "e1")
    c = next(r for r in results if r.source == "pride")
    assert c.accession == "PXD012345"
    assert c.title == "Phosphoproteomics EGFR KRAS"
    assert c.n_samples == 12
    assert c.organism == "Homo sapiens"
    assert c.assay == "Phosphoproteomics"
    assert c.primary_pmid == "12345678"
    assert c.suggested_pipeline == "nf-core/proteomicslfq"


def test_find_multi_combines_geo_and_pride():
    from quration.models.geo_search import ExperimentalDesign, GeoDatasetCandidate

    geo_candidate = GeoDatasetCandidate(
        gse_id="GSE999", title="GEO study", summary="s",
        experimental_design=ExperimentalDesign(conditions=None, design_type="case-control",
                                               tech="RNA-Seq", notes="", is_partial=False),
        n_samples=6, organism="Homo sapiens", platforms=["GPL"], primary_pmid="111",
        maybe_has_survival_data=False, match_reasons=["r"], raw_metadata={})

    def geo_fn(spec, max_results=8):
        return [geo_candidate]

    svc = RealDatasetSearchService(
        geo_search_fn=geo_fn,
        proteomics_search_fn=_fake_proteomics_search_fn,
    )
    results = svc.find_multi(_graph(), "e1")
    sources = {c.source for c in results}
    assert "geo" in sources
    assert "pride" in sources


def test_find_multi_degrades_gracefully_when_pride_fails():
    def boom(spec, max_results=8):
        raise RuntimeError("PRIDE network down")

    svc = RealDatasetSearchService(
        geo_search_fn=_geo_search_fn_empty,
        proteomics_search_fn=boom,
    )
    # Should return GEO-only (empty here), not raise
    results = svc.find_multi(_graph(), "e1")
    assert all(c.source == "geo" for c in results)


def test_find_multi_unknown_edge_returns_empty():
    svc = RealDatasetSearchService(
        geo_search_fn=_geo_search_fn_empty,
        proteomics_search_fn=_fake_proteomics_search_fn,
    )
    assert svc.find_multi(_graph(), "no-such-edge") == []
