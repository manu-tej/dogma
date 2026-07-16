"""Deterministic fakes for the orchestrator's seams."""

import pytest

from quration.hypothesis.connectors.base import SuggestionResult
from quration.hypothesis.evidence import EvidenceDirection, EvidenceEntry
from quration.hypothesis.graph import Edge, Node, NodeType
from quration.hypothesis.orchestrator.checkpoint import (
    PipelineResult,
    ProposedTest,
    QueryKind,
)
from quration.hypothesis.provenance import PipelineRunProvenance
from quration.hypothesis.repository import InMemoryHypothesisRepository


class FakeSuggester:
    """Returns a fixed 2-node / 1-edge suggestion regardless of seeds."""

    def expand(self, seeds, query=None):
        nodes = [
            Node(id="P00533", type=NodeType.TARGET, label="EGFR"),
            Node(id="P01116", type=NodeType.TARGET, label="KRAS"),
        ]
        edges = [
            Edge(id="SIGNOR-100", source_id="P00533", target_id="P01116",
                 relation="up-regulates activity", pending=True)
        ]
        return SuggestionResult(nodes=nodes, edges=edges)

    def check_pair(self, source, target):
        return None


class FakeSupervisor:
    """Scriptable supervisor. `kind` drives triage; the rest are canned."""

    def __init__(self, kind=QueryKind.INVESTIGATIVE):
        self.kind = kind

    def triage(self, query):
        return self.kind

    def seeds_for(self, query):
        return ["P00533"]

    def propose_test(self, graph):
        return ProposedTest(
            edge_id="SIGNOR-100", gap="low-n in resistant arm",
            pipeline="nf-core/rnaseq", data_accession="GSE123",
        )

    def interpret(self, proposed, result):
        return EvidenceEntry(
            edge_id=proposed.edge_id,
            direction=EvidenceDirection.SUPPORTS,
            provenance=PipelineRunProvenance(
                run_id=result.run_id, data_accession=result.data_accession
            ),
        )


class FakePipelineRunner:
    def run(self, proposed):
        return PipelineResult(
            run_id="run-1", data_accession=proposed.data_accession, summary="ok"
        )


@pytest.fixture
def deps():
    return {
        "repository": InMemoryHypothesisRepository(),
        "suggester": FakeSuggester(),
        "supervisor": FakeSupervisor(),
        "runner": FakePipelineRunner(),
    }
