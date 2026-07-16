from quration.hypothesis.orchestrator.relation_method_map import (
    expected_direction_for, keywords_for_relation, relation_polarity,
)


def test_phospho_relation_maps_to_phospho_readout_keywords():
    kws = keywords_for_relation("phosphorylates and activates")
    assert any("phospho" in k for k in kws)


def test_expression_relation_maps_to_differential_expression():
    kws = keywords_for_relation("up-regulates")
    assert any("expression" in k or "differential" in k for k in kws)


def test_binds_and_activates_maps_to_interaction_not_expression():
    # "binds" must win over the generic "activat" trigger (ordering): a binding
    # relation's readout is an interaction assay, not differential expression.
    kws = keywords_for_relation("binds and activates")
    assert any("interaction" in k for k in kws)
    assert not any("expression" in k for k in kws)


def test_phospho_wins_over_activation_in_compound_phrase():
    kws = keywords_for_relation("phosphorylates and activates")
    assert any("phospho" in k for k in kws)
    assert not any("expression" in k for k in kws)


def test_unknown_relation_returns_empty():
    assert keywords_for_relation("manifests as") == []
    assert keywords_for_relation(None) == []


def test_methylation_maps_to_bisulfite_not_chipseq():
    assert "bisulfite-seq" in keywords_for_relation("methylates")
    assert "chip-seq" not in keywords_for_relation("methylates")


def test_relation_polarity_signs():
    assert relation_polarity("activates") == 1
    assert relation_polarity("inhibits") == -1
    assert relation_polarity("binds") == 0


def test_expected_direction_from_polarity():
    assert expected_direction_for("activates") == "increase"
    assert expected_direction_for("represses") == "decrease"
    assert expected_direction_for("binds") == "unknown"
