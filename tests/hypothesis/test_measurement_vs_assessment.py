"""An edge must not report itself examined when nothing measured it.

The reproduction, against the loop as it was:

    iter 0: edge=e-egfr-kras   magnitude='COVERAGE_GAP' weight=0.01
    iter 1: edge=e-kras-resist magnitude='COVERAGE_GAP' weight=0.01
    iter 2: next_proposal -> None          (loop reports DONE)
    FINAL:  both edges state=examined

`COVERAGE_GAP` means "no method exists for this readout" — a record of failing to
measure. `rollup_edge` returned EXAMINED for any ledger entry at all, so the graph
claimed work that had not happened.

See docs/decisions/2026-07-30-what-a-measurement-may-change-on-an-edge.md
"""

from quration.hypothesis.evidence import (
    EvidenceDirection,
    EvidenceEntry,
    EvidenceKind,
    rollup_edge,
)
from quration.hypothesis.graph import CausalGraph, Edge, EdgeState, Node, NodeType
from quration.hypothesis.provenance import (
    GroundingProvenance,
    PipelineRunProvenance,
)


def entry(kind: EvidenceKind, magnitude: str = "COVERAGE_GAP") -> EvidenceEntry:
    """Provenance is chosen to match the kind, because EvidenceEntry now enforces it:
    a MEASUREMENT must be backed by a real run, and an assessment must not claim one.
    Writing these tests the other way is what the validator is there to catch — it
    caught this helper."""
    provenance = (
        PipelineRunProvenance(run_id="r1", data_accession="GSE1")
        if kind is EvidenceKind.MEASUREMENT
        else GroundingProvenance(verdict=magnitude, method_id=None)
    )
    return EvidenceEntry(
        edge_id="e1",
        kind=kind,
        direction=EvidenceDirection.INCONCLUSIVE,
        weight=0.01,
        magnitude=magnitude,
        provenance=provenance,
    )


class TestRollup:
    def test_no_entries_is_untested(self):
        assert rollup_edge([])[0] == EdgeState.UNTESTED

    def test_a_coverage_gap_alone_does_not_count_as_examined(self):
        """The defect. An assessment saying "we cannot measure this" is not a
        measurement, and must not read as one."""
        state, _ = rollup_edge([entry(EvidenceKind.FEASIBILITY)])
        assert state == EdgeState.ASSESSED
        assert state != EdgeState.EXAMINED

    def test_a_measurement_is_examined(self):
        state, _ = rollup_edge([entry(EvidenceKind.MEASUREMENT, magnitude="log2FC 1.4")])
        assert state == EdgeState.EXAMINED

    def test_one_measurement_among_assessments_is_enough(self):
        state, _ = rollup_edge([
            entry(EvidenceKind.FEASIBILITY),
            entry(EvidenceKind.MEASUREMENT, magnitude="log2FC 1.4"),
            entry(EvidenceKind.FEASIBILITY),
        ])
        assert state == EdgeState.EXAMINED

    def test_confidence_stays_zero(self):
        """North-star §2.2 is unchanged: this reports process state, not a verdict.
        No measurement may produce a confidence number."""
        for kind in (EvidenceKind.MEASUREMENT, EvidenceKind.FEASIBILITY):
            assert rollup_edge([entry(kind)])[1] == 0.0

    def test_an_entry_claims_measurement_only_if_it_says_so(self):
        """The default is the conservative one — every entry any production path has
        written is an assessment, and claiming otherwise must be deliberate."""
        bare = EvidenceEntry(
            edge_id="e1",
            direction=EvidenceDirection.INCONCLUSIVE,
            provenance=GroundingProvenance(verdict="COVERAGE_GAP"),
        )
        assert bare.kind == EvidenceKind.FEASIBILITY
        assert rollup_edge([bare])[0] == EdgeState.ASSESSED


class TestGraphSelection:
    def _graph(self) -> CausalGraph:
        g = CausalGraph(id="g", query="q")
        for nid in ("a", "b", "c"):
            g.add_node(Node(id=nid, type=NodeType.TARGET, label=nid.upper()))
        g.add_edge(Edge(id="untested", source_id="a", target_id="b", relation="drives"))
        g.add_edge(
            Edge(
                id="assessed",
                source_id="b",
                target_id="c",
                relation="drives",
                state=EdgeState.ASSESSED,
            )
        )
        g.add_edge(
            Edge(
                id="measured",
                source_id="a",
                target_id="c",
                relation="drives",
                state=EdgeState.EXAMINED,
            )
        )
        return g

    def test_untested_excludes_assessed_so_gaps_are_not_retried_forever(self):
        assert [e.id for e in self._graph().untested_edges()] == ["untested"]

    def test_unmeasured_counts_assessed_as_still_outstanding(self):
        """The honest denominator for "how much of this graph is tested"."""
        assert sorted(e.id for e in self._graph().unmeasured_edges()) == [
            "assessed",
            "untested",
        ]

    def test_a_measured_edge_is_in_neither_outstanding_set(self):
        g = self._graph()
        assert "measured" not in {e.id for e in g.untested_edges()}
        assert "measured" not in {e.id for e in g.unmeasured_edges()}


def test_assessed_is_a_distinct_state():
    assert EdgeState.ASSESSED.value == "assessed"
    assert EdgeState.ASSESSED not in (EdgeState.UNTESTED, EdgeState.EXAMINED)
