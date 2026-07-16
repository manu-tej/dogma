"""Tests for the unified Provenance discriminated union."""

import pytest
from pydantic import TypeAdapter, ValidationError

from quration.hypothesis.provenance import (
    KGEdgeProvenance,
    LiteratureProvenance,
    OntologyTermProvenance,
    PipelineRunProvenance,
    Provenance,
)

_adapter = TypeAdapter(Provenance)


def test_ontology_term_parses_by_discriminator():
    p = _adapter.validate_python(
        {"kind": "ontology_term", "ontology": "EFO", "term_id": "EFO:0000305"}
    )
    assert isinstance(p, OntologyTermProvenance)
    assert p.term_id == "EFO:0000305"
    assert p.label is None


def test_kg_edge_parses_with_optional_count():
    p = _adapter.validate_python(
        {"kind": "kg_edge", "source": "signor", "reference": "SIG-123", "statement_count": 4}
    )
    assert isinstance(p, KGEdgeProvenance)
    assert p.source == "signor"
    assert p.statement_count == 4


def test_literature_and_pipeline_run_parse():
    lit = _adapter.validate_python({"kind": "literature", "pmid": "12345678"})
    run = _adapter.validate_python(
        {"kind": "pipeline_run", "run_id": "run_abc", "data_accession": "GSE123"}
    )
    assert isinstance(lit, LiteratureProvenance)
    assert isinstance(run, PipelineRunProvenance)
    assert run.data_accession == "GSE123"


def test_unknown_kind_rejected():
    with pytest.raises(ValidationError):
        _adapter.validate_python({"kind": "vibes", "note": "trust me"})


from quration.hypothesis.provenance import (
    OntologyTermProvenance,
    ProteinModification,
    ProteinStateProvenance,
)


def test_protein_state_provenance_round_trips():
    state = ProteinStateProvenance(
        family_label="AKT (phospho-S473/T308)",
        members=[
            OntologyTermProvenance(ontology="UniProt", term_id="P31749", label="AKT1"),
            OntologyTermProvenance(ontology="UniProt", term_id="P31751", label="AKT2"),
            OntologyTermProvenance(ontology="UniProt", term_id="Q9Y243", label="AKT3"),
        ],
        modification=ProteinModification(residues=["S473", "T308"]),
    )
    assert state.kind == "protein_state"
    assert state.resolved_to is None
    assert state.modification.kind == "phosphorylation"

    reparsed = ProteinStateProvenance.model_validate_json(state.model_dump_json())
    assert reparsed == state
    assert [m.term_id for m in reparsed.members] == ["P31749", "P31751", "Q9Y243"]


def test_protein_modification_defaults_to_empty_residues():
    mod = ProteinModification()
    assert mod.kind == "phosphorylation"
    assert mod.residues == []
