"""Significance must reach the model, and its absence must be stated.

`src/quration/interpretation/` had no tests at all.

The request schema has always accepted `adjustedPValue`. The route converted each
gene to a bare `(symbol, log2FoldChange)` tuple, and `interpret_deg_results` was
typed `list[tuple[str, float]]`, so the number was structurally incapable of
reaching the prompt. Two requests differing only in adjusted p-value produced
byte-identical prompts.

That matters because the prompt template also says "Statistical thresholds:
adjusted p-value < $pvalue_threshold" — so the model was told a significance filter
had been applied, and then shown a list of genes with no significance attached. Fold
change alone does not establish differential expression, and a model shown a 2-fold
change with nothing qualifying it will describe it as a finding.
"""

import pytest

from quration.interpretation.prompts import PromptBuilder

UP = [("EGFR", 2.4, 1e-8), ("KRAS", 1.9, 3e-5)]
DOWN = [("TP53", -2.1, 4e-7)]

UP_NO_SIG = [("EGFR", 2.4), ("KRAS", 1.9)]
DOWN_NO_SIG = [("TP53", -2.1)]


def _deg_prompt(up, down) -> str:
    builder = PromptBuilder("deg_analysis")
    builder.set_variables(
        experiment_type="RNA-seq", condition_a="treated", condition_b="control"
    )
    builder.set_deg_results(up, down)
    return "\n".join(builder.build())


class TestSignificanceReachesThePrompt:
    def test_adjusted_p_values_appear(self):
        prompt = _deg_prompt(UP, DOWN)
        assert "1.00e-08" in prompt
        assert "adj. p" in prompt

    def test_differing_significance_produces_a_different_prompt(self):
        """The audit's measurement. These two used to be byte-identical."""
        strong = _deg_prompt([("EGFR", 2.4, 1e-30)], [])
        weak = _deg_prompt([("EGFR", 2.4, 0.87)], [])
        assert strong != weak

    def test_fold_change_is_still_reported(self):
        assert "2.40" in _deg_prompt(UP, DOWN)


class TestAbsentSignificanceIsDeclared:
    def test_each_gene_says_significance_was_not_provided(self):
        prompt = _deg_prompt(UP_NO_SIG, DOWN_NO_SIG)
        assert "not provided" in prompt

    def test_the_prompt_warns_against_calling_them_significant(self):
        prompt = _deg_prompt(UP_NO_SIG, DOWN_NO_SIG)
        assert "No adjusted p-values were supplied" in prompt
        assert "do not describe any gene as significantly changed" in prompt.replace(
            "\n", " "
        )

    def test_no_such_warning_when_significance_was_supplied(self):
        assert "No adjusted p-values were supplied" not in _deg_prompt(UP, DOWN)

    def test_a_partial_list_is_not_treated_as_wholly_unqualified(self):
        """One gene carrying significance means the caller had it; the per-gene
        "not provided" marker still flags the others."""
        prompt = _deg_prompt([("EGFR", 2.4, 1e-8), ("KRAS", 1.9)], [])
        assert "No adjusted p-values were supplied" not in prompt
        assert "not provided" in prompt


class TestPathwaySignificance:
    def _pathway_prompt(self, pathways) -> str:
        builder = PromptBuilder("pathway_enrichment")
        builder.set_variables(experiment_context="RNA-seq, treated vs control")
        builder.set_pathway_results(pathways)
        return "\n".join(builder.build())

    def test_adjusted_p_value_is_preferred_over_nominal(self):
        prompt = self._pathway_prompt(
            [{"name": "MAPK", "p_value": 0.001, "adjusted_p_value": 0.04, "gene_count": 12}]
        )
        assert "adj. p: 4.00e-02" in prompt

    def test_a_nominal_only_p_value_is_labelled_unadjusted(self):
        """Enrichment tests thousands of gene sets; an unqualified nominal p-value is
        the one number that must not stand alone."""
        prompt = self._pathway_prompt(
            [{"name": "MAPK", "p_value": 0.001, "gene_count": 12}]
        )
        assert "UNADJUSTED" in prompt

    def test_missing_significance_is_stated_not_omitted(self):
        prompt = self._pathway_prompt([{"name": "MAPK", "gene_count": 12}])
        assert "not provided" in prompt


class TestBackwardCompatibility:
    def test_two_element_entries_still_work(self):
        """Existing callers pass (gene, log2fc); they must not break."""
        assert "EGFR" in _deg_prompt(UP_NO_SIG, DOWN_NO_SIG)

    def test_mixed_arities_do_not_raise(self):
        _deg_prompt([("EGFR", 2.4, 1e-8), ("KRAS", 1.9)], [("TP53", -2.1)])

    @pytest.mark.parametrize("entries", [[], [("EGFR", 0.0, None)]])
    def test_degenerate_inputs_do_not_raise(self, entries):
        _deg_prompt(entries, [])
