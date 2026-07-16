"""Tests for HypothesisLoop. Fakes + the `deps` fixture come from conftest.py
(auto-discovered by pytest — no import needed)."""

import pytest

from quration.hypothesis.graph import EdgeState
from quration.hypothesis.orchestrator.checkpoint import MethodChoice, ProposedTest, QueryKind
from quration.hypothesis.orchestrator.loop import (
    HypothesisLoop,
    MethodSelector,
    NullMethodSelector,
    PipelineRunner,
    Supervisor,
)


def _loop(deps):
    return HypothesisLoop(
        repository=deps["repository"],
        suggester=deps["suggester"],
        supervisor=deps["supervisor"],
        runner=deps["runner"],
        id_factory=lambda: "g-test",
    )


def test_protocols_are_runtime_checkable(deps):
    assert isinstance(deps["supervisor"], Supervisor)
    assert isinstance(deps["runner"], PipelineRunner)


def test_start_simple_returns_no_graph(deps):
    deps["supervisor"].kind = QueryKind.SIMPLE  # FakeSupervisor.triage returns self.kind
    result = _loop(deps).start("what tissue is EGFR in?")
    assert result.kind == QueryKind.SIMPLE
    assert result.graph_id is None
    assert deps["repository"].get_graph("g-test") is None


def test_start_investigative_assembles_and_saves_graph(deps):
    result = _loop(deps).start("does EGFR drive KRAS activity?")
    assert result.kind == QueryKind.INVESTIGATIVE
    assert result.graph_id == "g-test"
    graph = deps["repository"].get_graph("g-test")
    assert graph is not None
    assert graph.query == "does EGFR drive KRAS activity?"
    assert {n.id for n in graph.nodes} == {"P00533", "P01116"}
    assert [e.id for e in graph.edges] == ["SIGNOR-100"]


def test_next_proposal_returns_supervisor_proposal(deps):
    loop = _loop(deps)
    loop.start("does EGFR drive KRAS activity?")
    proposed = loop.next_proposal("g-test")
    assert proposed is not None
    assert proposed.edge_id == "SIGNOR-100"
    assert proposed.pipeline == "nf-core/rnaseq"
    # nothing ran: the edge is still untested, no evidence recorded
    assert deps["repository"].evidence_for_edge("g-test", "SIGNOR-100") == []


def test_next_proposal_unknown_graph_raises(deps):
    with pytest.raises(KeyError, match="unknown graph"):
        _loop(deps).next_proposal("nope")


def test_approve_runs_interprets_and_records_evidence(deps):
    loop = _loop(deps)
    loop.start("does EGFR drive KRAS activity?")
    proposed = loop.next_proposal("g-test")

    entry = loop.approve("g-test", proposed)

    assert entry.edge_id == "SIGNOR-100"
    assert entry.provenance.run_id == "run-1"
    assert len(deps["repository"].evidence_for_edge("g-test", "SIGNOR-100")) == 1


def test_full_loop_records_evidence_on_edge(deps):
    loop = _loop(deps)
    start = loop.start("does EGFR drive KRAS activity?")
    edge = deps["repository"].get_graph(start.graph_id).get_edge("SIGNOR-100")
    assert edge.state == EdgeState.UNTESTED

    loop.approve(start.graph_id, loop.next_proposal(start.graph_id))

    edge = deps["repository"].get_graph(start.graph_id).get_edge("SIGNOR-100")
    assert edge.state == EdgeState.EXAMINED  # has a ledger record, not a verdict
    assert edge.confidence == 0.0


def test_approve_unknown_graph_raises(deps):
    proposed = ProposedTest(edge_id="SIGNOR-100", gap="x", pipeline="p", data_accession="d")
    with pytest.raises(KeyError, match="unknown graph"):
        _loop(deps).approve("nope", proposed)


def test_approve_rejects_edge_not_in_graph(deps):
    loop = _loop(deps)
    start = loop.start("does EGFR drive KRAS activity?")  # graph has edge SIGNOR-100 only
    bogus = ProposedTest(edge_id="OTHER-999", gap="x", pipeline="p", data_accession="d")
    with pytest.raises(KeyError, match="not in graph"):
        loop.approve(start.graph_id, bogus)
    # guard fired before running/recording anything
    assert deps["repository"].evidence_for_edge("g-test", "OTHER-999") == []


def test_build_from_skeleton_persists_graph(deps):
    from quration.hypothesis.graph import Edge, Node, NodeType
    from quration.hypothesis.orchestrator.seeding import SeedSkeleton

    skeleton = SeedSkeleton(
        nodes=[
            Node(id="A", type=NodeType.TARGET, label="A"),
            Node(id="B", type=NodeType.PHENOTYPE, label="B"),
        ],
        edges=[Edge(id="A-B", source_id="A", target_id="B", relation="drives", pending=True)],
        rationale="r",
    )
    result = _loop(deps).build_from_skeleton("my question", skeleton)
    assert result.kind.value == "investigative"
    assert result.graph_id == "g-test"
    graph = deps["repository"].get_graph("g-test")
    assert graph.query == "my question"
    assert [n.id for n in graph.nodes] == ["A", "B"]
    assert [e.id for e in graph.edges] == ["A-B"]


def test_build_from_skeleton_drops_dangling_edges(deps):
    from quration.hypothesis.graph import Edge, Node, NodeType
    from quration.hypothesis.orchestrator.seeding import SeedSkeleton

    skeleton = SeedSkeleton(
        nodes=[
            Node(id="A", type=NodeType.TARGET, label="A"),
            Node(id="B", type=NodeType.PHENOTYPE, label="B"),
        ],
        edges=[
            Edge(id="A-B", source_id="A", target_id="B", relation="drives", pending=True),
            Edge(id="A-X", source_id="A", target_id="X", relation="drives", pending=True),
        ],
        rationale="r",
    )
    _loop(deps).build_from_skeleton("q", skeleton)
    graph = deps["repository"].get_graph("g-test")
    # the edge to the missing node X is dropped; the valid edge survives
    assert [e.id for e in graph.edges] == ["A-B"]


def test_apply_edge_edit_persists_mutation(deps):
    from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
    from quration.hypothesis.orchestrator.edge_chat import SetRelation

    deps["repository"].save_graph(CausalGraph(
        id="g-test", query="q",
        nodes=[Node(id="A", type=NodeType.TARGET, label="A"),
               Node(id="B", type=NodeType.PHENOTYPE, label="B")],
        edges=[Edge(id="A-B", source_id="A", target_id="B", relation="drives")],
    ))
    updated = _loop(deps).apply_edge_edit("g-test", SetRelation(edge_id="A-B", relation="up-regulates"))
    assert updated.get_edge("A-B").relation == "up-regulates"
    assert deps["repository"].get_graph("g-test").get_edge("A-B").relation == "up-regulates"


def test_apply_edge_edit_unknown_graph_raises(deps):
    import pytest
    from quration.hypothesis.orchestrator.edge_chat import FlipEdge
    with pytest.raises(KeyError, match="unknown graph"):
        _loop(deps).apply_edge_edit("nope", FlipEdge(edge_id="x"))


class _StubSelector:
    def select(self, proposed, graph):
        return MethodChoice(method_id="m:x", name="X", score=0.9,
                            source="structural", rationale="stub")


class _BoomSelector:
    def select(self, proposed, graph):
        raise RuntimeError("selector blew up")


def _loop_with_selector(deps, selector):
    return HypothesisLoop(
        repository=deps["repository"], suggester=deps["suggester"],
        supervisor=deps["supervisor"], runner=deps["runner"],
        selector=selector, id_factory=lambda: "g-test",
    )


def test_null_selector_satisfies_protocol():
    assert isinstance(NullMethodSelector(), MethodSelector)


def test_next_proposal_attaches_method_choice(deps):
    loop = _loop_with_selector(deps, _StubSelector())
    loop.start("does EGFR drive KRAS activity?")
    proposed = loop.next_proposal("g-test")
    assert proposed is not None
    assert proposed.method is not None
    assert proposed.method.method_id == "m:x"


def test_next_proposal_without_selector_has_no_method(deps):
    loop = _loop(deps)  # default NullMethodSelector
    loop.start("does EGFR drive KRAS activity?")
    assert loop.next_proposal("g-test").method is None


def test_selector_failure_is_non_fatal(deps):
    loop = _loop_with_selector(deps, _BoomSelector())
    loop.start("does EGFR drive KRAS activity?")
    proposed = loop.next_proposal("g-test")
    assert proposed is not None
    assert proposed.method is None


def test_orchestrator_exports_selection_symbols():
    from quration.hypothesis.orchestrator import (
        BrokerMethodSelector,
        MethodChoice,
        MethodSelector,
        NullMethodSelector,
    )
    assert all([BrokerMethodSelector, MethodChoice, MethodSelector, NullMethodSelector])
