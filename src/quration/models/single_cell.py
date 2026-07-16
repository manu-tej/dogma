"""Single-cell RNA-seq data models for MVP."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from quration.models.metadata import (
    CuratedDataset,
    OntologyTerm,
    QualityMetrics,
    SampleCharacteristics,
)


class MarkerGene(BaseModel):
    """Marker gene for a cell population."""

    gene_symbol: str = Field(..., description="Gene symbol (e.g., CD3D)")
    gene_id: str | None = Field(None, description="Gene ID (e.g., ENSG00000167286)")
    log2_fold_change: float | None = Field(None, description="Log2 fold change")
    p_value: float | None = Field(None, ge=0.0, le=1.0, description="P-value")
    adjusted_p_value: float | None = Field(
        None, ge=0.0, le=1.0, description="Adjusted p-value"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "gene_symbol": "CD3D",
                "gene_id": "ENSG00000167286",
                "log2_fold_change": 2.5,
                "p_value": 1e-50,
                "adjusted_p_value": 1e-45,
            }
        }


class CellPopulation(BaseModel):
    """Represents a cluster or cell population."""

    population_id: str = Field(..., description="Unique population identifier")
    population_name: str = Field(..., description="Population name/label")
    cell_type: OntologyTerm | None = Field(
        None, description="Annotated cell type (Cell Ontology)"
    )
    n_cells: int = Field(..., ge=0, description="Number of cells in population")
    marker_genes: list[MarkerGene] = Field(
        default_factory=list, description="Top marker genes"
    )
    mean_genes_detected: float | None = Field(
        None, description="Mean number of genes detected per cell"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "population_id": "0",
                "population_name": "T cells",
                "cell_type": {
                    "term": "T cell",
                    "ontology_id": "CL:0000084",
                    "ontology_name": "CL",
                },
                "n_cells": 5000,
                "marker_genes": [
                    {"gene_symbol": "CD3D", "log2_fold_change": 2.5},
                    {"gene_symbol": "CD3E", "log2_fold_change": 2.3},
                ],
                "mean_genes_detected": 1500.0,
            }
        }


class SingleCellSample(SampleCharacteristics):
    """Extended sample characteristics for single-cell data."""

    n_cells: int = Field(..., ge=0, description="Number of cells in sample")
    n_genes: int = Field(..., ge=0, description="Number of genes measured")
    assay_type: str | None = Field(
        None, description="Assay type (e.g., '10x 3' v3', 'Smart-seq2')"
    )
    cell_populations: list[CellPopulation] = Field(
        default_factory=list, description="Cell populations identified"
    )
    clustering_method: str | None = Field(
        None, description="Clustering algorithm (e.g., 'leiden', 'louvain')"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "sample_id": "GSM123456",
                "sample_name": "Patient 1 PBMC",
                "n_cells": 10000,
                "n_genes": 20000,
                "assay_type": "10x 3' v3",
                "organism": {
                    "term": "Homo sapiens",
                    "ontology_id": "NCBITaxon:9606",
                },
                "tissue": {"term": "blood", "ontology_id": "UBERON:0000178"},
            }
        }


class SingleCellDataset(CuratedDataset):
    """Extended dataset model for single-cell data."""

    # Override samples type
    samples: list[SingleCellSample] = Field(..., description="Single-cell samples")

    total_cells: int = Field(..., ge=0, description="Total cells across all samples")
    total_genes: int = Field(..., ge=0, description="Total unique genes measured")
    cell_type_summary: dict[str, int] = Field(
        default_factory=dict, description="Cell type -> count mapping"
    )

    # Data availability flags
    has_raw_counts: bool = Field(False, description="Whether raw count data available")
    has_embeddings: bool = Field(False, description="Whether UMAP/t-SNE available")
    has_clusters: bool = Field(False, description="Whether cluster assignments available")
    has_marker_genes: bool = Field(False, description="Whether marker genes available")

    # File references
    h5ad_url: str | None = Field(None, description="URL to H5AD file")

    class Config:
        json_schema_extra = {
            "example": {
                "dataset_id": "GSE123456",
                "title": "Single-cell RNA-seq of tumor microenvironment",
                "total_cells": 50000,
                "total_genes": 20000,
                "cell_type_summary": {
                    "T cell": 15000,
                    "B cell": 5000,
                    "Macrophage": 10000,
                },
                "has_raw_counts": True,
                "has_embeddings": True,
                "has_clusters": True,
                "has_marker_genes": True,
            }
        }
