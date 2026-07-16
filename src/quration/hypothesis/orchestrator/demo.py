"""Deterministic, offline demo implementations of the loop's seams.

They let the API run the full hypothesis loop end-to-end without a live LLM or
Nextflow. Sub-projects 4b/4c replace these with the real Supervisor / PipelineRunner.
"""

from quration.hypothesis.connectors.base import SuggestionResult
from quration.hypothesis.evidence import EvidenceDirection, EvidenceEntry
from quration.hypothesis.graph import Edge, Node, NodeType
from quration.hypothesis.orchestrator.checkpoint import (
    PipelineResult,
    ProposedTest,
    QueryKind,
)
from quration.hypothesis.orchestrator.loop import HypothesisLoop
from quration.hypothesis.provenance import (
    KGEdgeProvenance,
    OntologyTermProvenance,
    PipelineRunProvenance,
)
from quration.hypothesis.repository import (
    HypothesisRepository,
    InMemoryHypothesisRepository,
)

_DEMO_NODES = [
    ("P00533", "EGFR", NodeType.TARGET),
    ("P01116", "KRAS", NodeType.TARGET),
    ("RESIST", "drug resistance", NodeType.PHENOTYPE),
]
_DEMO_EDGES = [
    ("e-egfr-kras", "P00533", "P01116", "up-regulates activity"),
    ("e-kras-resist", "P01116", "RESIST", "drives"),
]


class DemoSuggester:
    """Returns a fixed 3-node / 2-edge causal sketch regardless of seeds."""

    def expand(self, seeds: list[str], query: str | None = None) -> SuggestionResult:
        nodes = [
            Node(
                id=node_id,
                type=node_type,
                label=label,
                grounding=OntologyTermProvenance(ontology="UniProt", term_id=node_id),
            )
            for node_id, label, node_type in _DEMO_NODES
        ]
        edges = [
            Edge(
                id=edge_id,
                source_id=source,
                target_id=target,
                relation=relation,
                pending=True,
                suggested_by=[KGEdgeProvenance(source="demo", reference=edge_id)],
            )
            for edge_id, source, target, relation in _DEMO_EDGES
        ]
        return SuggestionResult(nodes=nodes, edges=edges)

    def check_pair(self, source: str, target: str):
        return None


class DemoSupervisor:
    """Always investigative; proposes the first untested edge; interprets as support."""

    def triage(self, query: str) -> QueryKind:
        return QueryKind.INVESTIGATIVE

    def seeds_for(self, query: str) -> list[str]:
        return ["P00533"]

    def propose_test(self, graph) -> ProposedTest | None:
        for edge in graph.untested_edges():
            pt = edge.proposed_test
            return ProposedTest(
                edge_id=edge.id,
                gap=f"no experimental evidence yet for: {edge.relation}",
                pipeline=(pt.pipeline if pt and pt.pipeline else "nf-core/rnaseq"),
                data_accession=(pt.data_accession if pt and pt.data_accession else "GSE-DEMO"),
                est_time="~30 min",
            )
        return None

    def interpret(self, proposed: ProposedTest, result: PipelineResult) -> EvidenceEntry:
        return EvidenceEntry(
            edge_id=proposed.edge_id,
            direction=EvidenceDirection.SUPPORTS,
            magnitude="log2FC=1.8, padj=1e-4",
            rationale="demo: pipeline reported a significant effect",
            provenance=PipelineRunProvenance(
                run_id=result.run_id, data_accession=result.data_accession
            ),
        )


class DemoPipelineRunner:
    """Returns a canned successful run."""

    def run(self, proposed: ProposedTest) -> PipelineResult:
        return PipelineResult(
            run_id=f"demo-run-{proposed.edge_id}",
            data_accession=proposed.data_accession,
            summary="demo pipeline completed",
        )


def build_demo_loop(repository: HypothesisRepository | None = None) -> HypothesisLoop:
    """A HypothesisLoop wired entirely with deterministic demo seams."""
    return HypothesisLoop(
        repository=repository or InMemoryHypothesisRepository(),
        suggester=DemoSuggester(),
        supervisor=DemoSupervisor(),
        runner=DemoPipelineRunner(),
    )
