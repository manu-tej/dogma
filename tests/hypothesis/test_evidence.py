"""Tests for evidence entries and the deterministic edge rollup."""

import pytest
from pydantic import ValidationError

from quration.hypothesis.evidence import (
    EvidenceDirection,
    EvidenceEntry,
    dataset_validation_for,
    rollup_edge,
)
from quration.hypothesis.graph import EdgeState
from quration.hypothesis.provenance import PipelineRunProvenance


def _entry(direction: EvidenceDirection, weight: float = 1.0) -> EvidenceEntry:
    return EvidenceEntry(
        edge_id="e1",
        direction=direction,
        weight=weight,
        provenance=PipelineRunProvenance(run_id="r", data_accession="GSE1"),
    )


def test_no_evidence_is_untested():
    assert rollup_edge([]) == (EdgeState.UNTESTED, 0.0)


def test_rollup_never_returns_a_verdict():
    # Even a pile of "supports" entries must NOT produce SUPPORTED — verdicts are
    # abolished (north-star §2.2). Weights are irrelevant to the state now.
    entries = [_entry(EvidenceDirection.SUPPORTS, 1.0)] * 3 + [_entry(EvidenceDirection.REFUTES, 1.0)]
    assert rollup_edge(entries) == (EdgeState.EXAMINED, 0.0)


def test_any_evidence_is_examined():
    # supports / refutes / inconclusive all count as "the edge has a ledger record".
    for direction in EvidenceDirection:
        assert rollup_edge([_entry(direction)]) == (EdgeState.EXAMINED, 0.0)


def test_only_an_empty_ledger_is_untested():
    assert rollup_edge([]) == (EdgeState.UNTESTED, 0.0)


def test_weight_must_be_in_unit_interval():
    with pytest.raises(ValidationError):
        _entry(EvidenceDirection.SUPPORTS, weight=0.0)
    with pytest.raises(ValidationError):
        _entry(EvidenceDirection.SUPPORTS, weight=1.5)


def test_dataset_channel_makes_no_verdict():
    # The dataset channel must no longer assert support/contradiction — the ledger
    # is the record (north-star §2.2). dataset_validation_for returns None always.
    entries = [_entry(EvidenceDirection.SUPPORTS)]
    assert dataset_validation_for(entries, created_at="2026-06-18T00:00:00Z") is None
