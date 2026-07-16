"""Metadata models for NGS datasets."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class SequencingPlatform(str, Enum):
    """Common sequencing platforms."""

    ILLUMINA_HISEQ = "Illumina HiSeq"
    ILLUMINA_NEXTSEQ = "Illumina NextSeq"
    ILLUMINA_NOVASEQ = "Illumina NovaSeq"
    ILLUMINA_MISEQ = "Illumina MiSeq"
    PACBIO = "PacBio"
    OXFORD_NANOPORE = "Oxford Nanopore"
    ION_TORRENT = "Ion Torrent"
    OTHER = "Other"


class MassSpecPlatform(str, Enum):
    """Common mass spectrometry platforms for proteomics."""

    # Orbitrap family
    ORBITRAP_FUSION = "Orbitrap Fusion"
    ORBITRAP_FUSION_LUMOS = "Orbitrap Fusion Lumos"
    ORBITRAP_ECLIPSE = "Orbitrap Eclipse"
    Q_EXACTIVE = "Q Exactive"
    Q_EXACTIVE_HF = "Q Exactive HF"
    Q_EXACTIVE_HF_X = "Q Exactive HF-X"
    Q_EXACTIVE_PLUS = "Q Exactive Plus"
    ORBITRAP_EXPLORIS = "Orbitrap Exploris"
    ORBITRAP_ASTRAL = "Orbitrap Astral"

    # Triple TOF
    TRIPLE_TOF_5600 = "TripleTOF 5600"
    TRIPLE_TOF_6600 = "TripleTOF 6600"

    # timsTOF
    TIMSTOF_PRO = "timsTOF Pro"
    TIMSTOF_FLEX = "timsTOF fleX"
    TIMSTOF_SCP = "timsTOF SCP"

    # Q-TOF
    QTOF = "Q-TOF"
    SYNAPT_G2 = "Synapt G2"

    # Triple Quadrupole
    TSQ_QUANTIVA = "TSQ Quantiva"
    TSQ_ALTIS = "TSQ Altis"
    QTRAP = "QTRAP"

    # MALDI
    MALDI_TOF = "MALDI-TOF"
    MALDI_TOF_TOF = "MALDI-TOF/TOF"

    # Other
    LTQ = "LTQ"
    LTQ_ORBITRAP = "LTQ Orbitrap"
    VELOS = "Velos"
    OTHER = "Other"


class ExperimentType(str, Enum):
    """Types of sequencing and proteomics experiments."""

    # Sequencing experiments
    RNA_SEQ = "RNA-Seq"
    CHIP_SEQ = "ChIP-Seq"
    ATAC_SEQ = "ATAC-Seq"
    WGS = "Whole Genome Sequencing"
    WES = "Whole Exome Sequencing"
    TARGETED = "Targeted Sequencing"
    METHYL_SEQ = "Methylation Sequencing"

    # Proteomics experiments
    LC_MSMS = "LC-MS/MS"
    SHOTGUN_PROTEOMICS = "Shotgun Proteomics"
    TMT_LABELING = "TMT Labeling"
    ITRAQ_LABELING = "iTRAQ Labeling"
    LABEL_FREE_QUANT = "Label-Free Quantification"
    SILAC = "SILAC"
    DIA_PROTEOMICS = "DIA Proteomics"
    DDA_PROTEOMICS = "DDA Proteomics"
    TARGETED_PROTEOMICS = "Targeted Proteomics (SRM/MRM/PRM)"
    TOP_DOWN_PROTEOMICS = "Top-Down Proteomics"
    BOTTOM_UP_PROTEOMICS = "Bottom-Up Proteomics"
    PTM_ANALYSIS = "PTM Analysis"
    PHOSPHOPROTEOMICS = "Phosphoproteomics"
    GLYCOPROTEOMICS = "Glycoproteomics"
    UBIQUITINOMICS = "Ubiquitinomics"
    ACETYLOMICS = "Acetylomics"

    OTHER = "Other"


class LibraryStrategy(str, Enum):
    """Library preparation strategies."""

    RNA_SEQ = "RNA-Seq"
    CHIP_SEQ = "ChIP-Seq"
    ATAC_SEQ = "ATAC-Seq"
    WGS = "WGS"
    WXS = "WXS"
    AMPLICON = "AMPLICON"
    BISULFITE_SEQ = "Bisulfite-Seq"
    OTHER = "OTHER"


class OntologyTerm(BaseModel):
    """Ontology term with ID and label."""

    term: str = Field(..., description="Ontology term label")
    ontology_id: str | None = Field(None, description="Ontology term ID (e.g., EFO:0000001)")
    ontology_name: str | None = Field(
        None, description="Ontology source (e.g., EFO, UBERON)"
    )
    iri: str | None = Field(None, description="Full IRI for the ontology term")
    confidence: float = Field(
        1.0, ge=0.0, le=1.0, description="Confidence in ontology mapping"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "term": "breast carcinoma",
                "ontology_id": "MONDO:0007254",
                "ontology_name": "MONDO",
                "iri": "http://purl.obolibrary.org/obo/MONDO_0007254",
                "confidence": 0.95,
            }
        }


class SampleCharacteristics(BaseModel):
    """Standardized sample characteristics."""

    # Core identifiers
    sample_id: str = Field(..., description="Sample identifier")
    sample_name: str | None = Field(None, description="Sample name/title")

    # Biological characteristics
    organism: OntologyTerm | None = Field(None, description="Species/organism")
    tissue: OntologyTerm | None = Field(None, description="Tissue type")
    cell_type: OntologyTerm | None = Field(None, description="Cell type")
    disease: OntologyTerm | None = Field(None, description="Disease state")
    development_stage: OntologyTerm | None = Field(None, description="Developmental stage")

    # Clinical/experimental metadata
    age: str | None = Field(None, description="Age or age range")
    sex: str | None = Field(None, description="Biological sex")
    genotype: OntologyTerm | None = Field(None, description="Genotype")
    treatment: OntologyTerm | None = Field(None, description="Treatment condition")

    # Additional characteristics
    additional_characteristics: dict[str, Any] = Field(
        default_factory=dict, description="Other sample attributes"
    )

    # Provenance
    original_characteristics: dict[str, str] = Field(
        default_factory=dict, description="Original raw characteristics from source"
    )
    curation_notes: list[str] = Field(
        default_factory=list, description="Notes from curation process"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "sample_id": "GSM123456",
                "sample_name": "Breast cancer patient 1, tumor tissue",
                "organism": {
                    "term": "Homo sapiens",
                    "ontology_id": "NCBITaxon:9606",
                    "ontology_name": "NCBITaxon",
                },
                "tissue": {
                    "term": "breast",
                    "ontology_id": "UBERON:0000310",
                    "ontology_name": "UBERON",
                },
                "disease": {
                    "term": "breast carcinoma",
                    "ontology_id": "MONDO:0007254",
                    "ontology_name": "MONDO",
                },
                "age": "45",
                "sex": "female",
            }
        }


class Platform(BaseModel):
    """Platform information for sequencing or mass spectrometry."""

    platform_type: SequencingPlatform | MassSpecPlatform | str = Field(
        ..., description="Platform type (sequencing or mass spec)"
    )
    platform_model: str | None = Field(None, description="Specific platform model")
    platform_id: str | None = Field(None, description="Platform ID from source database")
    platform_category: str | None = Field(
        None, description="Platform category (sequencing, mass_spectrometry, etc.)"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "platform_type": "Illumina NovaSeq",
                "platform_model": "NovaSeq 6000",
                "platform_id": "GPL24676",
            }
        }


class ExperimentalProtocol(BaseModel):
    """Experimental protocol details."""

    # Experiment type
    experiment_type: ExperimentType | str = Field(..., description="Type of experiment")
    library_strategy: LibraryStrategy | str = Field(
        ..., description="Library preparation strategy"
    )
    library_source: str | None = Field(None, description="Library source (e.g., TRANSCRIPTOMIC)")
    library_selection: str | None = Field(
        None, description="Library selection method (e.g., cDNA, PolyA)"
    )

    # Sequencing details
    read_length: str | None = Field(None, description="Read length (e.g., 2x150)")
    is_paired_end: bool | None = Field(None, description="Whether paired-end sequencing")

    # Protocol description
    extraction_protocol: str | None = Field(None, description="Nucleic acid extraction protocol")
    library_construction_protocol: str | None = Field(
        None, description="Library construction protocol"
    )
    sequencing_protocol: str | None = Field(None, description="Sequencing protocol")

    # Quality and validation
    protocol_validated: bool = Field(
        False, description="Whether protocol was validated by LLM"
    )
    protocol_issues: list[str] = Field(
        default_factory=list, description="Issues found in protocol"
    )
    protocol_completeness_score: float = Field(
        0.0, ge=0.0, le=1.0, description="Completeness score for protocol information"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "experiment_type": "RNA-Seq",
                "library_strategy": "RNA-Seq",
                "library_source": "TRANSCRIPTOMIC",
                "library_selection": "cDNA",
                "read_length": "2x150",
                "is_paired_end": True,
                "protocol_validated": True,
                "protocol_completeness_score": 0.9,
            }
        }


class Publication(BaseModel):
    """Publication information."""

    pmid: str | None = Field(None, description="PubMed ID")
    title: str | None = Field(None, description="Publication title")
    authors: list[str] = Field(default_factory=list, description="Authors")
    journal: str | None = Field(None, description="Journal name")
    year: int | None = Field(None, description="Publication year")
    doi: str | None = Field(None, description="DOI")
    url: HttpUrl | None = Field(None, description="Publication URL")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "pmid": "12345678",
                "title": "Transcriptomic analysis of breast cancer",
                "journal": "Nature",
                "year": 2023,
                "doi": "10.1038/nature12345",
            }
        }


class QualityMetrics(BaseModel):
    """Quality metrics for curated metadata."""

    # Completeness
    completeness_score: float = Field(
        0.0, ge=0.0, le=1.0, description="Overall completeness (0-1)"
    )
    missing_required_fields: list[str] = Field(
        default_factory=list, description="Required fields that are missing"
    )
    missing_recommended_fields: list[str] = Field(
        default_factory=list, description="Recommended fields that are missing"
    )

    # Consistency
    consistency_score: float = Field(
        1.0, ge=0.0, le=1.0, description="Internal consistency (0-1)"
    )
    consistency_issues: list[str] = Field(
        default_factory=list, description="Consistency problems found"
    )

    # Ontology compliance
    ontology_coverage: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Proportion of terms mapped to ontologies",
    )
    unmapped_terms: list[str] = Field(
        default_factory=list, description="Terms that couldn't be mapped to ontologies"
    )

    # Overall quality
    overall_quality_score: float = Field(
        0.0, ge=0.0, le=1.0, description="Overall quality score (0-1)"
    )
    quality_grade: str = Field(
        "U", description="Quality grade (A/B/C/D/F/U for ungraded)"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "completeness_score": 0.85,
                "consistency_score": 0.95,
                "ontology_coverage": 0.8,
                "overall_quality_score": 0.87,
                "quality_grade": "B",
            }
        }


class CuratedSample(BaseModel):
    """Complete curated sample metadata."""

    characteristics: SampleCharacteristics = Field(..., description="Sample characteristics")
    quality_metrics: QualityMetrics = Field(..., description="Quality metrics")

    # Provenance
    source_database: str = Field(..., description="Source database (e.g., GEO)")
    source_id: str = Field(..., description="Source identifier")
    curated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Curation timestamp"
    )
    curated_by: str = Field(default="quration-llm", description="Curation agent")
    curation_version: str = Field(default="0.1.0", description="Curation framework version")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "characteristics": {
                    "sample_id": "GSM123456",
                    "organism": {"term": "Homo sapiens", "ontology_id": "NCBITaxon:9606"},
                },
                "quality_metrics": {
                    "completeness_score": 0.85,
                    "overall_quality_score": 0.87,
                    "quality_grade": "B",
                },
                "source_database": "GEO",
                "source_id": "GSM123456",
            }
        }


class CuratedDataset(BaseModel):
    """Complete curated dataset with all samples."""

    # Dataset identifiers
    dataset_id: str = Field(..., description="Dataset identifier (e.g., GSE123456)")
    title: str = Field(..., description="Dataset title")
    description: str | None = Field(None, description="Dataset description")

    # Experimental details
    platform: Platform = Field(..., description="Sequencing platform")
    protocol: ExperimentalProtocol = Field(..., description="Experimental protocol")

    # Samples
    samples: list[CuratedSample] = Field(..., description="Curated samples")
    sample_count: int = Field(..., description="Number of samples")

    # Publication
    publication: Publication | None = Field(None, description="Associated publication")

    # Metadata
    submission_date: str | None = Field(None, description="Dataset submission date")
    last_update_date: str | None = Field(None, description="Last update date")
    release_date: str | None = Field(None, description="Public release date")

    # Summary statistics
    organism_summary: dict[str, int] = Field(
        default_factory=dict, description="Count of samples per organism"
    )
    tissue_summary: dict[str, int] = Field(
        default_factory=dict, description="Count of samples per tissue"
    )
    disease_summary: dict[str, int] = Field(
        default_factory=dict, description="Count of samples per disease"
    )

    # Overall quality
    dataset_quality_metrics: QualityMetrics = Field(
        ..., description="Overall dataset quality"
    )

    # Provenance
    source_database: str = Field(default="GEO", description="Source database")
    curated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Curation timestamp"
    )
    curation_version: str = Field(default="0.1.0", description="Curation framework version")

    # Raw metadata (optional)
    raw_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Original raw metadata from source database"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "dataset_id": "GSE123456",
                "title": "RNA-seq of breast cancer samples",
                "sample_count": 50,
                "organism_summary": {"Homo sapiens": 50},
                "tissue_summary": {"breast": 50},
            }
        }
