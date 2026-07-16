"""Data models for proteomics dataset search functionality."""

from dataclasses import dataclass, field
from typing import Any, List, Literal, Optional

TherapyScope = Literal["specific", "broad"]


@dataclass
class ProteomicsQuerySpec:
    """Specification for a proteomics dataset query."""

    disease_terms: List[str]
    therapy_class: Optional[str]
    therapy_scope: TherapyScope
    targets_or_proteins: List[str]  # Protein names/IDs instead of genes
    study_keywords: List[str]
    must_have_quantification: bool = False  # Require quantitative proteomics data
    min_samples: Optional[int] = None
    organism: Optional[str] = "Homo sapiens"  # Default to human


@dataclass
class ProteomicsCondition:
    """Represents an experimental condition in proteomics study."""

    name: str
    n_replicates: Optional[int] = None
    treatment: Optional[str] = None


@dataclass
class ProteomicsExperimentalDesign:
    """Structured experimental design for proteomics."""

    conditions: Optional[List[ProteomicsCondition]]
    design_type: Optional[str]  # e.g., 'case-control', 'time-series', 'dose-response'
    instrument: Optional[str]  # e.g., 'Orbitrap Fusion Lumos'
    quantification_method: Optional[str]  # e.g., 'TMT', 'Label-free', 'SILAC'
    acquisition_strategy: Optional[str]  # e.g., 'DDA', 'DIA'
    notes: str
    is_partial: bool  # True if any major fields are missing/uncertain


@dataclass
class ProteomicsAssay:
    """Represents a single proteomics assay/run."""

    assay_id: str
    title: str
    sample_type: Optional[str] = None
    characteristics: dict[str, str] = field(default_factory=dict)
    raw_metadata: Any = None


@dataclass
class ProteomicsDatasetCandidate:
    """A proteomics dataset candidate matching the query."""

    # Required fields (no defaults)
    accession: str  # e.g., 'PXD012345'
    title: str
    description: str
    experimental_design: ProteomicsExperimentalDesign
    n_assays: Optional[int]
    organism: Optional[str]
    instruments: List[str]
    experiment_types: List[str]  # e.g., ['TMT labeling', 'Phosphoproteomics']
    quantification_methods: List[str]  # e.g., ['TMT11plex', 'Label-free']
    tissues: List[str]  # Sample characteristics
    diseases: List[str]
    cell_types: List[str]
    primary_doi: Optional[str]  # Publication info
    primary_pmid: Optional[str]
    has_protein_data: bool  # Data availability
    has_peptide_data: bool
    has_quantification_data: bool
    match_reasons: List[str]  # Matching
    raw_metadata: Any  # Metadata

    # Optional fields (with defaults)
    matched_queries: List[str] = field(default_factory=list)
    assays: List[ProteomicsAssay] = field(default_factory=list)
    assays_fetched: bool = False


@dataclass
class ProteomicsSearchResult:
    """Result from proteomics dataset search."""

    query_spec: ProteomicsQuerySpec
    candidates: List[ProteomicsDatasetCandidate]
    total_found: int
    search_time_seconds: float
    queries_executed: List[str] = field(default_factory=list)
    notes: str = ""
