"""Tests for GEO survival data detection."""


from quration.data_sources.geo_survival_detector import (
    detect_maybe_has_survival_data,
    detect_survival_data,
    extract_survival_keywords,
)


class TestSurvivalDetection:
    """Tests for survival data detection."""

    def test_detect_overall_survival_in_title(self):
        """Test detection of 'overall survival' in title."""
        assert detect_survival_data(
            title="Overall survival analysis in lung cancer patients",
            summary="A gene expression study",
        )

    def test_detect_pfs_in_summary(self):
        """Test detection of 'progression-free survival' in summary."""
        assert detect_survival_data(
            title="Gene expression study",
            summary="This study includes progression-free survival data",
        )

    def test_detect_prognosis(self):
        """Test detection of 'prognosis' keyword."""
        assert detect_survival_data(
            summary="Analysis of prognostic markers in breast cancer"
        )

    def test_detect_nct_id(self):
        """Test detection of clinical trial NCT ID."""
        assert detect_survival_data(
            title="Clinical trial NCT01234567 expression data"
        )

    def test_detect_clinical_trial_text(self):
        """Test detection of 'clinical trial' text."""
        assert detect_survival_data(
            summary="Samples from a phase III clinical trial"
        )

    def test_detect_followup(self):
        """Test detection of 'follow-up'."""
        assert detect_survival_data(
            overall_design="Patients were followed for 5 years"
        )

    def test_detect_kaplan_meier(self):
        """Test detection of 'Kaplan-Meier' (survival analysis method)."""
        assert detect_survival_data(
            summary="Kaplan-Meier analysis was performed"
        )

    def test_no_survival_data(self):
        """Test that non-clinical studies return False."""
        assert not detect_survival_data(
            title="In vitro cell line study",
            summary="Gene expression in cultured HeLa cells",
        )

    def test_empty_fields(self):
        """Test with empty fields."""
        assert not detect_survival_data(title="", summary="")

    def test_case_insensitive(self):
        """Test that detection is case-insensitive."""
        assert detect_survival_data(
            title="SURVIVAL ANALYSIS",
            summary="PROGNOSIS markers",
        )


class TestSurvivalKeywordExtraction:
    """Tests for survival keyword extraction."""

    def test_extract_os_keyword(self):
        """Test extraction of 'overall survival'."""
        keywords = extract_survival_keywords(
            summary="Overall survival was the primary endpoint"
        )
        assert "overall survival" in keywords

    def test_extract_multiple_keywords(self):
        """Test extraction of multiple keywords."""
        keywords = extract_survival_keywords(
            summary="Overall survival and progression-free survival were analyzed"
        )
        assert "overall survival" in keywords
        assert "progression-free survival" in keywords

    def test_extract_nct_id(self):
        """Test extraction of NCT ID."""
        keywords = extract_survival_keywords(
            title="Clinical trial NCT01234567"
        )
        assert any("NCT01234567" in k for k in keywords)

    def test_no_keywords(self):
        """Test with no survival keywords."""
        keywords = extract_survival_keywords(
            summary="Cell line expression profiling"
        )
        assert len(keywords) == 0


class TestSpecCompliantFunction:
    """Tests for spec-compliant detect_maybe_has_survival_data function."""

    def test_spec_function_with_survival_data(self):
        """Test spec function detects survival data."""
        result = detect_maybe_has_survival_data(
            title="Overall survival analysis",
            summary="Study of patient outcomes",
            overall_design="Clinical trial design",
            primary_pmid="12345678",
            raw_metadata={"some": "data"},
        )
        assert result is True

    def test_spec_function_without_survival_data(self):
        """Test spec function returns False for non-clinical data."""
        result = detect_maybe_has_survival_data(
            title="Cell line study",
            summary="In vitro experiments",
            overall_design="Laboratory experiment",
            primary_pmid=None,
            raw_metadata={},
        )
        assert result is False
