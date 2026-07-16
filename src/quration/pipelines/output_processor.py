"""
Output processor for Nextflow pipelines.

This module processes pipeline outputs and maps them to the quration
unified metadata schema.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models.nextflow import PipelineExecution, PipelineOutput, PipelineStatus
from ..models.metadata import (
    CuratedDataset,
    CuratedSample,
    ExperimentalProtocol,
    Platform,
    QualityMetrics,
    SampleCharacteristics,
)


logger = logging.getLogger(__name__)


class OutputProcessor:
    """
    Processes pipeline outputs and maps them to quration metadata schema.

    Handles:
    - Parsing MultiQC reports
    - Extracting summary statistics
    - Mapping outputs to metadata schema
    - Quality metric extraction
    """

    def __init__(self):
        """Initialize the output processor."""
        pass

    def process_execution_output(
        self,
        execution: PipelineExecution,
    ) -> PipelineOutput:
        """
        Process outputs from a completed pipeline execution.

        Args:
            execution: Pipeline execution record

        Returns:
            Structured pipeline output

        Raises:
            ValueError: If execution is not completed
        """
        if execution.status != PipelineStatus.COMPLETED:
            raise ValueError(
                f"Cannot process output for execution in status: {execution.status}"
            )

        output_dir = Path(execution.output_directory)
        if not output_dir.exists():
            raise ValueError(f"Output directory not found: {output_dir}")

        # Create output structure
        pipeline_output = PipelineOutput(
            execution_id=execution.execution_id,
            pipeline_id=execution.pipeline_id,
            status=execution.status,
            output_directory=str(output_dir),
        )

        # Categorize output files
        self._categorize_outputs(execution, pipeline_output)

        # Extract summary statistics
        pipeline_output.summary_stats = self._extract_summary_stats(execution, output_dir)

        # Map to metadata schema
        pipeline_output.mapped_metadata = self._map_to_metadata_schema(
            execution,
            pipeline_output,
        )

        return pipeline_output

    def _categorize_outputs(
        self,
        execution: PipelineExecution,
        pipeline_output: PipelineOutput,
    ):
        """
        Categorize output files into primary, QC, and intermediate.

        Args:
            execution: Pipeline execution
            pipeline_output: Output structure to populate
        """
        output_dir = Path(execution.output_directory)

        # Patterns for different file types
        primary_patterns = [
            "**/star_salmon/*.counts.tsv",  # RNA-seq gene counts
            "**/star_rsem/*.genes.results",  # RNA-seq RSEM
            "**/kallisto/**/*.tsv",  # Kallisto quantification
            "**/alevin/**/*.mtx",  # Single-cell counts
            "**/protein_groups.txt",  # Proteomics
            "**/peptides.txt",  # Proteomics
            "**/feature_matrix.csv",  # Metabolomics
            "**/identifications.tsv",  # Metabolomics
        ]

        qc_patterns = [
            "**/multiqc_report.html",
            "**/fastqc/**/*.html",
            "**/execution_report.html",
            "**/execution_timeline.html",
            "**/ptxqc_report.pdf",
        ]

        # Find primary outputs
        for pattern in primary_patterns:
            for file_path in output_dir.glob(pattern):
                pipeline_output.primary_outputs.append(str(file_path))

        # Find QC outputs
        for pattern in qc_patterns:
            for file_path in output_dir.glob(pattern):
                pipeline_output.qc_outputs.append(str(file_path))

        # Set report paths
        multiqc_reports = list(output_dir.glob("**/multiqc_report.html"))
        if multiqc_reports:
            pipeline_output.multiqc_report_path = str(multiqc_reports[0])

        exec_reports = list(output_dir.glob("**/execution_report.html"))
        if exec_reports:
            pipeline_output.execution_report_path = str(exec_reports[0])

        timeline_reports = list(output_dir.glob("**/execution_timeline.html"))
        if timeline_reports:
            pipeline_output.execution_timeline_path = str(timeline_reports[0])

        logger.info(
            f"Categorized outputs: {len(pipeline_output.primary_outputs)} primary, "
            f"{len(pipeline_output.qc_outputs)} QC"
        )

    def _extract_summary_stats(
        self,
        execution: PipelineExecution,
        output_dir: Path,
    ) -> Dict[str, Any]:
        """
        Extract summary statistics from pipeline outputs.

        Args:
            execution: Pipeline execution
            output_dir: Output directory path

        Returns:
            Dictionary of summary statistics
        """
        stats = {}

        # Try to parse MultiQC data
        multiqc_data_file = output_dir / "multiqc_data" / "multiqc_data.json"
        if multiqc_data_file.exists():
            try:
                with open(multiqc_data_file, "r") as f:
                    multiqc_data = json.load(f)
                    stats["multiqc"] = self._parse_multiqc_data(multiqc_data)
            except Exception as e:
                logger.warning(f"Failed to parse MultiQC data: {e}")

        # Pipeline-specific statistics
        if execution.pipeline_id == "nf-core/rnaseq":
            stats.update(self._extract_rnaseq_stats(output_dir))
        elif execution.pipeline_id == "nf-core/scrnaseq":
            stats.update(self._extract_scrnaseq_stats(output_dir))
        elif execution.pipeline_id == "nf-core/proteomicslfq":
            stats.update(self._extract_proteomics_stats(output_dir))
        elif execution.pipeline_id == "nf-core/metaboigniter":
            stats.update(self._extract_metabolomics_stats(output_dir))

        return stats

    def _parse_multiqc_data(self, multiqc_data: Dict) -> Dict[str, Any]:
        """
        Parse MultiQC JSON data for summary statistics.

        Args:
            multiqc_data: MultiQC data dictionary

        Returns:
            Extracted statistics
        """
        stats = {
            "total_samples": 0,
            "general_stats": {},
        }

        # Extract general statistics
        if "report_general_stats_data" in multiqc_data:
            general_stats = multiqc_data["report_general_stats_data"]
            stats["total_samples"] = len(general_stats)

            # Aggregate statistics across samples
            if general_stats:
                first_sample = next(iter(general_stats.values()))
                stats["metrics_available"] = list(first_sample.keys())

        return stats

    def _extract_rnaseq_stats(self, output_dir: Path) -> Dict[str, Any]:
        """Extract RNA-seq specific statistics."""
        stats = {}

        # Count gene count files
        count_files = list(output_dir.glob("**/star_salmon/*.counts.tsv"))
        stats["samples_processed"] = len(count_files)

        # Try to parse one count file for gene count
        if count_files:
            try:
                with open(count_files[0], "r") as f:
                    lines = f.readlines()
                    stats["genes_quantified"] = len(lines) - 1  # Minus header
            except:
                pass

        return stats

    def _extract_scrnaseq_stats(self, output_dir: Path) -> Dict[str, Any]:
        """Extract single-cell RNA-seq specific statistics."""
        stats = {}

        # Look for count matrices
        mtx_files = list(output_dir.glob("**/*.mtx"))
        stats["count_matrices"] = len(mtx_files)

        return stats

    def _extract_proteomics_stats(self, output_dir: Path) -> Dict[str, Any]:
        """Extract proteomics specific statistics."""
        stats = {}

        # Look for protein groups file
        protein_files = list(output_dir.glob("**/protein_groups.txt"))
        if protein_files:
            try:
                with open(protein_files[0], "r") as f:
                    lines = f.readlines()
                    stats["proteins_identified"] = len(lines) - 1
            except:
                pass

        return stats

    def _extract_metabolomics_stats(self, output_dir: Path) -> Dict[str, Any]:
        """Extract metabolomics specific statistics."""
        stats = {}

        # Look for feature matrix
        feature_files = list(output_dir.glob("**/feature_matrix.csv"))
        if feature_files:
            stats["feature_matrices"] = len(feature_files)

        return stats

    def _map_to_metadata_schema(
        self,
        execution: PipelineExecution,
        pipeline_output: PipelineOutput,
    ) -> Dict[str, Any]:
        """
        Map pipeline outputs to quration metadata schema.

        Args:
            execution: Pipeline execution
            pipeline_output: Pipeline output structure

        Returns:
            Mapped metadata dictionary
        """
        mapped = {
            "pipeline_info": {
                "pipeline_id": execution.pipeline_id,
                "pipeline_version": execution.pipeline_version,
                "execution_id": execution.execution_id,
                "execution_date": execution.completed_at.isoformat() if execution.completed_at else None,
            },
            "processing_info": {
                "aligner": execution.configuration.parameters.get("aligner"),
                "reference_genome": execution.configuration.parameters.get("genome"),
                "parameters": execution.configuration.parameters,
            },
        }

        # Add quality metrics if available
        if pipeline_output.summary_stats:
            mapped["quality_metrics"] = pipeline_output.summary_stats

        # Add file paths
        mapped["output_files"] = {
            "primary": pipeline_output.primary_outputs,
            "qc": pipeline_output.qc_outputs,
            "reports": {
                "multiqc": pipeline_output.multiqc_report_path,
                "execution": pipeline_output.execution_report_path,
                "timeline": pipeline_output.execution_timeline_path,
            },
        }

        return mapped

    def create_curated_dataset_from_pipeline(
        self,
        execution: PipelineExecution,
        pipeline_output: PipelineOutput,
        original_dataset_id: Optional[str] = None,
    ) -> Optional[CuratedDataset]:
        """
        Create a CuratedDataset object from pipeline output.

        This integrates pipeline results with the existing quration metadata schema.

        Args:
            execution: Pipeline execution
            pipeline_output: Processed pipeline output
            original_dataset_id: Original GEO dataset ID if applicable

        Returns:
            CuratedDataset or None if unable to create
        """
        # This would create a full CuratedDataset object
        # For now, return None as this requires more complex integration
        # with the existing curation workflow
        logger.info(
            f"CuratedDataset creation from pipeline output not yet implemented. "
            f"Use mapped_metadata for now."
        )
        return None

    def export_results_summary(
        self,
        pipeline_output: PipelineOutput,
        output_path: Path,
    ):
        """
        Export a summary of pipeline results to JSON.

        Args:
            pipeline_output: Pipeline output
            output_path: Path to save summary
        """
        summary = {
            "execution_id": pipeline_output.execution_id,
            "pipeline_id": pipeline_output.pipeline_id,
            "status": pipeline_output.status.value,
            "output_directory": pipeline_output.output_directory,
            "primary_outputs_count": len(pipeline_output.primary_outputs),
            "qc_outputs_count": len(pipeline_output.qc_outputs),
            "summary_statistics": pipeline_output.summary_stats,
            "mapped_metadata": pipeline_output.mapped_metadata,
        }

        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"Exported results summary to {output_path}")
