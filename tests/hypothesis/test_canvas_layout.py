"""Canvas layout (positions) + structural delete ops. Positions are cosmetic and
must never alter epistemic claim state."""

from quration.hypothesis.graph import CausalGraph, Edge, Node, NodePosition, NodeType


def test_node_position_defaults_none_and_back_compat():
    # A node with no position deserializes fine (old graph JSON has no field).
    n = Node.model_validate({"id": "a", "type": "target", "label": "A"})
    assert n.position is None
    # And a node can carry a position round-trip.
    n2 = Node(id="b", type="target", label="B", position=NodePosition(x=10.5, y=-3.0))
    assert CausalGraph.model_validate_json(
        CausalGraph(id="g", query="q", nodes=[n2]).model_dump_json()
    ).get_node("b").position == NodePosition(x=10.5, y=-3.0)


import pytest

from quration.hypothesis.orchestrator.demo import build_demo_loop
from quration.hypothesis.orchestrator.edge_chat import RemoveEdge, RemoveNode
from quration.hypothesis.repository import InMemoryHypothesisRepository
from quration.hypothesis.store import SqliteHypothesisRepository


@pytest.fixture(params=["inmemory", "sqlite"])
def loop(request, tmp_path):
    repo = (InMemoryHypothesisRepository() if request.param == "inmemory"
            else SqliteHypothesisRepository(str(tmp_path / "h.db")))
    yield build_demo_loop(repository=repo)
    if hasattr(repo, "close"):
        repo.close()


def _seed(loop):
    g = CausalGraph(id="g", query="q")
    g.add_node(Node(id="a", type=NodeType.TARGET, label="A"))
    g.add_node(Node(id="b", type=NodeType.PATHWAY, label="B"))
    g.add_node(Node(id="c", type=NodeType.PHENOTYPE, label="C"))
    g.add_edge(Edge(id="e_ab", source_id="a", target_id="b", relation="activates"))
    g.add_edge(Edge(id="e_bc", source_id="b", target_id="c", relation="drives"))
    loop._repo.save_graph(g)


def test_remove_edge_drops_only_that_edge(loop):
    _seed(loop)
    g = loop.apply_edge_edit("g", RemoveEdge(edge_id="e_ab"))
    assert g.get_edge("e_ab") is None
    assert g.get_edge("e_bc") is not None
    assert len(g.nodes) == 3  # nodes untouched


def test_remove_node_cascades_incident_edges(loop):
    _seed(loop)
    g = loop.apply_edge_edit("g", RemoveNode(node_id="b"))
    assert g.get_node("b") is None
    # both edges were incident to b -> gone; no dangling edges remain
    assert g.get_edge("e_ab") is None
    assert g.get_edge("e_bc") is None
    assert {n.id for n in g.nodes} == {"a", "c"}


def test_remove_unknown_raises(loop):
    _seed(loop)
    with pytest.raises(ValueError):
        loop.apply_edge_edit("g", RemoveEdge(edge_id="nope"))
    with pytest.raises(ValueError):
        loop.apply_edge_edit("g", RemoveNode(node_id="nope"))


from quration.hypothesis.epistemics import EdgeValidationStatus, ProposalSource
from quration.hypothesis.orchestrator.edge_chat import ConnectNodes


def test_user_connect_is_user_sourced_and_not_pending(loop):
    _seed(loop)
    g = loop.apply_edge_edit("g", ConnectNodes(
        source_id="a", target_id="c", relation="linked",
        proposal_source=ProposalSource.USER, pending=False))
    new = next(e for e in g.edges if e.source_id == "a" and e.target_id == "c")
    assert new.proposal_source == ProposalSource.USER
    assert new.pending is False
    assert new.validation_status == EdgeValidationStatus.UNVALIDATED


def test_connect_defaults_unchanged_for_existing_callers(loop):
    _seed(loop)
    g = loop.apply_edge_edit("g", ConnectNodes(source_id="a", target_id="c", relation="x"))
    new = next(e for e in g.edges if e.source_id == "a" and e.target_id == "c")
    assert new.proposal_source == ProposalSource.LLM  # default preserved
    assert new.pending is True                         # default preserved
