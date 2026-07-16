"""
Tests for data fetcher with mocked NCBI API calls.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from quration.analysis.data_fetcher import DataFetcher, GEOToSRAConverter


class TestGEOToSRAConverter:
    """Test GEO to SRA conversion with mocked API calls."""

    def test_create_converter(self):
        """Test creating a converter."""
        converter = GEOToSRAConverter(email="test@example.com")

        assert converter.email == "test@example.com"
        assert converter.api_key is None

    def test_create_with_api_key(self):
        """Test creating converter with API key."""
        converter = GEOToSRAConverter(
            email="test@example.com",
            api_key="test_key"
        )

        assert converter.api_key == "test_key"

    @patch('quration.analysis.data_fetcher.requests.get')
    def test_convert_gse_to_sra(
        self,
        mock_get,
        sample_ncbi_esearch_response,
        sample_ncbi_elink_response,
        sample_ncbi_efetch_xml,
    ):
        """Test converting GSE to SRA IDs with mocked API."""
        # Setup mock responses
        mock_responses = [
            Mock(status_code=200),  # esearch
            Mock(status_code=200),  # elink
            Mock(status_code=200),  # efetch
        ]
        mock_responses[0].json.return_value = sample_ncbi_esearch_response
        mock_responses[1].json.return_value = sample_ncbi_elink_response
        mock_responses[2].text = sample_ncbi_efetch_xml

        mock_get.side_effect = mock_responses

        # Test conversion
        converter = GEOToSRAConverter(email="test@example.com")
        sra_ids = converter.convert_geo_to_sra("GSE123456")

        assert len(sra_ids) > 0
        assert "SRR123456" in sra_ids
        assert mock_get.call_count == 3

    @patch('quration.analysis.data_fetcher.requests.get')
    def test_convert_gse_no_results(self, mock_get):
        """Test converting GSE with no results."""
        # Setup mock with empty results
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            "esearchresult": {
                "idlist": [],
                "count": "0",
            }
        }
        mock_get.return_value = mock_response

        converter = GEOToSRAConverter(email="test@example.com")
        sra_ids = converter.convert_geo_to_sra("GSE999999")

        assert len(sra_ids) == 0

    @patch('quration.analysis.data_fetcher.requests.get')
    def test_convert_gsm_to_sra(
        self,
        mock_get,
        sample_ncbi_esearch_response,
        sample_ncbi_elink_response,
        sample_ncbi_efetch_xml,
    ):
        """Test converting GSM to SRA IDs."""
        # Setup mock responses
        mock_responses = [
            Mock(status_code=200),  # esearch
            Mock(status_code=200),  # elink
            Mock(status_code=200),  # efetch
        ]
        mock_responses[0].json.return_value = sample_ncbi_esearch_response
        mock_responses[1].json.return_value = sample_ncbi_elink_response
        mock_responses[2].text = sample_ncbi_efetch_xml

        mock_get.side_effect = mock_responses

        converter = GEOToSRAConverter(email="test@example.com")
        sra_ids = converter.convert_geo_to_sra("GSM111111")

        assert len(sra_ids) > 0

    def test_convert_invalid_geo_id(self):
        """Test converting invalid GEO ID raises error."""
        converter = GEOToSRAConverter(email="test@example.com")

        with pytest.raises(ValueError, match="Unsupported GEO accession type"):
            converter.convert_geo_to_sra("GPL12345")  # Platform, not supported

    @patch('quration.analysis.data_fetcher.requests.get')
    def test_api_includes_email(self, mock_get):
        """Test that API requests include email parameter."""
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            "esearchresult": {"idlist": [], "count": "0"}
        }
        mock_get.return_value = mock_response

        converter = GEOToSRAConverter(email="test@example.com")
        converter.convert_geo_to_sra("GSE123456")

        # Check that email was included in request
        call_args = mock_get.call_args
        assert call_args[1]["params"]["email"] == "test@example.com"

    @patch('quration.analysis.data_fetcher.requests.get')
    def test_api_includes_api_key(self, mock_get):
        """Test that API requests include API key if provided."""
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            "esearchresult": {"idlist": [], "count": "0"}
        }
        mock_get.return_value = mock_response

        converter = GEOToSRAConverter(
            email="test@example.com",
            api_key="test_key"
        )
        converter.convert_geo_to_sra("GSE123456")

        # Check that API key was included
        call_args = mock_get.call_args
        assert call_args[1]["params"]["api_key"] == "test_key"


class TestDataFetcher:
    """Test data fetcher functionality."""

    def test_create_data_fetcher(self):
        """Test creating a data fetcher."""
        fetcher = DataFetcher(email="test@example.com")

        assert fetcher.converter.email == "test@example.com"
        assert fetcher.executor is not None

    @patch.object(GEOToSRAConverter, 'convert_geo_to_sra')
    @patch('quration.analysis.data_fetcher.NextflowExecutor')
    def test_fetch_from_geo(
        self,
        mock_executor_class,
        mock_convert,
        tmp_output_dir,
    ):
        """Test fetching data from GEO."""
        from quration.analysis.models import ExecutionResult, ExecutionStatus, PipelineType
        from datetime import datetime

        # Setup mocks
        mock_convert.return_value = ["SRR123456", "SRR123457"]

        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor

        mock_result = ExecutionResult(
            pipeline_type=PipelineType.FETCHNGS,
            dataset_id="GSE123456",
            status=ExecutionStatus.COMPLETED,
            started_at=datetime.now(),
            work_dir="/work",
            output_dir=str(tmp_output_dir),
        )
        mock_executor.execute_pipeline.return_value = mock_result

        # Test fetch
        fetcher = DataFetcher(email="test@example.com")
        result = fetcher.fetch_from_geo(
            geo_id="GSE123456",
            output_dir=tmp_output_dir,
        )

        assert result.status == ExecutionStatus.COMPLETED
        mock_convert.assert_called_once_with("GSE123456")
        mock_executor.execute_pipeline.assert_called_once()

    @patch.object(GEOToSRAConverter, 'convert_geo_to_sra')
    def test_fetch_from_geo_no_sra_ids(self, mock_convert, tmp_output_dir):
        """Test fetching when no SRA IDs found."""
        mock_convert.return_value = []  # No SRA IDs

        fetcher = DataFetcher(email="test@example.com")

        with pytest.raises(ValueError, match="Could not find SRA accessions"):
            fetcher.fetch_from_geo(
                geo_id="GSE999999",
                output_dir=tmp_output_dir,
            )

    @patch('quration.analysis.data_fetcher.NextflowExecutor')
    def test_fetch_from_sra(self, mock_executor_class, tmp_output_dir, sample_sra_ids):
        """Test fetching data from SRA directly."""
        from quration.analysis.models import ExecutionResult, ExecutionStatus, PipelineType
        from datetime import datetime

        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor

        mock_result = ExecutionResult(
            pipeline_type=PipelineType.FETCHNGS,
            dataset_id="SRR123456",
            status=ExecutionStatus.COMPLETED,
            started_at=datetime.now(),
            work_dir="/work",
            output_dir=str(tmp_output_dir),
        )
        mock_executor.execute_pipeline.return_value = mock_result

        fetcher = DataFetcher(email="test@example.com")
        result = fetcher.fetch_from_sra(
            sra_ids=sample_sra_ids,
            output_dir=tmp_output_dir,
        )

        assert result.status == ExecutionStatus.COMPLETED
        mock_executor.execute_pipeline.assert_called_once()

    def test_get_fastq_directory(self, tmp_output_dir):
        """Test finding FASTQ directory in fetchngs output."""
        # Create mock structure
        fastq_dir = tmp_output_dir / "fastq"
        fastq_dir.mkdir()
        (fastq_dir / "sample1.fastq.gz").touch()

        fetcher = DataFetcher(email="test@example.com")
        found_dir = fetcher.get_fastq_directory(tmp_output_dir)

        assert found_dir == fastq_dir

    def test_get_fastq_directory_not_found(self, tmp_output_dir):
        """Test when FASTQ directory doesn't exist."""
        fetcher = DataFetcher(email="test@example.com")
        found_dir = fetcher.get_fastq_directory(tmp_output_dir)

        assert found_dir is None

    def test_extract_sra_ids_from_dataset(self, sample_curated_dataset):
        """Test extracting SRA IDs from curated dataset."""
        fetcher = DataFetcher(email="test@example.com")
        sra_ids = fetcher.extract_sra_ids_from_curated_dataset(sample_curated_dataset)

        assert len(sra_ids) == 3
        assert "SRR123456" in sra_ids
        assert "SRR123457" in sra_ids
        assert "SRR123458" in sra_ids

    def test_extract_sra_ids_no_duplicates(self):
        """Test that duplicate SRA IDs are removed."""
        dataset = {
            "samples": [
                {"sra_id": "SRR123456"},
                {"sra_id": "SRR123456"},  # Duplicate
                {"sra_id": "SRR123457"},
            ]
        }

        fetcher = DataFetcher(email="test@example.com")
        sra_ids = fetcher.extract_sra_ids_from_curated_dataset(dataset)

        assert len(sra_ids) == 2
        assert "SRR123456" in sra_ids
        assert "SRR123457" in sra_ids


class TestFetchNGSIntegration:
    """Integration tests for fetchngs workflow."""

    @patch.object(GEOToSRAConverter, 'convert_geo_to_sra')
    @patch('quration.analysis.data_fetcher.NextflowExecutor')
    @patch('quration.analysis.data_fetcher.ConfigGenerator')
    def test_full_fetch_workflow(
        self,
        mock_config_gen_class,
        mock_executor_class,
        mock_convert,
        tmp_output_dir,
    ):
        """Test complete fetch workflow from GEO to FASTQ."""
        from quration.analysis.models import (
            ExecutionResult,
            ExecutionStatus,
            PipelineType,
            PipelineConfig,
            FetchNGSParameters,
        )
        from datetime import datetime

        # Setup mocks
        mock_convert.return_value = ["SRR123456", "SRR123457"]

        mock_config_gen = Mock()
        mock_config_gen_class.return_value = mock_config_gen

        mock_config = PipelineConfig(
            pipeline_type=PipelineType.FETCHNGS,
            parameters=FetchNGSParameters(
                input=str(tmp_output_dir / "sra_ids.csv"),
                outdir=str(tmp_output_dir / "fetchngs_output"),
            ),
        )
        mock_config_gen.generate_fetchngs_config.return_value = mock_config

        mock_executor = Mock()
        mock_executor_class.return_value = mock_executor

        mock_result = ExecutionResult(
            pipeline_type=PipelineType.FETCHNGS,
            dataset_id="GSE123456",
            status=ExecutionStatus.COMPLETED,
            started_at=datetime.now(),
            work_dir="/work",
            output_dir=str(tmp_output_dir / "fetchngs_output"),
        )
        mock_executor.execute_pipeline.return_value = mock_result

        # Run workflow
        fetcher = DataFetcher(email="test@example.com")
        result = fetcher.fetch_from_geo(
            geo_id="GSE123456",
            output_dir=tmp_output_dir,
            download_method="ftp",
            for_pipeline="rnaseq",
            wait=True,
        )

        # Verify workflow
        assert result.status == ExecutionStatus.COMPLETED
        mock_convert.assert_called_once()
        mock_executor.execute_pipeline.assert_called_once()
