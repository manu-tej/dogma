import pytest

from quration.hypothesis.evidence import EvidenceRecord, ResolverProvenance
from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
from quration.hypothesis.repository import InMemoryHypothesisRepository
from quration.hypothesis.store.sqlite_repository import SqliteHypothesisRepository


def _rec():
    return EvidenceRecord(edge_id="e1", claim_signature=("s", "t", "r"),
                          measured_vs_claimed="x", directness="proxy_modality",
                          provenance=ResolverProvenance())


def _graph():
    return CausalGraph(id="g1", query="q",
                       nodes=[Node(id="s", type=NodeType.TARGET, label="S"),
                              Node(id="t", type=NodeType.TARGET, label="T")],
                       edges=[Edge(id="e1", source_id="s", target_id="t", relation="r")])


@pytest.mark.parametrize("repo_factory", [InMemoryHypothesisRepository, SqliteHypothesisRepository])
def test_records_roundtrip_and_do_not_flip_state(repo_factory):
    repo = repo_factory()
    repo.save_graph(_graph())
    repo.add_evidence_record("g1", _rec())
    got = repo.evidence_records_for("g1", "e1")
    assert len(got) == 1 and got[0].directness == "proxy_modality"
    assert repo.get_graph("g1").get_edge("e1").state.value == "untested"
