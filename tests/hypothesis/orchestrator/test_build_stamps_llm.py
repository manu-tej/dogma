"""build_from_skeleton marks seed edges as LLM-proposed, unvalidated drafts."""

from quration.hypothesis.epistemics import EdgeValidationStatus as S, ProposalSource
from quration.hypothesis.graph import Edge, Node, NodeType
from quration.hypothesis.orchestrator.demo import build_demo_loop
from quration.hypothesis.orchestrator.seeding import SeedSkeleton


def test_built_seed_edges_are_llm_unvalidated_drafts():
    loop = build_demo_loop()
    skeleton = SeedSkeleton(
        nodes=[Node(id="a", type=NodeType.TARGET, label="A"),
               Node(id="b", type=NodeType.TARGET, label="B")],
        # Even if an edge arrives mis-stamped, the seed is the LLM's proposal:
        edges=[Edge(id="e1", source_id="a", target_id="b", relation="activates",
                    proposal_source=ProposalSource.KG,
                    validation_status=S.KG_SUPPORTED_DIRECT)],
        rationale="r")
    result = loop.build_from_skeleton("q", skeleton)
    edge = loop.get_graph(result.graph_id).get_edge("e1")
    assert edge.proposal_source == ProposalSource.LLM
    assert edge.validation_status == S.UNVALIDATED
    assert edge.validations == []
