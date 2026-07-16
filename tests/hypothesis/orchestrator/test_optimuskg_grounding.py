"""Tests for OptimusKG-backed grounding (injected loader; no network)."""

import polars as pl

from quration.hypothesis.graph import Node, NodeType
from quration.hypothesis.orchestrator.optimuskg_grounding import (
    OptimusKGGroundingService,
    candidate_labels,
    clean_label,
)

# --- fake OptimusKG node tables (matching the real schema we care about) ---

_GENES = pl.DataFrame(
    {
        "id": ["ENSG00000146648", "ENSG00000183087"],
        "label": ["GEN", "GEN"],
        "properties": [
            {
                "symbol": "EGFR", "name": "epidermal growth factor receptor",
                "symbol_synonyms": ["ERBB1", "HER1"], "synonyms": [],
                "associated_proteins": [
                    {"id": "P00533", "source": "uniprot_swissprot"},
                    {"id": "C9JYS6", "source": "uniprot_trembl"},
                ],
            },
            {
                "symbol": "GENA", "name": "growth arrest specific 6",
                "symbol_synonyms": ["GENBLG"], "synonyms": ["GENB ligand"],
                "associated_proteins": [{"id": "P00001", "source": "uniprot_swissprot"}],
            },
        ],
    }
)
_DISEASES = pl.DataFrame(
    {
        "id": ["EFO_0020001"],
        "label": ["DIS"],
        "properties": [{"name": "drug resistance", "synonyms": ["drug resistant"]}],
    }
)
_DRUGS = pl.DataFrame(
    {
        "id": ["CHEMBL941"],
        "label": ["DRU"],
        "properties": [{"name": "imatinib", "synonyms": ["gleevec"]}],
    }
)

_TABLES = {
    "nodes/gene.parquet": _GENES,
    "nodes/disease.parquet": _DISEASES,
    "nodes/drug.parquet": _DRUGS,
}


def _svc():
    return OptimusKGGroundingService(loader=lambda path: _TABLES[path])


def _node(label, ntype):
    return Node(id="n1", type=ntype, label=label)


def test_clean_label_strips_parenthetical():
    assert clean_label("GENA (GENB ligand)") == "GENA"
    assert clean_label("  EGFR ") == "EGFR"


def test_gene_grounds_to_swissprot_uniprot():
    p = _svc().ground(_node("EGFR", NodeType.TARGET))
    assert p.found and p.proposed_edit.ontology == "UniProt"
    assert p.proposed_edit.term_id == "P00533"
    assert p.proposed_edit.node_id == "n1"


def test_compound_node_falls_back_to_gene_table():
    # GENA is a protein mistyped as compound; the drug probe misses, gene probe hits.
    p = _svc().ground(_node("GENA (GENB ligand)", NodeType.COMPOUND))
    assert p.found and p.proposed_edit.ontology == "UniProt"
    assert p.proposed_edit.term_id == "P00001"


def test_disease_grounds_with_split_ontology_id():
    p = _svc().ground(_node("drug resistance", NodeType.PHENOTYPE))
    assert p.found
    assert p.proposed_edit.ontology == "EFO" and p.proposed_edit.term_id == "0020001"


def test_drug_grounds_to_chembl():
    p = _svc().ground(_node("imatinib", NodeType.COMPOUND))
    assert p.found
    assert p.proposed_edit.ontology == "ChEMBL" and p.proposed_edit.term_id == "CHEMBL941"


def test_synonym_hit():
    p = _svc().ground(_node("HER1", NodeType.TARGET))  # EGFR symbol synonym
    assert p.found and p.proposed_edit.term_id == "P00533"


def test_miss_returns_not_found():
    p = _svc().ground(_node("Nonexiston", NodeType.TARGET))
    assert not p.found and p.proposed_edit is None


def test_disease_with_malformed_id_returns_not_found():
    diseases = pl.DataFrame({
        "id": ["EFO0020001"],  # no underscore -> malformed, must not emit a garbage edit
        "label": ["DIS"],
        "properties": [{"name": "weird disease", "synonyms": []}],
    })
    svc = OptimusKGGroundingService(loader=lambda path: {
        "nodes/gene.parquet": _GENES, "nodes/disease.parquet": diseases,
        "nodes/drug.parquet": _DRUGS}[path])
    assert not svc.ground(_node("weird disease", NodeType.DISEASE)).found


def test_null_synonym_list_does_not_crash():
    # A real table can carry null synonym lists; a symbol-miss must scan them safely.
    genes = pl.DataFrame({
        "id": ["ENSG1", "ENSG2"],
        "label": ["GEN", "GEN"],
        "properties": [
            {"symbol": "EGFR", "name": "egfr", "symbol_synonyms": ["HER1"],
             "synonyms": ["x"], "associated_proteins": [{"id": "P00533", "source": "uniprot_swissprot"}]},
            {"symbol": "GENA", "name": "GENA", "symbol_synonyms": None,
             "synonyms": None, "associated_proteins": [{"id": "P00001", "source": "uniprot_swissprot"}]},
        ],
    })
    svc = OptimusKGGroundingService(loader=lambda path: {
        "nodes/gene.parquet": genes, "nodes/disease.parquet": _DISEASES,
        "nodes/drug.parquet": _DRUGS}[path])
    # symbol match still works on the null-synonym row
    assert svc.ground(_node("GENA", NodeType.TARGET)).proposed_edit.term_id == "P00001"
    # a miss forces the synonym scan over a null list -> not-found, never raises
    assert not svc.ground(_node("notarealgene", NodeType.TARGET)).found


def test_candidate_labels_extracts_parenthetical_names_for_compound():
    cands = candidate_labels("Foo inhibitor (e.g., CMPD-1/foostatib)", NodeType.COMPOUND)
    assert cands[0] == "Foo inhibitor"  # cleaned label tried first
    assert "CMPD-1" in cands and "foostatib" in cands  # names rescued from parenthetical
    assert "Foo" not in cands  # no synthetic gene symbol for a compound (would mis-ground)


def test_candidate_labels_adds_leading_symbol_for_descriptive_target():
    cands = candidate_labels("GENX receptor tyrosine kinase", NodeType.TARGET)
    assert cands[0] == "GENX receptor tyrosine kinase"
    assert "GENX" in cands  # leading token offered as a likely gene symbol


def test_compound_with_parenthetical_name_grounds():
    # clean_label strips the parenthetical, leaving the class "Foo inhibitor"
    # (no entity) — the actual compound name lives inside the parenthetical.
    drugs = pl.DataFrame({
        "id": ["CHEMBL999999"], "label": ["DRU"],
        "properties": [{"name": "foostatib", "synonyms": ["CMPD-1"]}],
    })
    svc = OptimusKGGroundingService(loader=lambda path: {
        "nodes/gene.parquet": _GENES, "nodes/disease.parquet": _DISEASES,
        "nodes/drug.parquet": drugs}[path])
    p = svc.ground(_node("Foo inhibitor (e.g., CMPD-1/foostatib)", NodeType.COMPOUND))
    assert p.found and p.proposed_edit.ontology == "ChEMBL"
    assert p.proposed_edit.term_id == "CHEMBL999999"


def test_descriptive_target_label_grounds_via_leading_symbol():
    genes = pl.DataFrame({
        "id": ["ENSG_X"], "label": ["GEN"],
        "properties": [{"symbol": "GENX", "name": "GENX receptor tyrosine kinase",
                        "symbol_synonyms": ["GX1"], "synonyms": [],
                        "associated_proteins": [{"id": "P99999", "source": "uniprot_swissprot"}]}],
    })
    svc = OptimusKGGroundingService(loader=lambda path: {
        "nodes/gene.parquet": genes, "nodes/disease.parquet": _DISEASES,
        "nodes/drug.parquet": _DRUGS}[path])
    p = svc.ground(_node("GENX receptor tyrosine kinase", NodeType.TARGET))
    assert p.found and p.proposed_edit.term_id == "P99999"


def test_gene_synonym_struct_schema_matches():
    # Real gene tables carry `synonyms` as list[struct{label,source}] (not list[str]);
    # the synonym scan must handle that shape instead of silently failing.
    genes = pl.DataFrame({
        "id": ["ENSG_Y"], "label": ["GEN"],
        "properties": [{"symbol": "GENY", "name": "y gene", "symbol_synonyms": [],
                        "synonyms": [{"label": "alphagene", "source": "SRC"}],
                        "associated_proteins": [{"id": "P11111", "source": "uniprot_swissprot"}]}],
    })
    svc = OptimusKGGroundingService(loader=lambda path: {
        "nodes/gene.parquet": genes, "nodes/disease.parquet": _DISEASES,
        "nodes/drug.parquet": _DRUGS}[path])
    p = svc.ground(_node("alphagene", NodeType.TARGET))
    assert p.found and p.proposed_edit.term_id == "P11111"


def test_gene_without_swissprot_is_skipped():
    genes = pl.DataFrame({
        "id": ["ENSG1"], "label": ["GEN"],
        "properties": [{"symbol": "ORFX", "name": "orf x", "symbol_synonyms": [],
                        "synonyms": [], "associated_proteins": [
                            {"id": "ENSP1", "source": "ensembl_PRO"}]}],
    })
    svc = OptimusKGGroundingService(loader=lambda path: {"nodes/gene.parquet": genes,
                                                         "nodes/disease.parquet": _DISEASES,
                                                         "nodes/drug.parquet": _DRUGS}[path])
    p = svc.ground(_node("ORFX", NodeType.TARGET))
    assert not p.found


def test_pathway_node_does_not_gene_fallback():
    # Pathways have no OptimusKG node table; they must NOT borrow a gene match
    # (otherwise a pathway gets pinned to one protein). They miss here and are
    # expected to fall through to a pathway ontology (GO/Reactome) elsewhere.
    p = _svc().ground(_node("EGFR", NodeType.PATHWAY))
    assert not p.found
