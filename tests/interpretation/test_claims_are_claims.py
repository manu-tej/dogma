"""A claim the benchmark scores must be a claim, not a shard of one.

The first honest `--published` run scored these as extracted claims:

    'NANOG activate their'
    'that activate the'
    'Statistical robustness'

Two defects produced them, confirmed by reproduction against the saved run:

1. `_extract_atomic_claims` applies `re.IGNORECASE` to every pattern group,
   including the ones whose entire selectivity is the uppercase gene class
   `[A-Z][A-Z0-9]{1,10}`. Under IGNORECASE, "that", "their" and "the" qualify
   as gene symbols, so any "X activates Y" word triple in prose becomes a
   regulatory claim. Case-sensitively, the same text yields zero false matches.

2. `_extract_claims` runs `_is_substantive_claim` on the full sentence but
   stores the *simplified* statement. "Statistical robustness — the nominal
   p=0.001 has not been corrected for multiple testing" passes the check as a
   sentence; the em-dash split then stores the two-word label the check would
   have rejected.

Every downstream metric — accuracy, claim precision, claim recall, the overall
benchmark score — is computed over these statements. Fragments in, noise out.
"""

import pytest

from quration.interpretation.parsers import ResponseParser


def statements(text: str) -> list[str]:
    return [c.statement for c in ResponseParser().parse(text).claims]


class TestEnglishWordsAreNotGeneSymbols:
    """Root cause 1: IGNORECASE erased the case constraint on gene patterns."""

    def test_a_relative_clause_is_not_a_regulatory_claim(self):
        # From the saved pub-pathway-001 output: "...the same core factors
        # that activate the proliferation program..."
        text = (
            "The circuit contains core factors that activate the proliferation "
            "program in stem cells."
        )
        assert "that activate the" not in [s.lower() for s in statements(text)]

    def test_a_gene_verb_pronoun_triple_is_not_a_regulatory_claim(self):
        # "NANOG activate their ..." — NANOG is real, "their" is not a gene.
        text = (
            "Master regulators such as OCT4, SOX2 and NANOG activate their own "
            "transcription in a positive feedback loop."
        )
        assert "NANOG activate their" not in statements(text)

    def test_a_real_regulatory_pair_still_matches(self):
        text = "Our analysis indicates that TP53 activates CDKN1A in this system."
        assert any("TP53 activates CDKN1A" in s for s in statements(text))

    def test_lowercase_words_around_is_upregulated_are_not_genes(self):
        text = "It remains unclear which gene is upregulated in this contrast."
        for s in statements(text):
            assert "which is upregulated" not in s.lower()

    def test_pathway_prose_still_matches_case_insensitively(self):
        """The pathway patterns match prose, not symbols — they keep IGNORECASE."""
        text = "The P53 Pathway is enriched in the treated samples."
        assert any("pathway" in s.lower() for s in statements(text))


class TestTheStoredStatementIsTheOneChecked:
    """Root cause 2: substantive-claim check ran on a statement never stored."""

    def test_an_em_dash_label_is_not_stored_as_a_claim(self):
        # Verbatim shape from the saved pub-pathway-001 output.
        text = (
            "- Statistical robustness — the nominal p=0.001 has not been "
            "corrected for multiple testing, and no other pathways were shown "
            "for comparison."
        )
        assert "Statistical robustness" not in statements(text)

    def test_a_simplified_claim_that_stays_substantive_is_kept(self):
        text = (
            "ERBB2 shows elevated expression across all tumor samples — "
            "consistent with the amplification reported in the original study."
        )
        kept = statements(text)
        assert any("ERBB2" in s and "elevated" in s for s in kept)

    @pytest.mark.parametrize(
        "fragment",
        ["NANOG activate their", "that activate the", "Statistical robustness"],
    )
    def test_no_known_fragment_survives_the_real_benchmark_text(self, fragment):
        """The three fragments the first honest run actually scored."""
        text = (
            "## Interpretation\n\n"
            "Master regulators such as OCT4, SOX2 and NANOG activate their own "
            "transcription. The same core factors that activate the "
            "proliferation program also repress differentiation.\n\n"
            "- Statistical robustness — the nominal p=0.001 has not been "
            "corrected for multiple testing.\n"
        )
        assert fragment not in statements(text)
