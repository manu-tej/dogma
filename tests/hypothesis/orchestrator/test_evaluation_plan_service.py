# tests/hypothesis/orchestrator/test_evaluation_plan_service.py
from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
from quration.hypothesis.orchestrator.dataset_search import DatasetCandidate
from quration.hypothesis.orchestrator.evaluation_plan_service import EvaluationPlanService
from quration.hypothesis.orchestrator.readout_resolver import DemoReadoutResolver
from quration.hypothesis.repository import InMemoryHypothesisRepository


def _graph():
    g = CausalGraph(id="g1", query="q",
                    nodes=[Node(id="s", type=NodeType.TARGET, label="AKT"),
                           Node(id="t", type=NodeType.TARGET, label="MDM2")],
                    edges=[Edge(id="e1", source_id="s", target_id="t", relation="represses")])
    return g


def test_skeleton_is_edge_specific_without_resolving():
    svc = EvaluationPlanService(resolver=DemoReadoutResolver(), grounding_provider=None)
    plan = svc.build_skeleton(_graph(), "e1")
    assert plan.edge_id == "e1"
    assert plan.ideal_readout.modality == "transcript"
    assert plan.expected_direction == "decrease"      # "represses"
    assert plan.resolved_readout is None
    assert plan.method is None                          # provider None -> coverage gap, no method


def test_resolve_fills_dataset_and_persists_one_record():
    repo = InMemoryHypothesisRepository()
    g = _graph()
    repo.save_graph(g)
    svc = EvaluationPlanService(resolver=DemoReadoutResolver(), grounding_provider=None)
    plan = svc.resolve(g, "e1", candidates=[
        DatasetCandidate(source="geo", accession="GSE9", title="rna-seq", assay="RNA-Seq")], repo=repo)
    assert plan.resolved_readout is not None
    assert plan.directness is not None
    records = repo.evidence_records_for("g1", "e1")
    assert len(records) == 1
    assert records[0].directness == plan.directness
    # ledger fact must NOT flip the edge to EXAMINED
    assert repo.get_graph("g1").get_edge("e1").state.value == "untested"


def test_resolve_stamps_created_at_on_evidence_record():
    """EvidenceRecord.created_at must be populated (not None) after resolve."""
    repo = InMemoryHypothesisRepository()
    g = _graph()
    repo.save_graph(g)
    svc = EvaluationPlanService(resolver=DemoReadoutResolver(), grounding_provider=None)
    svc.resolve(g, "e1", candidates=[
        DatasetCandidate(source="geo", accession="GSE9", title="rna-seq", assay="RNA-Seq")], repo=repo)
    records = repo.evidence_records_for("g1", "e1")
    assert records[0].created_at is not None
    # Must be a parseable ISO-8601 string
    from datetime import datetime
    datetime.fromisoformat(records[0].created_at)
