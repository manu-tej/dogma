# Analysis Module Tests

This directory contains comprehensive tests for the Quration analysis module.

## Test Organization

- **conftest.py**: Shared fixtures and test data
- **test_models.py**: Tests for Pydantic models and validation
- **test_pipeline_registry.py**: Tests for pipeline registry and matching logic
- **test_config_generator.py**: Tests for configuration generation
- **test_data_fetcher.py**: Tests for GEO/SRA data fetching (with mocked APIs)
- **test_plan_generator.py**: Tests for LLM-powered plan generation (with mocked LLM)

## Running Tests

Run all analysis tests:
```bash
pytest tests/analysis/
```

Run specific test file:
```bash
pytest tests/analysis/test_models.py
```

Run with coverage:
```bash
pytest tests/analysis/ --cov=src/quration/analysis --cov-report=html
```

Run specific test:
```bash
pytest tests/analysis/test_models.py::TestReferenceGenome::test_create_reference_genome
```

## Test Coverage

Current test coverage includes:

### Models (test_models.py)
- ✅ Reference genome creation and validation
- ✅ Comparison group models
- ✅ Pipeline parameter models (RNA-seq, fetchngs)
- ✅ Pipeline configuration
- ✅ Analysis plan creation
- ✅ Execution results
- ✅ Samplesheet generation
- ✅ Enum types

### Pipeline Registry (test_pipeline_registry.py)
- ✅ Pipeline metadata retrieval
- ✅ Pipeline matching based on library strategy
- ✅ Library strategy normalization
- ✅ Genome registry for model organisms
- ✅ Default genome selection

### Config Generation (test_config_generator.py)
- ✅ FetchNGS configuration generation
- ✅ RNA-seq configuration generation
- ✅ Samplesheet creation (paired-end and single-end)
- ✅ Contrast file generation for DE analysis
- ✅ Custom Nextflow config generation
- ✅ Profile selection by compute environment

### Data Fetcher (test_data_fetcher.py)
- ✅ GEO to SRA conversion (mocked NCBI API)
- ✅ SRA data fetching
- ✅ FASTQ directory detection
- ✅ SRA ID extraction from curated datasets
- ✅ Error handling for invalid IDs

### Plan Generator (test_plan_generator.py)
- ✅ Analysis plan generation (mocked LLM)
- ✅ Metadata extraction and summarization
- ✅ Plan construction from LLM response
- ✅ Genome inference
- ✅ Comparison group extraction
- ✅ JSON parsing with markdown code blocks
- ✅ Error handling for invalid LLM responses

## Mocking Strategy

Tests use mocking to avoid external dependencies:

- **NCBI API**: Mocked with `unittest.mock.patch` on `requests.get`
- **LLM calls**: Mocked with `patch` on `get_llm_provider`
- **Nextflow execution**: Mocked to avoid requiring Nextflow installation
- **File system**: Uses pytest's `tmp_path` fixture for temporary directories

## Fixtures

Common fixtures are defined in `conftest.py`:

- `sample_curated_dataset`: Mock curated dataset
- `sample_analysis_plan`: Mock analysis plan
- `sample_sra_ids`: List of SRA IDs
- `tmp_output_dir`: Temporary output directory
- `mock_fastq_dir`: Mock FASTQ directory with sample files
- `sample_ncbi_*_response`: Mock NCBI API responses
- `sample_llm_plan_response`: Mock LLM response

## Adding New Tests

When adding new features to the analysis module:

1. Add test fixtures to `conftest.py` if needed
2. Create test class following the existing pattern
3. Mock external dependencies (APIs, LLM calls, Nextflow)
4. Test both success and error cases
5. Verify that tests run in isolation

Example:

```python
class TestNewFeature:
    """Test new feature."""

    def test_feature_works(self, sample_fixture):
        """Test that feature works correctly."""
        # Setup
        feature = NewFeature()

        # Execute
        result = feature.do_something(sample_fixture)

        # Verify
        assert result is not None
```

## Test Requirements

Additional dependencies for testing:
- pytest>=8.2.0
- pytest-cov>=5.0.0
- pytest-mock (for advanced mocking)

Install with:
```bash
pip install -e ".[dev]"
```
