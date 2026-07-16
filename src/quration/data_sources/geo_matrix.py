"""GEO expression matrix downloader.

This module provides functionality to download and parse expression matrices
from GEO (Gene Expression Omnibus) including:
- Series Matrix files
- Supplementary data files
- Raw and processed expression data
"""

import gzip
import io
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from quration.config import GEOConfig, get_config
from quration.models.expression import (
    ExpressionMatrix,
    MatrixFormat,
    MatrixType,
    SupplementaryFile,
)

logger = logging.getLogger(__name__)


class GEOMatrixDownloader:
    """Downloads and parses expression matrices from GEO.

    This class handles:
    1. Downloading GEO Series Matrix files
    2. Downloading supplementary files
    3. Parsing various matrix formats
    4. Validating matrix data quality
    """

    # GEO FTP URLs
    GEO_FTP_BASE = "https://ftp.ncbi.nlm.nih.gov/geo"
    GEO_SERIES_MATRIX_BASE = "https://ftp.ncbi.nlm.nih.gov/geo/series"

    def __init__(self, config: Optional[GEOConfig] = None):
        """Initialize matrix downloader.

        Args:
            config: GEO configuration (uses global config if not provided)
        """
        if config is None:
            config = get_config().data_sources.geo

        self.config = config
        self._last_request_time = 0.0
        self._min_interval = 1.0 / self.config.get_effective_rate_limit()

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _download_file(
        self, url: str, output_path: Optional[Path] = None
    ) -> bytes:
        """Download file with retry logic.

        Args:
            url: URL to download
            output_path: Optional local path to save file

        Returns:
            File content as bytes
        """
        self._rate_limit()

        response = requests.get(url, timeout=60)
        response.raise_for_status()

        content = response.content

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(content)

        return content

    def _get_series_matrix_url(self, gse_id: str) -> str:
        """Construct URL for Series Matrix file.

        Args:
            gse_id: GSE accession (e.g., 'GSE123456')

        Returns:
            URL string
        """
        # Extract numeric part and create range directory
        # E.g., GSE123456 -> GSE123nnn
        match = re.match(r"GSE(\d+)", gse_id.upper())
        if not match:
            raise ValueError(f"Invalid GSE ID format: {gse_id}")

        gse_num = int(match.group(1))
        # GEO organizes series in 1000-number ranges
        range_dir = f"GSE{gse_num // 1000}nnn"

        # Construct URL
        url = f"{self.GEO_SERIES_MATRIX_BASE}/{range_dir}/{gse_id}/matrix/{gse_id}_series_matrix.txt.gz"
        return url

    def download_series_matrix(
        self, gse_id: str, output_dir: Optional[Path] = None
    ) -> Optional[ExpressionMatrix]:
        """Download and parse GEO Series Matrix file.

        Args:
            gse_id: GSE accession (e.g., 'GSE123456')
            output_dir: Optional directory to save downloaded file

        Returns:
            ExpressionMatrix object or None if download fails

        Example:
            >>> downloader = GEOMatrixDownloader()
            >>> matrix = downloader.download_series_matrix("GSE123456")
            >>> if matrix:
            ...     print(f"{matrix.n_genes} genes x {matrix.n_samples} samples")
        """
        url = self._get_series_matrix_url(gse_id)

        try:
            # Determine output path
            if output_dir:
                output_path = Path(output_dir) / f"{gse_id}_series_matrix.txt.gz"
            else:
                output_path = None

            # Download file
            content = self._download_file(url, output_path)

            # Decompress if gzipped
            if url.endswith(".gz"):
                content = gzip.decompress(content)

            # Parse Series Matrix file
            matrix = self._parse_series_matrix(content, gse_id, url)
            return matrix

        except Exception as e:
            logger.error(f"Failed to download Series Matrix for {gse_id}: {e}")
            return None

    def _parse_series_matrix(
        self, content: bytes, gse_id: str, source_url: str
    ) -> ExpressionMatrix:
        """Parse GEO Series Matrix file.

        Args:
            content: File content as bytes
            gse_id: GSE accession
            source_url: Source URL

        Returns:
            ExpressionMatrix object
        """
        # Decode content
        text = content.decode("utf-8", errors="ignore")

        # Series Matrix files have metadata at the top starting with !
        # and the actual matrix data at the bottom

        lines = text.split("\n")
        metadata: Dict[str, Any] = {}
        matrix_start_idx = 0
        matrix_end_idx = len(lines)

        # Parse metadata. The data table's header line is the (often quoted)
        # "ID_REF" row; it ends at "!series_matrix_table_end".
        for i, line in enumerate(lines):
            if line.startswith("!"):
                if line.startswith("!series_matrix_table_end"):
                    matrix_end_idx = i
                    break
                # Metadata line
                if "\t" in line:
                    parts = line.split("\t")
                    key = parts[0].strip("! ")
                    values = [v.strip('"') for v in parts[1:] if v.strip()]
                    metadata[key] = values
            elif line.lstrip('"').startswith("ID_REF"):
                # Start of matrix data (header row; may be quoted)
                matrix_start_idx = i

        # Parse matrix data (header row through table_end, exclusive)
        matrix_lines = lines[matrix_start_idx:matrix_end_idx]
        matrix_text = "\n".join(matrix_lines)

        # Read into DataFrame
        df = pd.read_csv(io.StringIO(matrix_text), sep="\t", index_col=0)

        # Extract gene IDs (row index) and sample IDs (columns)
        gene_ids = df.index.tolist()
        sample_ids = df.columns.tolist()

        # Determine matrix type (heuristic)
        matrix_type = self._infer_matrix_type(df)

        # The platform accession (GPLxxx) lets callers resolve probe ids to symbols.
        platform_values = metadata.get("Series_platform_id") or []
        platform_id = platform_values[0] if platform_values else None

        # Create ExpressionMatrix
        matrix = ExpressionMatrix(
            dataset_id=gse_id,
            source_database="GEO",
            matrix_type=matrix_type,
            matrix_data=df,
            gene_ids=gene_ids,
            sample_ids=sample_ids,
            platform_id=platform_id,
            source_url=source_url,
            original_format=MatrixFormat.SOFT,
        )

        # Compute quality metrics
        matrix.compute_quality_metrics()

        return matrix

    def _infer_matrix_type(self, df: pd.DataFrame) -> MatrixType:
        """Infer matrix type from data characteristics.

        Args:
            df: Expression matrix DataFrame

        Returns:
            MatrixType enum
        """
        # Get numeric values (excluding NaN)
        values = df.values.flatten()
        values = values[~pd.isna(values)]

        if len(values) == 0:
            return MatrixType.UNKNOWN

        min_val = values.min()
        max_val = values.max()
        has_negative = min_val < 0

        # Heuristics for matrix type inference
        if has_negative:
            if max_val < 20:
                return MatrixType.LOG2  # Likely log2 transformed
            else:
                return MatrixType.NORMALIZED
        else:
            if max_val < 1000:
                # Could be TPM/FPKM
                return MatrixType.NORMALIZED
            else:
                # Likely raw counts
                return MatrixType.RAW_COUNTS

    def list_supplementary_files(self, gse_id: str) -> List[SupplementaryFile]:
        """List supplementary files for a dataset.

        Args:
            gse_id: GSE accession

        Returns:
            List of SupplementaryFile objects

        Note:
            This queries the GEO website to find supplementary files.
            For the MVP, we'll return an empty list and implement this later.
        """
        # TODO: Implement supplementary file listing
        # This requires parsing the GEO dataset page
        return []

    def download_supplementary_file(
        self, file: SupplementaryFile, output_dir: Path
    ) -> Optional[Path]:
        """Download a supplementary file.

        Args:
            file: SupplementaryFile object with download URL
            output_dir: Directory to save file

        Returns:
            Path to downloaded file or None if failed
        """
        if not file.download_url:
            return None

        try:
            output_path = output_dir / file.filename
            self._download_file(file.download_url, output_path)
            file.local_path = output_path
            return output_path
        except Exception as e:
            logger.error(f"Failed to download {file.filename}: {e}")
            return None

    def parse_matrix_file(
        self,
        file_path: Path,
        dataset_id: str,
        matrix_type: MatrixType = MatrixType.UNKNOWN,
    ) -> Optional[ExpressionMatrix]:
        """Parse an expression matrix file.

        Args:
            file_path: Path to matrix file
            dataset_id: Dataset identifier
            matrix_type: Type of matrix (if known)

        Returns:
            ExpressionMatrix object or None if parsing fails

        Supports formats: .txt, .tsv, .csv, .xlsx, .gz
        """
        file_path = Path(file_path)

        try:
            # Handle gzipped files
            if file_path.suffix == ".gz":
                with gzip.open(file_path, "rt") as f:
                    content = f.read()
                # Get the actual format from the filename without .gz
                actual_suffix = file_path.stem.split(".")[-1]
            else:
                content = file_path.read_text()
                actual_suffix = file_path.suffix.lstrip(".")

            # Determine format
            if actual_suffix in ["txt", "tsv"]:
                df = pd.read_csv(io.StringIO(content), sep="\t", index_col=0)
                format_type = MatrixFormat.TSV
            elif actual_suffix == "csv":
                df = pd.read_csv(io.StringIO(content), index_col=0)
                format_type = MatrixFormat.CSV
            elif actual_suffix in ["xlsx", "xls"]:
                df = pd.read_excel(file_path, index_col=0)
                format_type = MatrixFormat.XLSX
            else:
                # Try tab-separated as default
                df = pd.read_csv(io.StringIO(content), sep="\t", index_col=0)
                format_type = MatrixFormat.TXT

            # Extract IDs
            gene_ids = df.index.astype(str).tolist()
            sample_ids = df.columns.astype(str).tolist()

            # Infer matrix type if unknown
            if matrix_type == MatrixType.UNKNOWN:
                matrix_type = self._infer_matrix_type(df)

            # Create matrix
            matrix = ExpressionMatrix(
                dataset_id=dataset_id,
                source_database="GEO",
                matrix_type=matrix_type,
                matrix_data=df,
                gene_ids=gene_ids,
                sample_ids=sample_ids,
                source_file=str(file_path),
                original_format=format_type,
            )

            # Compute quality metrics
            matrix.compute_quality_metrics()

            return matrix

        except Exception as e:
            logger.error(f"Failed to parse matrix file {file_path}: {e}")
            return None

    def validate_matrix(self, matrix: ExpressionMatrix) -> List[str]:
        """Validate expression matrix.

        Args:
            matrix: ExpressionMatrix to validate

        Returns:
            List of validation errors (empty if valid)
        """
        return matrix.validate()
