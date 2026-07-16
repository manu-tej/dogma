# tests/hypothesis/orchestrator/test_ideal_readout.py
from quration.hypothesis.graph import Edge, Node, NodeType
from quration.hypothesis.provenance import (
    OntologyTermProvenance, ProteinModification, ProteinStateProvenance,
)
from quration.hypothesis.orchestrator.ideal_readout import (
    derive_ideal_readout, is_not_evaluable,
)


def _edge(relation):
    return Edge(id="e1", source_id="s", target_id="t", relation=relation)


def test_phospho_state_target_overrides_verb():
    # "AKT activates pAKT" — verb says activation, but the TARGET is a phospho-state,
    # so the ideal readout must be phospho, not differential expression.
    target = Node(id="t", type=NodeType.TARGET, label="pAKT (S473)",
                  grounding=ProteinStateProvenance(
                      family_label="AKT (phospho-S473)", members=[],
                      modification=ProteinModification(residues=["S473"])))
    spec = derive_ideal_readout(_edge("activates"), target)
    assert spec.modality == "phospho"


def test_transcriptional_relation_is_transcript_modality():
    target = Node(id="t", type=NodeType.TARGET, label="MDM2",
                  grounding=OntologyTermProvenance(ontology="HGNC", term_id="HGNC:6973"))
    spec = derive_ideal_readout(_edge("represses"), target)
    assert spec.modality == "transcript"


def test_definitional_relation_is_not_evaluable():
    assert is_not_evaluable("manifests as") is True
    assert is_not_evaluable("phosphorylates") is False
