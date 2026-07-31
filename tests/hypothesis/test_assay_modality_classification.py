"""Can this dataset bear on this claim? The classifier behind that answer.

This is the seed of the labelled evaluation set that C1 needs. Every case here has
an answer that is a matter of fact rather than expert judgement — a
phosphoproteomics experiment did not measure transcript abundance, whatever its
title says. Cases requiring real domain judgement (is a 3-donor scRNA-seq study
adequate for a population-level claim?) are deliberately NOT invented here; that
set needs expert labels, and fabricating them would defeat its purpose.

The defect these lock out: `_candidate_modality` scanned one flat dict in insertion
order over `assay + " " + title`, and `"expression"` was inserted before
`"phospho"`. Three of five realistic cases came back `transcript` — including a
phosphoproteomics study, a proteomics study, and a ChIP-seq study, because each had
"expression" in its title, as most real GEO titles do.

The consequence inverted the guarantee this module exists to make.
`ideal_readout.py` states it plainly: "mRNA cannot test a phosphorylation". Yet
`directness_for("phospho", <a real phosphoproteomics dataset>)` returned
`proxy_modality` — the assay was being reported as a stand-in for itself.
"""

import pytest

from quration.hypothesis.orchestrator.dataset_search import DatasetCandidate
from quration.hypothesis.orchestrator.readout_resolver import (
    _candidate_modality,
    directness_for,
)


def candidate(assay: str, title: str) -> DatasetCandidate:
    return DatasetCandidate(accession="GSE1", title=title, assay=assay, source="geo")


#: (assay, title, expected modality). Titles are written the way real ones read —
#: which is to say, most of them mention "expression" regardless of assay.
LABELLED = [
    ("Phosphoproteomics", "Phosphoproteomic profiling of expression changes", "phospho"),
    ("Phosphoproteomics", "Phosphosite quantification after treatment", "phospho"),
    ("RNA-seq", "Expression profiling of tumour vs normal", "transcript"),
    ("scRNA-seq", "Single-cell atlas of 60k cells", "transcript"),
    ("Microarray", "Affymetrix profiling of tumour vs normal", "transcript"),
    ("Proteomics", "Global proteome expression analysis", "protein"),
    ("Mass spec", "Quantitative proteome survey", "protein"),
    ("ChIP-seq", "ChIP-seq of TF binding with expression correlation", "binding"),
    ("Bisulfite-seq", "Genome-wide methylation and expression", "methylation"),
]


@pytest.mark.parametrize("assay,title,expected", LABELLED)
def test_modality_matches_the_assay_not_the_prose(assay, title, expected):
    assert _candidate_modality(candidate(assay, title)) == expected


class TestOrderingRules:
    def test_the_structured_assay_field_beats_the_title(self):
        """The title is prose; the assay field is the answer."""
        c = candidate("Phosphoproteomics", "RNA-seq of treated cells")
        assert _candidate_modality(c) == "phospho"

    def test_a_specific_assay_name_beats_a_generic_aim_word(self):
        """"expression" describes what a study was *for*, not what it measured, and it
        appears in titles across every modality."""
        c = candidate("", "Proteome-wide expression survey")
        assert _candidate_modality(c) == "protein"

    def test_a_generic_word_still_classifies_when_nothing_specific_is_present(self):
        assert _candidate_modality(candidate("", "Expression profiling by array")) == "transcript"

    def test_nothing_recognisable_is_unknown_not_a_guess(self):
        assert _candidate_modality(candidate("", "")) == "unknown"
        assert _candidate_modality(candidate("Widget-seq", "Assorted samples")) == "unknown"


class TestDirectnessFollowsTheClassification:
    def test_a_phospho_dataset_is_direct_for_a_phospho_claim(self):
        """The regression that mattered: this returned `proxy_modality`, i.e. a
        phosphoproteomics assay reported as a stand-in for itself."""
        c = candidate("Phosphoproteomics", "Phosphoproteomic profiling of expression changes")
        assert directness_for("phospho", c) == "direct"

    def test_mrna_remains_a_proxy_for_a_phospho_claim(self):
        """The contract `ideal_readout.py` refuses to soften: mRNA cannot test a
        phosphorylation event. Fixing the classifier must not weaken this."""
        c = candidate("RNA-seq", "Expression profiling after treatment")
        assert directness_for("phospho", c) == "proxy_modality"

    def test_an_unrecognised_assay_is_wrong_assay_not_a_proxy(self):
        c = candidate("", "Assorted samples")
        assert directness_for("phospho", c) == "wrong_assay"

    @pytest.mark.parametrize("assay,title,expected", LABELLED)
    def test_every_labelled_dataset_is_direct_for_its_own_modality(
        self, assay, title, expected
    ):
        """The metric C1 is ultimately after, in its simplest form: a dataset must be
        judged a direct readout for the modality it actually measured."""
        assert directness_for(expected, candidate(assay, title)) == "direct"
