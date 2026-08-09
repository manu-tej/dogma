"""An unfilled optional variable must not reach the model as `$name`.

`safe_substitute` leaves unknown variables verbatim, and `dataset_id` is listed
as optional — so a caller that had no accession sent the model the literal line
`Dataset: $dataset_id`. In the first honest `--published` run the model noticed
("`$dataset_id` was not resolved... no GEO accession was actually provided");
a less careful model invents one, and an invented accession is exactly the
class of output this repo exists to prevent.

"not provided" is the same convention the DEG formatter already uses for a
missing adjusted p-value: absence stated, never left as template syntax and
never silently filled in.
"""

from quration.interpretation.prompts import get_template


def _render_deg_user(**extra) -> str:
    return get_template("deg_analysis").render_user(
        experiment_type="RNA-seq",
        condition_a="treated",
        condition_b="control",
        upregulated_genes="EGFR (log2FC: 2.40)",
        downregulated_genes="TP53 (log2FC: -2.10)",
        **extra,
    )


class TestUnfilledOptionalVariables:
    def test_no_template_syntax_survives_rendering(self):
        rendered = _render_deg_user()
        assert "$dataset_id" not in rendered
        assert "$" not in rendered, f"unfilled variable leaked: {rendered}"

    def test_absence_is_stated_not_hidden(self):
        assert "Dataset: not provided" in _render_deg_user()

    def test_a_supplied_value_still_substitutes(self):
        rendered = _render_deg_user(dataset_id="GSE12345")
        assert "Dataset: GSE12345" in rendered
        assert "not provided" not in rendered.split("Organism")[0]

    def test_a_bare_content_block_renders_empty_not_labelled(self):
        """`$additional_context` stands alone, not behind a label. Absence
        there must vanish — a dangling "not provided" at the end of the
        prompt is itself noise. (The first fix got this wrong.)"""
        rendered = _render_deg_user()
        assert not rendered.rstrip().endswith("not provided")

    def test_every_template_renders_clean_with_no_optionals(self):
        """The defect class, not the instance: no template may leak `$name`
        for any of its declared optional variables."""
        from quration.interpretation.prompts import list_templates

        for name in list_templates():
            template = get_template(name)
            filler = {v: "x" for v in template.required_variables}
            system, user = template.render(**filler)
            for variable in template.optional_variables:
                assert f"${variable}" not in system, (name, variable)
                assert f"${variable}" not in user, (name, variable)
