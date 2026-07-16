"""Data models for GEO search functionality (from spec)."""

from dataclasses import dataclass, field
from typing import Any, List, Literal, Optional

TherapyScope = Literal["specific", "broad"]


@dataclass
class QuerySpec:
    """Specification for a bioinformatics/drug-discovery GEO query."""

    disease_terms: List[str]
    therapy_class: Optional[str]
    therapy_scope: TherapyScope
    targets_or_genes: List[str]
    study_keywords: List[str]
    must_have_clinical: bool
    min_samples: Optional[int] = None


@dataclass
class Condition:
    """Represents an experimental condition with sample count."""

    name: str
    n: Optional[int] = None


@dataclass
class ExperimentalDesign:
    """Structured experimental design information."""

    conditions: Optional[List[Condition]]
    design_type: Optional[str]  # e.g., 'case-control', 'time-series'
    tech: Optional[str]  # e.g., 'Illumina HiSeq'
    notes: str
    is_partial: bool  # True if any major fields are missing/uncertain


@dataclass
class GsmSample:
    """Represents a GSM (sample) record from GEO."""

    gsm_id: str
    title: str
    sample_type: Optional[str] = None
    characteristics: dict[str, str] = field(default_factory=dict)
    raw_metadata: Any = None


@dataclass
class GeoDatasetCandidate:
    """A GEO dataset candidate matching the query."""

    gse_id: str
    title: str
    summary: str
    experimental_design: ExperimentalDesign

    n_samples: Optional[int]
    organism: Optional[str]  # Organism (e.g., "Homo sapiens")
    platforms: List[str]
    primary_pmid: Optional[str]

    maybe_has_survival_data: bool
    match_reasons: List[str]

    raw_metadata: Any
    matched_queries: List[str] = field(default_factory=list)

    # GSM sample information for understanding dataset characteristics
    samples: List[GsmSample] = field(default_factory=list)
    samples_fetched: bool = False  # Whether GSM samples were fetched
