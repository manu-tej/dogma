"""Tests for the paired pre/post-treatment biopsy discovery pipeline.

Deterministic, offline. Discovery is injected via a fake ``search_fn`` returning
canonical ``GeoDatasetCandidate`` objects, so the orchestrator is tested without network.
"""

from quration.data_sources.clinical_trials import ClinicalTrial, ClinicalTrialsFetcher
from quration.data_sources.disease_profiles import DMD_PROFILE, get_profile
from quration.data_sources.dmd_treatments import (
    DMD_TREATMENTS,
    all_treatment_names,
    treatments_by_class,
)
from quration.data_sources.paired_biopsy_search import (
    PairedBiopsyCandidate,
    PairedBiopsySearch,
    to_markdown,
)
from quration.data_sources.paired_treatment_detector import detect_paired_pre_post
from quration.models.geo_search import ExperimentalDesign, GeoDatasetCandidate, GsmSample


# --------------------------------------------------------------------------- #
# Vocabulary / detector / profiles / CT.gov parsing (unit-level, unchanged API)
# --------------------------------------------------------------------------- #
class TestTreatmentVocabulary:
    def test_known_drugs_present(self):
        names = all_treatment_names()
        for drug in ["eteplirsen", "vamorolone", "ataluren", "givinostat"]:
            assert drug in names

    def test_brand_and_alias_searchable(self):
        names = all_treatment_names()
        assert "exondys 51" in names
        assert "avi-4658" in names

    def test_exon_skippers_have_target_exon(self):
        for t in treatments_by_class("exon_skipping"):
            assert t.target_exon in (45, 51, 53)

    def test_no_duplicate_names(self):
        names = all_treatment_names()
        assert len(names) == len(set(names))

    def test_all_have_class_and_mechanism(self):
        for t in DMD_TREATMENTS:
            assert t.generic_name and t.drug_class and t.mechanism


class TestPairingDetector:
    def test_positive(self):
        ev = detect_paired_pre_post(
            title="Eteplirsen in DMD muscle",
            summary="Muscle biopsies at baseline and week 48.",
            overall_design="Pre-treatment and post-treatment biopsies from same patients.",
            sample_titles=["Patient 1 pre-treatment", "Patient 1 week 48"],
        )
        assert ev.is_candidate and ev.has_treatment_signal and ev.confidence == "high"

    def test_biopsy_without_pairing(self):
        ev = detect_paired_pre_post(
            title="DMD muscle biopsy", summary="Single biopsy per patient vs controls."
        )
        assert ev.has_biopsy_signal and not ev.is_candidate

    def test_pairing_without_biopsy(self):
        ev = detect_paired_pre_post(
            title="Blood pre and post treatment",
            summary="Whole blood pre-treatment and post-treatment.",
        )
        assert ev.has_pairing_signal and not ev.has_biopsy_signal and not ev.is_candidate

    def test_week_regex_signal(self):
        ev = detect_paired_pre_post(summary="Muscle biopsy at week 24 and week 48.")
        assert ev.has_biopsy_signal and ev.has_pairing_signal

    def test_custom_treatment_vocab(self):
        # A non-DMD treatment is only detected when supplied.
        text = "Muscle biopsy pre and post alglucosidase treatment"
        assert not detect_paired_pre_post(summary=text, treatment_names=[]).has_treatment_signal
        assert detect_paired_pre_post(
            summary=text, treatment_names=["alglucosidase"]
        ).has_treatment_signal


class TestDiseaseProfiles:
    def test_dmd_profile_duchenne_specific(self):
        assert "Duchenne" in DMD_PROFILE.geo_terms
        assert all("muscular dystrophy" != t.lower() for t in DMD_PROFILE.geo_terms)
        assert DMD_PROFILE.has_treatments

    def test_known_resolves(self):
        assert get_profile("DMD") is DMD_PROFILE

    def test_unknown_generic(self):
        p = get_profile("Pompe disease")
        assert p.ct_condition == "Pompe disease" and not p.has_treatments


_STUDY_PAYLOAD = {
    "protocolSection": {
        "identificationModule": {"nctId": "NCT02255552", "briefTitle": "Eteplirsen in DMD"},
        "statusModule": {"overallStatus": "COMPLETED"},
        "designModule": {"phases": ["PHASE3"]},
        "armsInterventionsModule": {"interventions": [{"name": "eteplirsen", "type": "DRUG"}]},
        "conditionsModule": {"conditions": ["Duchenne Muscular Dystrophy"]},
        "descriptionModule": {
            "briefSummary": "Muscle biopsy to measure dystrophin.",
            "detailedDescription": "Biopsies at baseline and week 48.",
        },
        "referencesModule": {
            "references": [{"pmid": "31237898", "type": "RESULT"}, {"type": "BACKGROUND"}]
        },
    }
}


class TestClinicalTrialsParsing:
    def test_parse_extracts_fields(self):
        t = ClinicalTrialsFetcher()._parse_study(_STUDY_PAYLOAD)
        assert t and t.nct_id == "NCT02255552" and t.pmids == ["31237898"]
        assert t.mentions_biopsy and "eteplirsen" in t.interventions

    def test_parse_without_nct_none(self):
        assert ClinicalTrialsFetcher()._parse_study({"protocolSection": {}}) is None


# --------------------------------------------------------------------------- #
# Orchestrator (with injected search_fn) ------------------------------------ #
# --------------------------------------------------------------------------- #
def _gc(gse, title, summary, design="", organism="Homo sapiens", n=10, pmid=None, samples=None):
    return GeoDatasetCandidate(
        gse_id=gse,
        title=title,
        summary=summary,
        experimental_design=ExperimentalDesign(
            conditions=None, design_type=None, tech=None, notes=design, is_partial=True
        ),
        n_samples=n,
        organism=organism,
        platforms=[],
        primary_pmid=pmid,
        maybe_has_survival_data=False,
        match_reasons=[],
        raw_metadata={},
        samples=samples or [],
    )


def _fake_search(candidates):
    def fn(spec, max_results=50, fetch_samples=False, parse_design=True):
        return candidates
    return fn


class _StubGEO:
    def fetch_gse_samples(self, gse, limit=40):
        return []


class _StubCT:
    def __init__(self, trials):
        self._trials = trials

    def search_biopsy_trials(self, condition="", treatments=None, max_results=100, require_biopsy=True):
        return self._trials


def _make(candidates, trials=None):
    return PairedBiopsySearch(
        search_fn=_fake_search(candidates),
        geo_fetcher=_StubGEO(),
        ct_fetcher=_StubCT(trials or []),
        llm_client=None,
    )


class TestOrchestratorPrecision:
    def test_human_paired_treatment_passes(self):
        gc = _gc(
            "GSE111",
            "Eteplirsen DMD muscle",
            "Muscle biopsies at baseline and week 48 post-treatment.",
            design="Pre-treatment and post-treatment biopsies, same subjects.",
        )
        res = _make([gc]).run(use_llm=False)
        assert len(res) == 1 and res[0].gse_id == "GSE111" and res[0].source == "geo_direct"

    def test_mouse_rejected(self):
        gc = _gc("GSE222", "mdx mouse eteplirsen", "Muscle biopsies pre/post.", organism="Mus musculus")
        assert _make([gc]).run(use_llm=False) == []

    def test_no_treatment_no_trial_rejected(self):
        gc = _gc("GSE333", "DMD natural history", "Muscle biopsies pre and post, no drug.",
                 design="Longitudinal biopsies.")
        assert _make([gc]).run(use_llm=False) == []

    def test_trial_linked_without_drug_keyword_kept(self):
        gc = _gc(
            "GSE444",
            "DMD muscle transcriptome",
            "Muscle biopsies at baseline and post-treatment timepoints.",
            design="Paired biopsies from trial participants.",
            pmid="31237898",
        )
        trial = ClinicalTrial(
            nct_id="NCT02255552", title="Eteplirsen", status="COMPLETED",
            interventions=["eteplirsen"], pmids=["31237898"], mentions_biopsy=True,
        )
        res = _make([gc], trials=[trial]).run(use_llm=False)
        assert len(res) == 1
        assert res[0].source == "both"
        assert res[0].linked_trials == ["NCT02255552"]
        assert "eteplirsen" in res[0].interventions


class TestOrchestratorSurvey:
    def test_survey_keeps_untreated_paired(self):
        gc = _gc("GSE333", "DMD natural history", "Muscle biopsies pre and post, no drug.",
                 design="Longitudinal biopsies.")
        s = _make([gc])
        assert s.run(use_llm=False, survey=False) == []
        res = s.run(use_llm=False, survey=True)
        assert len(res) == 1 and res[0].pairing_evidence.has_biopsy_signal

    def test_survey_requires_biopsy(self):
        gc = _gc("GSE555", "DMD blood", "Whole blood pre and post treatment, no muscle.")
        assert _make([gc]).run(use_llm=False, survey=True) == []

    def test_survey_excludes_mouse(self):
        gc = _gc("GSE666", "mdx mouse", "Mouse muscle biopsies pre and post.", organism="Mus musculus")
        assert _make([gc]).run(use_llm=False, survey=True) == []


class TestMarkdown:
    def test_empty(self):
        assert "No candidates" in to_markdown([])

    def test_contains_gse_link_and_signals(self):
        ev = detect_paired_pre_post(
            title="x", summary="muscle biopsy baseline post-treatment eteplirsen"
        )
        c = PairedBiopsyCandidate(
            candidate=_gc("GSE999", "Test", "s", n=6),
            pairing_evidence=ev,
            source="both",
            linked_trials=["NCT02255552"],
        )
        md = to_markdown([c])
        assert "GSE999" in md and "acc=GSE999" in md and "NCT02255552" in md
        assert "Signals" in md
