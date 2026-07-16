"""Expression matrix data models.

This module defines data models for representing gene expression matrices
downloaded from various sources (GEO, ENA, etc.).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


class MatrixType(str, Enum):
    """Types of expression matrices."""

    RAW_COUNTS = "raw_counts"  # Raw read counts
    NORMALIZED = "normalized"  # Normalized expression
    TPM = "tpm"  # Transcripts Per Million
    FPKM = "fpkm"  # Fragments Per Kilobase Million
    RPKM = "rpkm"  # Reads Per Kilobase Million
    LOG2 = "log2"  # Log2 transformed
    UNKNOWN = "unknown"  # Unknown normalization


class MatrixFormat(str, Enum):
    """File formats for expression matrices."""

    TSV = "tsv"  # Tab-separated values
    CSV = "csv"  # Comma-separated values
    TXT = "txt"  # Generic text
    XLSX = "xlsx"  # Excel
    GCT = "gct"  # Gene Cluster Text (Broad Institute)
    H5 = "h5"  # HDF5 format
    SOFT = "soft"  # GEO SOFT format


@dataclass
class MatrixQualityMetrics:
    """Quality metrics for expression matrices."""

    n_genes: int
    n_samples: int
    completeness: float = 0.0  # Proportion of non-missing values (0-1)
    has_negative_values: bool = False
    value_range: Tuple[float, float] = (0.0, 0.0)  # (min, max)
    suspected_log_transformed: bool = False
    mean_expression: float = 0.0
    median_expression: float = 0.0
    zero_count_proportion: float = 0.0  # Proportion of zero values

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "n_genes": self.n_genes,
            "n_samples": self.n_samples,
            "completeness": self.completeness,
            "has_negative_values": self.has_negative_values,
            "value_range": {
                "min": self.value_range[0],
                "max": self.value_range[1],
            },
            "suspected_log_transformed": self.suspected_log_transformed,
            "mean_expression": self.mean_expression,
            "median_expression": self.median_expression,
            "zero_count_proportion": self.zero_count_proportion,
        }


@dataclass
class ExpressionMatrix:
    """Represents a gene expression matrix.

    This class holds expression data along with metadata about genes and samples.
    """

    # Identifiers
    dataset_id: str
    source_database: str  # e.g., "GEO", "ENA"

    # Matrix data
    matrix_type: MatrixType
    matrix_data: pd.DataFrame  # Genes (rows) x Samples (columns)

    # Metadata
    gene_ids: List[str]
    sample_ids: List[str]
    gene_annotations: Optional[pd.DataFrame] = None  # Gene metadata
    sample_annotations: Optional[pd.DataFrame] = None  # Sample metadata
    platform_id: Optional[str] = None  # GEO platform accession (e.g. "GPL570")

    # Processing info
    normalization_method: Optional[str] = None
    processing_notes: str = ""

    # Quality
    quality_metrics: Optional[MatrixQualityMetrics] = None

    # Provenance
    source_file: Optional[str] = None
    source_url: Optional[str] = None
    download_date: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # File format
    original_format: Optional[MatrixFormat] = None

    def __post_init__(self):
        """Validate data after initialization."""
        errors = []

        # Validate dataset_id
        if not self.dataset_id or not self.dataset_id.strip():
            errors.append("dataset_id cannot be empty")

        # Validate gene_ids and sample_ids are not empty
        if not self.gene_ids:
            errors.append("gene_ids cannot be empty")
        if not self.sample_ids:
            errors.append("sample_ids cannot be empty")

        # Check for duplicate IDs
        if len(self.gene_ids) != len(set(self.gene_ids)):
            errors.append("gene_ids contains duplicate entries")
        if len(self.sample_ids) != len(set(self.sample_ids)):
            errors.append("sample_ids contains duplicate entries")

        # Validate DataFrame dimensions match ID lists
        if self.matrix_data.shape[0] != len(self.gene_ids):
            errors.append(
                f"matrix_data has {self.matrix_data.shape[0]} rows but gene_ids has {len(self.gene_ids)} entries"
            )
        if self.matrix_data.shape[1] != len(self.sample_ids):
            errors.append(
                f"matrix_data has {self.matrix_data.shape[1]} columns but sample_ids has {len(self.sample_ids)} entries"
            )

        # Validate matrix contains numeric data
        if not all(pd.api.types.is_numeric_dtype(self.matrix_data[col]) for col in self.matrix_data.columns):
            errors.append("matrix_data must contain only numeric data")

        if errors:
            raise ValueError(f"ExpressionMatrix validation failed: {'; '.join(errors)}")

    @property
    def n_genes(self) -> int:
        """Number of genes."""
        return len(self.gene_ids)

    @property
    def n_samples(self) -> int:
        """Number of samples."""
        return len(self.sample_ids)

    @property
    def shape(self) -> Tuple[int, int]:
        """Matrix shape (genes, samples)."""
        return (self.n_genes, self.n_samples)

    def validate(self) -> List[str]:
        """Validate matrix consistency.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check for empty matrix
        if self.matrix_data.shape[0] == 0 or self.matrix_data.shape[1] == 0:
            errors.append("Matrix is empty")
            return errors  # No point checking further

        # Check matrix dimensions
        if self.matrix_data.shape[0] != self.n_genes:
            errors.append(
                f"Matrix has {self.matrix_data.shape[0]} rows but {self.n_genes} gene IDs"
            )

        if self.matrix_data.shape[1] != self.n_samples:
            errors.append(
                f"Matrix has {self.matrix_data.shape[1]} columns but {self.n_samples} sample IDs"
            )

        # Use numpy for efficient validation
        matrix_values = self.matrix_data.values

        # Check for missing data using numpy
        nan_mask = np.isnan(matrix_values)
        if nan_mask.any():
            null_count = nan_mask.sum()
            total = self.n_genes * self.n_samples
            null_pct = (null_count / total) * 100
            errors.append(f"Matrix contains {null_count} missing values ({null_pct:.2f}%)")

        # Check for all-NaN values
        if nan_mask.all():
            errors.append("Matrix contains only NaN values")

        # Check for infinite values using numpy
        if np.isinf(matrix_values).any():
            inf_count = np.isinf(matrix_values).sum()
            errors.append(f"Matrix contains {inf_count} infinite values")

        # Check data type consistency
        if not np.issubdtype(matrix_values.dtype, np.number):
            errors.append(f"Matrix has non-numeric dtype: {matrix_values.dtype}")

        # Check gene annotations if present
        if self.gene_annotations is not None:
            if len(self.gene_annotations) != self.n_genes:
                errors.append(
                    f"Gene annotations has {len(self.gene_annotations)} rows "
                    f"but {self.n_genes} genes"
                )

        # Check sample annotations if present
        if self.sample_annotations is not None:
            if len(self.sample_annotations) != self.n_samples:
                errors.append(
                    f"Sample annotations has {len(self.sample_annotations)} rows "
                    f"but {self.n_samples} samples"
                )

        return errors

    def compute_quality_metrics(self) -> MatrixQualityMetrics:
        """Compute quality metrics for the matrix.

        Uses numpy operations directly to minimize memory usage.
        For a 20K x 1K matrix (float64), this avoids creating 4x memory copies.

        Returns:
            MatrixQualityMetrics object
        """
        # Get direct reference to numpy array (no copy)
        matrix_values = self.matrix_data.values
        total_elements = matrix_values.size

        # Compute metrics using numpy operations (no copies)
        nan_mask = np.isnan(matrix_values)
        nan_count = np.count_nonzero(nan_mask)
        completeness = 1.0 - (nan_count / total_elements)

        # Check for negative values using numpy
        has_negative = np.any(matrix_values < 0)

        # Compute statistics on valid (non-NaN) values
        if nan_count < total_elements:
            # Use nanmin/nanmax/nanmean/nanmedian to avoid creating filtered array
            min_val = float(np.nanmin(matrix_values))
            max_val = float(np.nanmax(matrix_values))
            mean_expr = float(np.nanmean(matrix_values))
            median_expr = float(np.nanmedian(matrix_values))

            # Count zeros efficiently
            zero_count = np.count_nonzero(matrix_values == 0)
            valid_count = total_elements - nan_count
            zero_prop = zero_count / valid_count

            # Heuristic: if max < 100 and has negatives, likely log-transformed
            suspected_log = has_negative or (max_val < 100 and min_val < 0)
            value_range = (min_val, max_val)
        else:
            value_range = (0.0, 0.0)
            mean_expr = 0.0
            median_expr = 0.0
            zero_prop = 0.0
            suspected_log = False

        metrics = MatrixQualityMetrics(
            n_genes=self.n_genes,
            n_samples=self.n_samples,
            completeness=completeness,
            has_negative_values=bool(has_negative),
            value_range=value_range,
            suspected_log_transformed=suspected_log,
            mean_expression=mean_expr,
            median_expression=median_expr,
            zero_count_proportion=zero_prop,
        )

        self.quality_metrics = metrics
        return metrics

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding large matrix data).

        Returns:
            Dictionary representation
        """
        return {
            "dataset_id": self.dataset_id,
            "source_database": self.source_database,
            "matrix_type": self.matrix_type.value,
            "shape": {"genes": self.n_genes, "samples": self.n_samples},
            "normalization_method": self.normalization_method,
            "processing_notes": self.processing_notes,
            "quality_metrics": (
                self.quality_metrics.to_dict() if self.quality_metrics else None
            ),
            "source_file": self.source_file,
            "source_url": self.source_url,
            "download_date": self.download_date.isoformat(),
            "original_format": self.original_format.value if self.original_format else None,
        }

    def save_to_file(self, output_path: Path, include_annotations: bool = True) -> None:
        """Save expression matrix to file.

        Args:
            output_path: Output file path
            include_annotations: Whether to include gene/sample annotations

        Raises:
            ValueError: If file format is unsupported
            PermissionError: If lacking write permissions
            OSError: If directory doesn't exist or disk is full
        """
        output_path = Path(output_path)

        # Validate output path
        if not output_path.suffix:
            raise ValueError("Output path must have a file extension")

        # Check parent directory exists
        if not output_path.parent.exists():
            raise OSError(f"Output directory does not exist: {output_path.parent}")

        # Check if we have write permission
        if output_path.exists() and not output_path.parent.is_dir():
            raise OSError(f"Parent path is not a directory: {output_path.parent}")

        # Check for supported format first
        if output_path.suffix not in [".parquet", ".csv", ".tsv", ".txt", ".xlsx"]:
            raise ValueError(f"Unsupported file format: {output_path.suffix}")

        try:
            if output_path.suffix == ".parquet":
                # Save as Parquet
                self.matrix_data.to_parquet(output_path)
            elif output_path.suffix == ".csv":
                self.matrix_data.to_csv(output_path)
            elif output_path.suffix in [".tsv", ".txt"]:
                self.matrix_data.to_csv(output_path, sep="\t")
            elif output_path.suffix == ".xlsx":
                with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                    self.matrix_data.to_excel(writer, sheet_name="Expression")
                    if include_annotations and self.gene_annotations is not None:
                        self.gene_annotations.to_excel(writer, sheet_name="Gene_Annotations")
                    if include_annotations and self.sample_annotations is not None:
                        self.sample_annotations.to_excel(
                            writer, sheet_name="Sample_Annotations"
                        )

        except PermissionError as e:
            raise PermissionError(f"Permission denied writing to {output_path}: {e}") from e
        except OSError as e:
            if "No space left on device" in str(e):
                raise OSError(f"No space left on device when writing to {output_path}") from e
            raise OSError(f"Error writing to {output_path}: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error saving file to {output_path}: {e}") from e


class ExpressionMatrixModel(BaseModel):
    """Pydantic model for ExpressionMatrix (for API responses)."""

    dataset_id: str
    source_database: str
    matrix_type: str
    shape: Dict[str, int]
    normalization_method: Optional[str] = None
    processing_notes: str = ""
    quality_metrics: Optional[Dict[str, Any]] = None
    source_file: Optional[str] = None
    source_url: Optional[str] = None
    download_date: str
    original_format: Optional[str] = None

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "dataset_id": "GSE123456",
                "source_database": "GEO",
                "matrix_type": "normalized",
                "shape": {"genes": 20000, "samples": 50},
                "normalization_method": "DESeq2",
                "quality_metrics": {
                    "n_genes": 20000,
                    "n_samples": 50,
                    "completeness": 0.98,
                    "has_negative_values": True,
                    "value_range": {"min": -5.2, "max": 10.8},
                    "suspected_log_transformed": True,
                },
            }
        }


@dataclass
class SupplementaryFile:
    """Represents a supplementary file from a dataset."""

    file_id: str
    filename: str
    file_type: str  # e.g., "expression_matrix", "metadata", "raw_data"
    file_size: Optional[int] = None  # Size in bytes
    download_url: Optional[str] = None
    local_path: Optional[Path] = None
    description: Optional[str] = None
    format: Optional[MatrixFormat] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "download_url": self.download_url,
            "local_path": str(self.local_path) if self.local_path else None,
            "description": self.description,
            "format": self.format.value if self.format else None,
        }
