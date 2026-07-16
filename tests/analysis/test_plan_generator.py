"""
Tests for LLM-powered analysis plan generation with mocked LLM calls.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from quration.analysis.plan_generator import AnalysisPlanGenerator
from quration.analysis.models import PipelineType
from quration.llm import get_model_for_config


class TestAnalysisPlanGenerator:
    """Test analysis plan generator."""

    def test_create_plan_generator(self):
        """Test creating a plan generator."""
        generator = AnalysisPlanGenerator()

        # Default model tracks the configured "smart" tier (don't hardcode a model id
        # that goes stale on every model upgrade).
        assert generator.model == get_model_for_config(tier="smart")

    def test_create_with_custom_model(self):
        """Test creating with custom model."""
        generator = AnalysisPlanGenerator(model="claude-3-5-haiku-20241022")

        assert generator.model == "claude-3-5-haiku-20241022"

    @patch('quration.llm.get_provider_from_config')
    def test_generate_plan(
        self,
        mock_get_provider,
        sample_curated_dataset,
        sample_llm_plan_response,
    ):
        """Test generating an analysis plan with mocked LLM."""
        # Setup mock LLM
        mock_provider = Mock()
        mock_provider.create_message.return_value = sample_llm_plan_response
        mock_get_provider.return_value = mock_provider

        # Generate plan
        generator = AnalysisPlanGenerator()
        plan = generator.generate_plan(sample_curated_dataset)

        # Verify plan
        assert plan.dataset_id == "GSE123456"
        assert plan.primary_pipeline == PipelineType.RNASEQ
        assert plan.organism == "Homo sapiens"
        assert plan.sample_count == 3
        assert len(plan.comparison_groups) == 1
        assert plan.comparison_groups[0].name == "tumor_vs_normal"

        # Verify LLM was called
        mock_provider.create_message.assert_called_once()

    @patch('quration.llm.get_provider_from_config')
    def test_generate_plan_extracts_metadata(
        self,
        mock_get_provider,
        sample_curated_dataset,
        sample_llm_plan_response,
    ):
        """Test that metadata is correctly extracted and sent to LLM."""
        mock_provider = Mock()
        mock_provider.create_message.return_value = sample_llm_plan_response
        mock_get_provider.return_value = mock_provider

        generator = AnalysisPlanGenerator()
        generator.generate_plan(sample_curated_dataset)

        # Check that LLM was called with proper metadata
        call_args = mock_provider.create_message.call_args
        messages = call_args[1]["messages"]

        assert len(messages) == 1
        user_message = messages[0]["content"]

        # Verify key metadata is in the prompt
        assert "GSE123456" in user_message
        assert "RNA-seq" in user_message or "RNA-Seq" in user_message
        assert "breast cancer" in user_message

    @patch('quration.llm.get_provider_from_config')
    def test_generate_plan_handles_markdown_json(
        self,
        mock_get_provider,
        sample_curated_dataset,
    ):
        """Test that plan generator handles JSON in markdown code blocks."""
        # Return JSON wrapped in markdown
        markdown_response = f"""```json
        {{
            "recommended_pipelines": ["rnaseq"],
            "primary_pipeline": "rnaseq",
            "rationale": "Test",
            "comparison_groups": [],
            "expected_outputs": ["counts"],
            "estimated_runtime": "4h",
            "analysis_parameters": {{"genome_build": "GRCh38"}}
        }}
        ```"""

        mock_provider = Mock()
        mock_provider.create_message.return_value = markdown_response
        mock_get_provider.return_value = mock_provider

        generator = AnalysisPlanGenerator()
        plan = generator.generate_plan(sample_curated_dataset)

        assert plan is not None
        assert plan.primary_pipeline == PipelineType.RNASEQ

    @patch('quration.llm.get_provider_from_config')
    def test_generate_plan_invalid_json(
        self,
        mock_get_provider,
        sample_curated_dataset,
    ):
        """Test that invalid JSON from LLM raises error."""
        mock_provider = Mock()
        mock_provider.create_message.return_value = "not valid json"
        mock_get_provider.return_value = mock_provider

        generator = AnalysisPlanGenerator()

        with pytest.raises(ValueError, match="not valid JSON"):
            generator.generate_plan(sample_curated_dataset)

    @patch('quration.llm.get_provider_from_config')
    def test_generate_plan_from_file(
        self,
        mock_get_provider,
        sample_curated_dataset,
        sample_llm_plan_response,
        tmp_path,
    ):
        """Test generating plan from a file."""
        mock_provider = Mock()
        mock_provider.create_message.return_value = sample_llm_plan_response
        mock_get_provider.return_value = mock_provider

        # Save dataset to file
        dataset_file = tmp_path / "dataset.json"
        with open(dataset_file, "w") as f:
            json.dump(sample_curated_dataset, f)

        # Generate plan from file
        generator = AnalysisPlanGenerator()
        plan = generator.generate_plan_from_file(dataset_file)

        assert plan.dataset_id == "GSE123456"

    def test_save_plan(self, sample_analysis_plan, tmp_path):
        """Test saving analysis plan to file."""
        generator = AnalysisPlanGenerator()
        output_file = tmp_path / "plan.json"

        generator.save_plan(sample_analysis_plan, output_file)

        assert output_file.exists()

        # Verify saved content
        with open(output_file) as f:
            saved_plan = json.load(f)

        assert saved_plan["dataset_id"] == "GSE123456"
        assert saved_plan["primary_pipeline"] == "rnaseq"


class TestMetadataExtraction:
    """Test metadata extraction for LLM prompts."""

    @patch('quration.llm.get_provider_from_config')
    def test_extract_metadata_summary(
        self,
        mock_get_provider,
        sample_curated_dataset,
        sample_llm_plan_response,
    ):
        """Test metadata extraction creates correct summary."""
        mock_provider = Mock()
        mock_provider.create_message.return_value = sample_llm_plan_response
        mock_get_provider.return_value = mock_provider

        generator = AnalysisPlanGenerator()
        summary = generator._extract_metadata_summary(sample_curated_dataset)

        assert summary["dataset_id"] == "GSE123456"
        assert summary["sample_count"] == 3
        assert len(summary["samples"]) == 3
        assert summary["protocol"]["library_strategy"] == "RNA-Seq"

    @patch('quration.llm.get_provider_from_config')
    def test_extract_limits_sample_count(
        self,
        mock_get_provider,
        sample_llm_plan_response,
    ):
        """Test that metadata extraction limits sample count to 10."""
        # Create dataset with many samples
        dataset = {
            "dataset_id": "GSE123456",
            "title": "Test",
            "summary": "Test",
            "samples": [
                {"sample_id": f"GSM{i}", "characteristics": {}}
                for i in range(20)
            ],
            "protocol": {"library_strategy": "RNA-Seq"},
        }

        mock_provider = Mock()
        mock_provider.create_message.return_value = sample_llm_plan_response
        mock_get_provider.return_value = mock_provider

        generator = AnalysisPlanGenerator()
        summary = generator._extract_metadata_summary(dataset)

        # Should limit to 10 samples in summary
        assert len(summary["samples"]) == 10


class TestPlanConstruction:
    """Test analysis plan construction from LLM response."""

    @patch('quration.llm.get_provider_from_config')
    def test_build_analysis_plan(
        self,
        mock_get_provider,
        sample_curated_dataset,
        sample_llm_plan_response,
    ):
        """Test building analysis plan from LLM response."""
        mock_provider = Mock()
        mock_provider.create_message.return_value = sample_llm_plan_response
        mock_get_provider.return_value = mock_provider

        generator = AnalysisPlanGenerator()
        plan_data = json.loads(sample_llm_plan_response)

        plan = generator._build_analysis_plan(plan_data, sample_curated_dataset)

        assert plan.dataset_id == "GSE123456"
        assert plan.primary_pipeline == PipelineType.RNASEQ
        assert plan.suggested_genome.name == "GRCh38"

    @patch('quration.llm.get_provider_from_config')
    def test_build_plan_handles_unknown_pipeline(
        self,
        mock_get_provider,
        sample_curated_dataset,
    ):
        """Test that unknown pipeline types are handled gracefully."""
        llm_response = json.dumps({
            "recommended_pipelines": ["unknown_pipeline", "rnaseq"],
            "primary_pipeline": "rnaseq",
            "rationale": "Test",
            "comparison_groups": [],
            "expected_outputs": [],
            "analysis_parameters": {"genome_build": "GRCh38"},
        })

        mock_provider = Mock()
        mock_provider.create_message.return_value = llm_response
        mock_get_provider.return_value = mock_provider

        generator = AnalysisPlanGenerator()
        plan = generator.generate_plan(sample_curated_dataset)

        # Should still create plan with valid pipelines
        assert plan.primary_pipeline == PipelineType.RNASEQ

    @patch('quration.llm.get_provider_from_config')
    def test_build_plan_infers_genome(
        self,
        mock_get_provider,
        sample_curated_dataset,
    ):
        """Test that genome is inferred if not specified."""
        llm_response = json.dumps({
            "recommended_pipelines": ["rnaseq"],
            "primary_pipeline": "rnaseq",
            "rationale": "Test",
            "comparison_groups": [],
            "expected_outputs": [],
            "analysis_parameters": {},  # No genome specified
        })

        mock_provider = Mock()
        mock_provider.create_message.return_value = llm_response
        mock_get_provider.return_value = mock_provider

        generator = AnalysisPlanGenerator()
        plan = generator.generate_plan(sample_curated_dataset)

        # Should infer GRCh38 for Homo sapiens
        assert plan.suggested_genome.name == "GRCh38"


class TestLLMPromptGeneration:
    """Test LLM prompt generation."""

    @patch('quration.llm.get_provider_from_config')
    def test_prompt_includes_system_message(
        self,
        mock_get_provider,
        sample_curated_dataset,
        sample_llm_plan_response,
    ):
        """Test that system prompt is included."""
        mock_provider = Mock()
        mock_provider.create_message.return_value = sample_llm_plan_response
        mock_get_provider.return_value = mock_provider

        generator = AnalysisPlanGenerator()
        generator.generate_plan(sample_curated_dataset)

        # Verify system prompt was provided
        call_args = mock_provider.create_message.call_args
        system = call_args[1]["system"]

        assert "bioinformatician" in system.lower()
        assert "nf-core" in system.lower()

    @patch('quration.llm.get_provider_from_config')
    def test_prompt_uses_low_temperature(
        self,
        mock_get_provider,
        sample_curated_dataset,
        sample_llm_plan_response,
    ):
        """Test that low temperature is used for consistent recommendations."""
        mock_provider = Mock()
        mock_provider.create_message.return_value = sample_llm_plan_response
        mock_get_provider.return_value = mock_provider

        generator = AnalysisPlanGenerator()
        generator.generate_plan(sample_curated_dataset)

        # Verify low temperature
        call_args = mock_provider.create_message.call_args
        temperature = call_args[1]["temperature"]

        assert temperature < 0.5  # Should be low for consistency
