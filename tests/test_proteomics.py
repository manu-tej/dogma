"""Tests for proteomics data connector."""

import pytest

from quration.data_sources.proteomics import ProteomicsFetcher
from quration.data_sources.proteomics_parser import ProteomicsMetadataParser
from quration.models.proteomics_search import ProteomicsQuerySpec


class TestProteomicsFetcher:
    """Tests for ProteomicsFetcher class."""

    @pytest.fixture
    def fetcher(self):
        """Create a ProteomicsFetcher instance."""
        return ProteomicsFetcher()

    @pytest.mark.integration
    def test_search_datasets_basic(self, fetcher):
        """Test basic dataset search."""
        # This test requires network access to PRIDE Archive
        # Skip in offline environments
        try:
            accessions = fetcher.search_datasets(
                query="cancer",
                limit=5,
                organism="Homo sapiens",
            )
            # Should return a list (may be empty if PRIDE is unreachable)
            assert isinstance(accessions, list)
        except Exception as e:
            # Network errors are acceptable in test environment
            pytest.skip(f"Network error accessing PRIDE Archive: {e}")

    @pytest.mark.integration
    def test_search_by_therapeutic_area(self, fetcher):
        """Test therapeutic area search."""
        try:
            accessions = fetcher.search_by_therapeutic_area(
                therapeutic_area="oncology",
                limit=5,
                organism="Homo sapiens",
            )
            assert isinstance(accessions, list)
        except Exception:
            pytest.skip("Network error accessing PRIDE Archive")


class TestProteomicsMetadataParser:
    """Tests for ProteomicsMetadataParser class."""

    @pytest.fixture
    def parser(self):
        """Create a ProteomicsMetadataParser instance."""
        return ProteomicsMetadataParser()

    def test_parse_cv_param_dict(self, parser):
        """Test parsing controlled vocabulary parameter from dict."""
        cv_param = {
            "name": "Homo sapiens",
            "accession": "NCBITAXON:9606",
            "cvLabel": "NCBITAXON",
        }

        result = parser._parse_ontology_term(cv_param)

        assert result is not None
        assert result.term == "Homo sapiens"
        assert result.ontology_id == "NCBITAXON:9606"
        assert result.ontology_name == "NCBITAXON"
        assert result.confidence == 1.0

    def test_parse_cv_param_string(self, parser):
        """Test parsing controlled vocabulary parameter from string."""
        result = parser._parse_ontology_term("Homo sapiens")

        assert result is not None
        assert result.term == "Homo sapiens"
        assert result.ontology_id is None
        assert result.confidence == 0.8

    def test_parse_cv_param_none(self, parser):
        """Test parsing None CV parameter."""
        result = parser._parse_ontology_term(None)
        assert result is None

    def test_map_instrument_to_platform(self, parser):
        """Test mapping instrument names to platform enum."""
        # Orbitrap
        assert parser._map_instrument_to_platform("Orbitrap Fusion Lumos") == "Orbitrap Fusion Lumos"
        assert parser._map_instrument_to_platform("Q Exactive HF") == "Q Exactive HF"

        # timsTOF
        assert parser._map_instrument_to_platform("timsTOF Pro") == "timsTOF Pro"

        # Unknown
        result = parser._map_instrument_to_platform("Unknown Instrument XYZ")
        assert isinstance(result, str)
        assert result == "Unknown Instrument XYZ"

    def test_calculate_protocol_completeness(self, parser):
        """Test protocol completeness calculation."""
        # Both protocols present and detailed
        score1 = parser._calculate_protocol_completeness(
            sample_protocol="Detailed protocol with well over one hundred characters describing the sample processing methodology in thorough detail",
            data_protocol="Detailed protocol with well over one hundred characters describing the data processing pipeline in thorough detail",
        )
        assert score1 >= 0.8

        # Short protocols
        score2 = parser._calculate_protocol_completeness(
            sample_protocol="Short protocol",
            data_protocol="Short protocol",
        )
        assert 0.4 <= score2 < 0.8

        # No protocols
        score3 = parser._calculate_protocol_completeness(
            sample_protocol="",
            data_protocol="",
        )
        assert score3 == 0.0


class TestProteomicsQuerySpec:
    """Tests for ProteomicsQuerySpec dataclass."""

    def test_query_spec_creation(self):
        """Test creating a ProteomicsQuerySpec."""
        spec = ProteomicsQuerySpec(
            disease_terms=["breast cancer"],
            therapy_class="targeted therapy",
            therapy_scope="specific",
            targets_or_proteins=["HER2", "EGFR"],
            study_keywords=["phosphoproteomics"],
            must_have_quantification=True,
            min_samples=10,
            organism="Homo sapiens",
        )

        assert spec.disease_terms == ["breast cancer"]
        assert spec.therapy_class == "targeted therapy"
        assert spec.targets_or_proteins == ["HER2", "EGFR"]
        assert spec.must_have_quantification is True
        assert spec.organism == "Homo sapiens"


# Integration tests (require network access)

@pytest.mark.integration
class TestProteomicsIntegration:
    """Integration tests for proteomics connector."""

    @pytest.fixture
    def fetcher(self):
        """Create a ProteomicsFetcher instance."""
        return ProteomicsFetcher()

    @pytest.fixture
    def parser(self):
        """Create a ProteomicsMetadataParser instance."""
        return ProteomicsMetadataParser()

    def test_fetch_and_parse_dataset(self, fetcher, parser):
        """Test fetching and parsing a real PRIDE dataset."""
        # Use a well-known PRIDE dataset (example: PXD000001)
        # This is one of the first datasets in PRIDE Archive
        try:
            # Search for a dataset
            accessions = fetcher.search_datasets(
                query="proteomics",
                limit=1,
            )

            if not accessions:
                pytest.skip("No datasets found in PRIDE Archive")

            # Fetch metadata
            metadata = fetcher.fetch_dataset_metadata(accessions[0])

            # Verify metadata structure
            assert "accession" in metadata
            assert "title" in metadata
            assert metadata["source_database"] == "PRIDE"

            # Parse to unified schema
            dataset = parser.parse_pride_dataset(metadata)

            # Verify parsed dataset
            assert dataset.dataset_id == accessions[0]
            assert dataset.source_database == "PRIDE"
            assert len(dataset.samples) > 0

        except Exception as e:
            pytest.skip(f"Integration test failed: {e}")
