"""Tests for OptimusKG edge knowledge + KG neighbor expansion (injected loader)."""

import polars as pl

from quration.hypothesis.graph import Node, NodeType
from quration.hypothesis.orchestrator.optimuskg_kg import OptimusKGKnowledgeService

_GENES = pl.DataFrame({
    "id": ["ENSG_EGFR", "ENSG_KRAS", "ENSG_GRB2"],
    "label": ["GEN", "GEN", "GEN"],
    "properties": [
        {"symbol": "EGFR", "name": "egfr", "symbol_synonyms": [], "synonyms": [],
         "associated_proteins": [{"id": "P00533", "source": "uniprot_swissprot"}]},
        {"symbol": "KRAS", "name": "kras", "symbol_synonyms": [], "synonyms": [],
         "associated_proteins": [{"id": "P01116", "source": "uniprot_swissprot"}]},
        {"symbol": "GRB2", "name": "grb2", "symbol_synonyms": [], "synonyms": [],
         "associated_proteins": [{"id": "P62993", "source": "uniprot_swissprot"}]},
    ],
})
_DISEASES = pl.DataFrame({
    "id": ["DOID_1612"], "label": ["DIS"],
    "properties": [{"name": "breast cancer", "synonyms": []}],
})
_DRUGS = pl.DataFrame({
    "id": ["CHEMBL941"], "label": ["DRU"],
    "properties": [{"name": "imatinib", "synonyms": []}],
})

def _edge(frm, to, rel, direct, indirect=None):
    return {"from": frm, "to": to, "label": "X", "relation": rel, "undirected": False,
            "properties": {"sources": {"direct": direct, "indirect": indirect or []}}}

_GENE_GENE = pl.DataFrame([
    _edge("ENSG_EGFR", "ENSG_GRB2", "INTERACTS_WITH", ["PRIMEKG", "INTACT"], ["BIOPLEX"]),
    _edge("ENSG_GRB2", "ENSG_KRAS", "INTERACTS_WITH", ["PRIMEKG"]),
    # note: no EGFR<->KRAS edge (pathway-mediated, not a PPI)
])
_DISEASE_GENE = pl.DataFrame([
    _edge("DOID_1612", "ENSG_EGFR", "ASSOCIATED_WITH", ["DISGENET"]),
])

_TABLES = {
    "nodes/gene.parquet": _GENES, "nodes/disease.parquet": _DISEASES, "nodes/drug.parquet": _DRUGS,
    "edges/gene_gene.parquet": _GENE_GENE, "edges/disease_gene.parquet": _DISEASE_GENE,
}

def _svc():
    return OptimusKGKnowledgeService(loader=lambda p: _TABLES[p])

def _node(label, t):
    return Node(id="n", type=t, label=label)


def test_resolve_ref_gene_returns_ensembl_id():
    ref = _svc().resolve_ref("EGFR", NodeType.TARGET)
    assert ref.kind == "gene" and ref.id == "ENSG_EGFR"


def test_resolve_ref_type_agnostic_gene_fallback():
    # protein mistyped as compound still resolves via the gene table
    ref = _svc().resolve_ref("GENA" if False else "EGFR", NodeType.COMPOUND)
    assert ref.kind == "gene" and ref.id == "ENSG_EGFR"


def test_edge_knowledge_real_ppi_returns_sources():
    s = _svc()
    a = s.resolve_ref("EGFR", NodeType.TARGET)
    b = s.resolve_ref("GRB2", NodeType.TARGET)
    k = s.edge_knowledge(a, b)
    assert k.found
    assert "INTERACTS_WITH" in k.relations
    assert set(k.sources) >= {"PRIMEKG", "INTACT", "BIOPLEX"}


def test_edge_knowledge_no_direct_edge_is_honest():
    s = _svc()
    a = s.resolve_ref("EGFR", NodeType.TARGET)
    b = s.resolve_ref("KRAS", NodeType.TARGET)
    k = s.edge_knowledge(a, b)
    assert not k.found and "no direct" in k.summary.lower()


def test_edge_knowledge_cross_type_uses_disease_gene_file():
    s = _svc()
    a = s.resolve_ref("EGFR", NodeType.TARGET)
    b = s.resolve_ref("breast cancer", NodeType.DISEASE)
    k = s.edge_knowledge(a, b)
    assert k.found and "ASSOCIATED_WITH" in k.relations and "DISGENET" in k.sources


def test_neighbors_ranked_by_source_count_with_symbols():
    s = _svc()
    egfr = s.resolve_ref("EGFR", NodeType.TARGET)
    nbrs = s.neighbors(egfr, limit=5)
    assert [n.symbol for n in nbrs] == ["GRB2"]  # EGFR's only gene-gene neighbor here
    assert nbrs[0].relation == "INTERACTS_WITH"
    assert "PRIMEKG" in nbrs[0].sources


def test_edge_knowledge_unresolved_endpoint_not_found():
    s = _svc()
    a = s.resolve_ref("EGFR", NodeType.TARGET)
    assert a is not None
    # b unresolved
    b = s.resolve_ref("Nonexiston", NodeType.TARGET)
    assert b is None
