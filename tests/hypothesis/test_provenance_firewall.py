"""`PipelineRunProvenance` must mean a pipeline actually ran.

That type documents itself as "a reproducible pipeline run on named data", and
`EvidenceEntry` was typed to accept only it — described in the source as
"provenance-or-silence at the type level".

The guarantee was hollow. `MethodsGraphEvaluationRunner` consults a method registry
and runs nothing, yet its evidence carried
`PipelineRunProvenance(run_id="methods-graph-eval-<edge_id>",
data_accession="methods-graph")` — a fabricated run against a fabricated accession.
Every consumer downstream had no way to tell that apart from a real one, which makes
the type worth nothing: it meant only "somebody constructed this object".

The structural LLM-assertion/evidence firewall is the part of this system that is
genuinely hard to copy. It is only worth anything if it is enforced, so these tests
assert the enforcement, not merely that today's callers happen to comply.
"""

import pytest
from pydantic import ValidationError

from quration.hypothesis.evidence import (
    EvidenceDirection,
    EvidenceEntry,
    EvidenceKind,
)
from quration.hypothesis.provenance import (
    GroundingProvenance,
    PipelineRunProvenance,
)

RUN = PipelineRunProvenance(run_id="run-1", data_accession="GSE123")
GROUNDING = GroundingProvenance(verdict="COVERAGE_GAP", method_id=None)


def _entry(**kw) -> EvidenceEntry:
    base = dict(
        edge_id="e1",
        direction=EvidenceDirection.INCONCLUSIVE,
        provenance=GROUNDING,
    )
    base.update(kw)
    return EvidenceEntry(**base)


class TestTheFirewallIsEnforced:
    def test_a_measurement_cannot_claim_grounding_provenance(self):
        with pytest.raises(ValidationError, match="requires PipelineRunProvenance"):
            _entry(kind=EvidenceKind.MEASUREMENT, provenance=GROUNDING)

    def test_an_assessment_cannot_claim_a_pipeline_run(self):
        """The exact defect: a registry lookup stamping itself as a pipeline run."""
        with pytest.raises(ValidationError, match="must not carry PipelineRunProvenance"):
            _entry(kind=EvidenceKind.FEASIBILITY, provenance=RUN)

    def test_the_valid_pairings_are_accepted(self):
        assert _entry(kind=EvidenceKind.MEASUREMENT, provenance=RUN)
        assert _entry(kind=EvidenceKind.FEASIBILITY, provenance=GROUNDING)


class TestGroundingProvenanceCannotFabricate:
    def test_it_has_no_run_id_or_accession_to_fill_in(self):
        """The fields do not exist, so there is nothing to invent. That is the point:
        the previous placeholders were possible only because the type demanded them."""
        assert not hasattr(GROUNDING, "run_id")
        assert not hasattr(GROUNDING, "data_accession")

    def test_it_records_what_was_actually_established(self):
        assert GROUNDING.verdict == "COVERAGE_GAP"
        assert GROUNDING.source == "methods-graph"

    def test_it_is_discriminated_for_persistence(self):
        assert GROUNDING.kind == "grounding"
        assert RUN.kind == "pipeline_run"


class TestPersistedRowsStillLoad:
    def test_a_legacy_pipeline_run_row_round_trips(self):
        """Rows written before `grounding` existed must still deserialize. They were
        all measurements-by-declaration, so they load as MEASUREMENT entries."""
        raw = {
            "edge_id": "e1",
            "kind": "measurement",
            "direction": "supports",
            "provenance": {
                "kind": "pipeline_run",
                "run_id": "run-1",
                "data_accession": "GSE123",
            },
        }
        entry = EvidenceEntry.model_validate(raw)
        assert isinstance(entry.provenance, PipelineRunProvenance)

    def test_a_grounding_row_round_trips(self):
        entry = _entry(kind=EvidenceKind.FEASIBILITY, provenance=GROUNDING)
        restored = EvidenceEntry.model_validate(entry.model_dump())
        assert isinstance(restored.provenance, GroundingProvenance)
        assert restored.provenance.verdict == "COVERAGE_GAP"


def test_the_live_runner_produces_a_conformant_entry():
    """End to end through the real supervisor, so the firewall is exercised by the
    production path rather than only by hand-built objects."""
    from quration.hypothesis.orchestrator.checkpoint import PipelineResult, ProposedTest
    from quration.hypothesis.orchestrator.methods_eval import MethodsGraphSupervisor

    proposed = ProposedTest(
        edge_id="e1",
        gap="g",
        pipeline="nf-core/rnaseq",
        data_accession="GSE1",
        relation="up-regulates",
    )
    result = PipelineResult(
        run_id="methods-graph-eval-e1",
        data_accession="methods-graph",
        summary="No method matches the readout.",
        raw={"verdict": "COVERAGE_GAP", "method_id": None},
    )

    entry = MethodsGraphSupervisor().interpret(proposed, result)

    # Even handed a PipelineResult carrying the old placeholder strings, the
    # supervisor must not launder them into PipelineRunProvenance.
    assert isinstance(entry.provenance, GroundingProvenance)
    assert entry.kind is EvidenceKind.FEASIBILITY
