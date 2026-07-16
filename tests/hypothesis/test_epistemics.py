"""Epistemic/validation primitives: status summary + display derivation."""

from quration.hypothesis.epistemics import (
    EdgeValidation,
    EdgeValidationStatus as S,
    ProposalSource,
    display_status,
    record_validation,
    reset_edge_validation,
    summarize_status,
)
from quration.hypothesis.provenance import KGEdgeProvenance, PipelineRunProvenance


def _v(status, source, **kw):
    return EdgeValidation(status=status, source=source, created_at="t", **kw)


def test_summarize_empty_is_unvalidated():
    assert summarize_status([]) == S.UNVALIDATED


def test_summarize_picks_highest_priority_across_sources():
    # dataset_supported outranks kg_supported_direct
    vs = [_v(S.KG_SUPPORTED_DIRECT, ProposalSource.KG),
          _v(S.DATASET_SUPPORTED, ProposalSource.DATASET)]
    assert summarize_status(vs) == S.DATASET_SUPPORTED


def test_summarize_contradicted_is_sticky_over_kg():
    vs = [_v(S.KG_SUPPORTED_DIRECT, ProposalSource.KG),
          _v(S.CONTRADICTED, ProposalSource.DATASET)]
    assert summarize_status(vs) == S.CONTRADICTED


def test_summarize_uses_latest_per_source_channel():
    # a re-run of the KG check (same source) overwrites the prior KG result
    vs = [_v(S.KG_SUPPORTED_DIRECT, ProposalSource.KG),
          _v(S.UNSUPPORTED, ProposalSource.KG)]  # later KG check finds nothing
    assert summarize_status(vs) == S.UNSUPPORTED


def test_summarize_resets_at_supersedes_barrier():
    vs = [_v(S.KG_SUPPORTED_DIRECT, ProposalSource.KG),
          EdgeValidation(status=S.UNVALIDATED, source=ProposalSource.SYSTEM,
                         created_at="t2", supersedes_prior=True)]
    assert summarize_status(vs) == S.UNVALIDATED  # prior support no longer counts


def test_summarize_counts_validations_recorded_after_barrier():
    vs = [_v(S.KG_SUPPORTED_DIRECT, ProposalSource.KG),
          EdgeValidation(status=S.UNVALIDATED, source=ProposalSource.SYSTEM,
                         created_at="t2", supersedes_prior=True),
          _v(S.KG_SUPPORTED_DIRECT, ProposalSource.KG)]  # re-validated after the edit
    assert summarize_status(vs) == S.KG_SUPPORTED_DIRECT


def test_reset_edge_validation_supersedes_but_preserves_history():
    class _Edge:
        pass
    e = _Edge(); e.validations = []; e.validation_status = S.UNVALIDATED
    record_validation(e, _v(S.KG_SUPPORTED_DIRECT, ProposalSource.KG))
    assert e.validation_status == S.KG_SUPPORTED_DIRECT
    reset_edge_validation(e, "relation changed", "t2")
    assert e.validation_status == S.UNVALIDATED          # current claim unvalidated
    assert len(e.validations) == 2                        # prior record preserved
    assert e.validations[-1].supersedes_prior is True
    assert e.validations[-1].rationale == "relation changed"


def test_display_status_upgrades_only_when_both_endpoints_grounded():
    assert display_status(S.UNVALIDATED, src_grounded=True, tgt_grounded=True) == \
        S.ENTITY_GROUNDED_RELATION_UNCHECKED
    assert display_status(S.UNVALIDATED, src_grounded=True, tgt_grounded=False) == S.UNVALIDATED
    assert display_status(S.UNVALIDATED, src_grounded=False, tgt_grounded=False) == S.UNVALIDATED


def test_display_status_does_not_override_a_real_validation():
    # a validated edge keeps its status even if both endpoints are grounded
    assert display_status(S.KG_SUPPORTED_DIRECT, src_grounded=True, tgt_grounded=True) == \
        S.KG_SUPPORTED_DIRECT
    assert display_status(S.CONTRADICTED, src_grounded=True, tgt_grounded=True) == S.CONTRADICTED


def test_record_validation_rejects_display_only_status():
    import pytest

    class _Edge:
        validations = []
        validation_status = S.UNVALIDATED
    e = _Edge(); e.validations = []
    with pytest.raises(ValueError):
        record_validation(e, _v(S.ENTITY_GROUNDED_RELATION_UNCHECKED, ProposalSource.SYSTEM))


def test_record_validation_appends_and_recomputes():
    class _Edge:  # duck-typed Edge
        validations = []
        validation_status = S.UNVALIDATED
    e = _Edge()
    e.validations = []
    record_validation(e, _v(S.KG_SUPPORTED_DIRECT, ProposalSource.KG,
                            evidence=KGEdgeProvenance(source="optimuskg", reference="x")))
    assert e.validation_status == S.KG_SUPPORTED_DIRECT
    assert len(e.validations) == 1
    record_validation(e, _v(S.DATASET_SUPPORTED, ProposalSource.DATASET,
                            evidence=PipelineRunProvenance(run_id="r", data_accession="GSE1")))
    assert e.validation_status == S.DATASET_SUPPORTED
    assert len(e.validations) == 2
