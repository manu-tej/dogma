"""
Test fixtures for analysis module tests.

Provides sample data for curated datasets, analysis plans, and other test objects.
"""

import pytest
from pathlib import Path


@pytest.fixture
def sample_curated_dataset():
    """Sample curated dataset for testing."""
    return {
        "dataset_id": "GSE123456",
        "title": "RNA-seq analysis of breast cancer samples",
        "summary": "This study examines gene expression differences between tumor and normal tissue",
        "samples": [
            {
                "sample_id": "GSM111111",
                "sample_name": "Tumor_1",
                "characteristics": {
                    "organism": {"term": "Homo sapiens", "ontology_id": "NCBITaxon:9606"},
                    "tissue": {"term": "breast", "ontology_id": "UBERON:0000310"},
                    "disease": {"term": "breast cancer", "ontology_id": "DOID:1612"},
                    "treatment": None,
                },
                "sra_id": "SRR123456",
            },
            {
                "sample_id": "GSM111112",
                "sample_name": "Tumor_2",
                "characteristics": {
                    "organism": {"term": "Homo sapiens", "ontology_id": "NCBITaxon:9606"},
                    "tissue": {"term": "breast", "ontology_id": "UBERON:0000310"},
                    "disease": {"term": "breast cancer", "ontology_id": "DOID:1612"},
                    "treatment": None,
                },
                "sra_id": "SRR123457",
            },
            {
                "sample_id": "GSM111113",
                "sample_name": "Normal_1",
                "characteristics": {
                    "organism": {"term": "Homo sapiens", "ontology_id": "NCBITaxon:9606"},
                    "tissue": {"term": "breast", "ontology_id": "UBERON:0000310"},
                    "disease": None,
                    "treatment": None,
                },
                "sra_id": "SRR123458",
            },
        ],
        "protocol": {
            "library_strategy": "RNA-Seq",
            "library_source": "TRANSCRIPTOMIC",
            "library_selection": "cDNA",
            "instrument_model": "Illumina HiSeq 2500",
            "read_length": 100,
            "is_paired_end": True,
        },
        "experimental_design": "Case-control study comparing tumor vs normal breast tissue",
    }


@pytest.fixture
def sample_analysis_plan():
    """Sample analysis plan for testing."""
    from quration.analysis.models import (
        AnalysisPlan,
        ComparisonGroup,
        PipelineType,
        ReferenceGenome,
    )

    return AnalysisPlan(
        dataset_id="GSE123456",
        dataset_title="RNA-seq analysis of breast cancer samples",
        recommended_pipelines=[PipelineType.RNASEQ],
        primary_pipeline=PipelineType.RNASEQ,
        organism="Homo sapiens",
        library_strategy="RNA-Seq",
        sample_count=3,
        has_paired_end=True,
        suggested_genome=ReferenceGenome(
            name="GRCh38",
            organism="Homo sapiens",
            igenomes_ref="GRCh38",
        ),
        experimental_design="Case-control study comparing tumor vs normal breast tissue",
        comparison_groups=[
            ComparisonGroup(
                name="tumor_vs_normal",
                condition_a="tumor",
                condition_b="normal",
                sample_ids_a=["GSM111111", "GSM111112"],
                sample_ids_b=["GSM111113"],
            )
        ],
        rationale="RNA-seq pipeline recommended for gene expression analysis",
        expected_outputs=["Gene counts", "Differential expression results", "QC reports"],
        estimated_runtime="4-6 hours",
        requires_download=False,
        sra_ids=["SRR123456", "SRR123457", "SRR123458"],
    )


@pytest.fixture
def sample_sra_ids():
    """Sample SRA IDs for testing."""
    return ["SRR123456", "SRR123457", "SRR123458"]


@pytest.fixture
def tmp_output_dir(tmp_path):
    """Temporary output directory for tests."""
    output_dir = tmp_path / "test_output"
    output_dir.mkdir()
    return output_dir


@pytest.fixture
def mock_fastq_dir(tmp_path):
    """Mock FASTQ directory with sample files."""
    fastq_dir = tmp_path / "fastq"
    fastq_dir.mkdir()

    # Create mock FASTQ files
    for sample_id in ["GSM111111", "GSM111112", "GSM111113"]:
        (fastq_dir / f"{sample_id}_1.fastq.gz").touch()
        (fastq_dir / f"{sample_id}_2.fastq.gz").touch()

    return fastq_dir


@pytest.fixture
def sample_multiqc_data():
    """Sample MultiQC data for testing."""
    return {
        "report_general_stats_data": [
            {
                "GSM111111": {
                    "total_reads": 10000000,
                    "percent_gc": 50,
                },
                "GSM111112": {
                    "total_reads": 12000000,
                    "percent_gc": 52,
                },
            }
        ],
        "report_saved_raw_data": {
            "multiqc_fastqc": {
                "GSM111111": {
                    "basic_statistics": "pass",
                    "per_base_sequence_quality": "pass",
                },
                "GSM111112": {
                    "basic_statistics": "pass",
                    "per_base_sequence_quality": "warn",
                },
            }
        },
    }


@pytest.fixture
def sample_ncbi_esearch_response():
    """Sample NCBI E-Search API response."""
    return {
        "esearchresult": {
            "idlist": ["200123456"],
            "count": "1",
        }
    }


@pytest.fixture
def sample_ncbi_elink_response():
    """Sample NCBI E-Link API response."""
    return {
        "linksets": [
            {
                "linksetdbs": [
                    {
                        "dbto": "sra",
                        "links": ["300123456", "300123457", "300123458"],
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_ncbi_efetch_xml():
    """Sample NCBI E-Fetch XML response."""
    return """<?xml version="1.0"?>
    <EXPERIMENT_PACKAGE_SET>
        <EXPERIMENT_PACKAGE>
            <RUN_SET>
                <RUN>
                    <IDENTIFIERS>
                        <PRIMARY_ID>SRR123456</PRIMARY_ID>
                    </IDENTIFIERS>
                </RUN>
                <RUN>
                    <IDENTIFIERS>
                        <PRIMARY_ID>SRR123457</PRIMARY_ID>
                    </IDENTIFIERS>
                </RUN>
                <RUN>
                    <IDENTIFIERS>
                        <PRIMARY_ID>SRR123458</PRIMARY_ID>
                    </IDENTIFIERS>
                </RUN>
            </RUN_SET>
        </EXPERIMENT_PACKAGE>
    </EXPERIMENT_PACKAGE_SET>
    """


@pytest.fixture
def sample_llm_plan_response():
    """Sample LLM response for analysis plan generation."""
    return """{
        "recommended_pipelines": ["rnaseq"],
        "primary_pipeline": "rnaseq",
        "rationale": "RNA-seq pipeline is recommended for this dataset because it contains RNA-Seq data from a case-control study comparing tumor vs normal tissue. The dataset has paired-end reads and sufficient sample size for differential expression analysis.",
        "comparison_groups": [
            {
                "name": "tumor_vs_normal",
                "condition_a": "tumor",
                "condition_b": "normal",
                "sample_ids_a": ["GSM111111", "GSM111112"],
                "sample_ids_b": ["GSM111113"]
            }
        ],
        "expected_outputs": [
            "Gene expression counts matrix",
            "Differential expression results (tumor vs normal)",
            "MultiQC quality control report",
            "Gene set enrichment analysis"
        ],
        "estimated_runtime": "4-6 hours",
        "analysis_parameters": {
            "genome_build": "GRCh38",
            "key_settings": {
                "aligner": "star_salmon",
                "quantification": "salmon"
            }
        }
    }"""
