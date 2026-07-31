"""loop.record_known: a KG known-check is an auditable edge validation."""

from quration.hypothesis.epistemics import EdgeValidationStatus as S, ProposalSource
from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
from quration.hypothesis.orchestrator.demo import build_demo_loop
from quration.hypothesis.orchestrator.kg_knowledge import EdgeKnowledge
from quration.hypothesis.repository import InMemoryHypothesisRepository


def _loop_with_two_edges():
    repo = InMemoryHypothesisRepository()
    loop = build_demo_loop(repository=repo)
    g = CausalGraph(id="g", query="q")
    for nid in ("a", "b", "c"):
        g.add_node(Node(id=nid, type=NodeType.TARGET, label=nid.upper()))
    # proposal_source stated explicitly: the assertion below is that recording KG
    # knowledge leaves the proposal origin unchanged, so the origin has to be set
    # on purpose rather than inherited from the field default (which is SYSTEM —
    # an unstated origin must not claim an LLM proposed the edge).
    g.add_edge(Edge(id="e1", source_id="a", target_id="b", relation="activates",
                    proposal_source=ProposalSource.LLM))
    g.add_edge(Edge(id="e2", source_id="b", target_id="c", relation="inhibits",
                    proposal_source=ProposalSource.LLM))
    repo.save_graph(g)
    return loop, repo


def test_record_known_direct_marks_only_target_edge():
    loop, repo = _loop_with_two_edges()
    loop.record_known("g", "e1", EdgeKnowledge(
        found=True, relations=["INTERACTS_WITH"], sources=["APID", "INTACT"],
        summary="2 sources"), kg_source="optimuskg")
    g = repo.get_graph("g")
    e1 = g.get_edge("e1")
    assert e1.validation_status == S.KG_SUPPORTED_DIRECT
    assert e1.proposal_source == ProposalSource.LLM  # proposal origin unchanged
    assert e1.validations[-1].evidence is not None    # KG provenance attached
    assert g.get_edge("e2").validation_status == S.UNVALIDATED  # untouched


def test_record_known_not_found_marks_unsupported_and_keeps_edge():
    loop, repo = _loop_with_two_edges()
    loop.record_known("g", "e1", EdgeKnowledge(found=False, summary="no direct edge"))
    g = repo.get_graph("g")
    assert g.get_edge("e1").validation_status == S.UNSUPPORTED
    assert g.get_edge("e1") is not None  # not hidden/removed


def test_record_known_direct_is_a_link_not_exact_causal_support():
    # An "inhibits" claim must NOT be represented as exact causal support just
    # because the KG reports "INTERACTS_WITH" — it's recorded as a direct KG link.
    repo = InMemoryHypothesisRepository()
    loop = build_demo_loop(repository=repo)
    g = CausalGraph(id="g", query="q")
    g.add_node(Node(id="a", type=NodeType.TARGET, label="A"))
    g.add_node(Node(id="b", type=NodeType.TARGET, label="B"))
    g.add_edge(Edge(id="e1", source_id="a", target_id="b", relation="inhibits"))
    repo.save_graph(g)

    loop.record_known("g", "e1", EdgeKnowledge(
        found=True, relations=["INTERACTS_WITH"], sources=["APID"], summary="1"),
        kg_source="optimuskg")
    v = repo.get_graph("g").get_edge("e1").validations[-1]
    assert "link" in v.rationale.lower()              # framed as a link
    assert "INTERACTS_WITH" in v.rationale            # surfaces the KG's own relation
    assert "inhibits" in v.rationale                  # vs the claim's relation
    assert v.evidence.reference == "INTERACTS_WITH"   # evidence carries the KG relation, not "inhibits"


def test_record_known_is_idempotent_latest_kg_result_wins():
    loop, repo = _loop_with_two_edges()
    loop.record_known("g", "e1", EdgeKnowledge(
        found=True, relations=["INTERACTS_WITH"], sources=["APID"], summary="1"))
    # a later re-check now finds nothing
    loop.record_known("g", "e1", EdgeKnowledge(found=False, summary="gone"))
    assert repo.get_graph("g").get_edge("e1").validation_status == S.UNSUPPORTED
