"""
Configuration generator for nf-core pipelines.

This module generates pipeline configurations and samplesheets from
curated metadata and analysis plans.
"""

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import (
    AnalysisPlan,
    ComputeEnvironment,
    FetchNGSParameters,
    PipelineConfig,
    PipelineType,
    RNASeqParameters,
    SampleSheet,
)

logger = logging.getLogger(__name__)


class ConfigGenerator:
    """Generate nf-core pipeline configurations from analysis plans."""

    def __init__(self, compute_env: ComputeEnvironment = ComputeEnvironment.LOCAL):
        """
        Initialize the config generator.

        Args:
            compute_env: Default compute environment
        """
        self.compute_env = compute_env

    def generate_fetchngs_config(
        self,
        sra_ids: List[str],
        output_dir: Path,
        download_method: str = "ftp",
        for_pipeline: Optional[str] = None,
    ) -> PipelineConfig:
        """
        Generate configuration for nf-core/fetchngs pipeline.

        Args:
            sra_ids: List of SRA accession IDs
            output_dir: Output directory
            download_method: Download method (ftp, sratools, aspera)
            for_pipeline: Format output for specific nf-core pipeline (e.g., 'rnaseq')

        Returns:
            PipelineConfig for fetchngs
        """
        # Create input IDs file
        ids_file = output_dir / "sra_ids.csv"
        ids_file.parent.mkdir(parents=True, exist_ok=True)

        with open(ids_file, "w", newline="") as f:
            writer = csv.writer(f)
            for sra_id in sra_ids:
                writer.writerow([sra_id])

        logger.info(f"Created SRA IDs file: {ids_file} with {len(sra_ids)} IDs")

        # Create parameters
        params = FetchNGSParameters(
            input=str(ids_file),
            outdir=str(output_dir / "fetchngs_output"),
            download_method=download_method,
            nf_core_pipeline=for_pipeline,
        )

        # Build config
        config = PipelineConfig(
            pipeline_type=PipelineType.FETCHNGS,
            parameters=params,
            compute_env=self.compute_env,
            profile=self._get_default_profiles(),
        )

        return config

    def generate_rnaseq_config(
        self,
        plan: AnalysisPlan,
        fastq_dir: Path,
        output_dir: Path,
        curated_dataset: Dict[str, Any],
        aligner: str = "star_salmon",
    ) -> PipelineConfig:
        """
        Generate configuration for nf-core/rnaseq pipeline.

        Args:
            plan: Analysis plan
            fastq_dir: Directory containing FASTQ files
            output_dir: Output directory
            curated_dataset: Curated dataset metadata
            aligner: Alignment tool to use

        Returns:
            PipelineConfig for rnaseq
        """
        # Generate samplesheet
        samplesheet_path = output_dir / "samplesheet.csv"
        samplesheet_path.parent.mkdir(parents=True, exist_ok=True)

        self._create_rnaseq_samplesheet(
            curated_dataset=curated_dataset,
            fastq_dir=fastq_dir,
            output_path=samplesheet_path,
            is_paired_end=plan.has_paired_end,
        )

        logger.info(f"Created samplesheet: {samplesheet_path}")

        # Create parameters
        params = RNASeqParameters(
            input=str(samplesheet_path),
            outdir=str(output_dir / "rnaseq_output"),
            genome=plan.suggested_genome.igenomes_ref,
            aligner=aligner,
            comparisons=plan.comparison_groups if plan.comparison_groups else None,
        )

        # Build config
        config = PipelineConfig(
            pipeline_type=PipelineType.RNASEQ,
            parameters=params,
            compute_env=self.compute_env,
            profile=self._get_default_profiles(),
        )

        return config

    def _create_rnaseq_samplesheet(
        self,
        curated_dataset: Dict[str, Any],
        fastq_dir: Path,
        output_path: Path,
        is_paired_end: bool = True,
    ) -> None:
        """
        Create a samplesheet for nf-core/rnaseq.

        Format:
        sample,fastq_1,fastq_2,strandedness
        """
        samples = curated_dataset.get("samples", [])

        with open(output_path, "w", newline="") as f:
            if is_paired_end:
                fieldnames = ["sample", "fastq_1", "fastq_2", "strandedness"]
            else:
                fieldnames = ["sample", "fastq_1", "strandedness"]

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for sample in samples:
                sample_id = sample.get("sample_id", sample.get("sample_name", "unknown"))

                # Look for FASTQ files
                fastq_1 = self._find_fastq_file(fastq_dir, sample_id, "_1")
                fastq_2 = None
                if is_paired_end:
                    fastq_2 = self._find_fastq_file(fastq_dir, sample_id, "_2")

                row = {
                    "sample": sample_id,
                    "fastq_1": str(fastq_1) if fastq_1 else "",
                    "strandedness": "auto",  # Let nf-core/rnaseq auto-detect
                }

                if is_paired_end:
                    row["fastq_2"] = str(fastq_2) if fastq_2 else ""

                writer.writerow(row)

    def _find_fastq_file(
        self, fastq_dir: Path, sample_id: str, suffix: str = ""
    ) -> Optional[Path]:
        """
        Find FASTQ file for a sample.

        Args:
            fastq_dir: Directory containing FASTQ files
            sample_id: Sample identifier
            suffix: Suffix to append (e.g., '_1', '_2')

        Returns:
            Path to FASTQ file if found
        """
        # Try different naming patterns
        patterns = [
            f"{sample_id}{suffix}.fastq.gz",
            f"{sample_id}{suffix}.fq.gz",
            f"{sample_id}{suffix}.fastq",
            f"{sample_id}{suffix}.fq",
        ]

        for pattern in patterns:
            file_path = fastq_dir / pattern
            if file_path.exists():
                return file_path

        # Also check in subdirectories
        for pattern in patterns:
            matches = list(fastq_dir.glob(f"**/{pattern}"))
            if matches:
                return matches[0]

        logger.warning(f"FASTQ file not found for {sample_id}{suffix}")
        return None

    def _get_default_profiles(self) -> List[str]:
        """Get default Nextflow profiles based on compute environment."""
        if self.compute_env == ComputeEnvironment.LOCAL:
            return ["docker"]
        elif self.compute_env == ComputeEnvironment.AWS:
            return ["awsbatch"]
        elif self.compute_env == ComputeEnvironment.GCP:
            return ["google"]
        elif self.compute_env == ComputeEnvironment.HPC_SLURM:
            return ["slurm"]
        elif self.compute_env == ComputeEnvironment.HPC_PBS:
            return ["pbs"]
        else:
            return ["standard"]

    def generate_contrast_file(
        self, plan: AnalysisPlan, output_path: Path
    ) -> None:
        """
        Generate a contrast/comparison file for differential analysis.

        Args:
            plan: Analysis plan with comparison groups
            output_path: Path to save contrast file
        """
        if not plan.comparison_groups:
            logger.warning("No comparison groups in plan, skipping contrast file")
            return

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["comparison", "condition_a", "condition_b"])

            for cg in plan.comparison_groups:
                writer.writerow([cg.name, cg.condition_a, cg.condition_b])

        logger.info(f"Created contrast file: {output_path}")

    def generate_custom_config(
        self,
        config: PipelineConfig,
        output_path: Path,
        custom_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Generate a custom Nextflow config file.

        Args:
            config: Pipeline configuration
            output_path: Path to save config file
            custom_params: Additional custom parameters
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write("// Custom Nextflow configuration\n\n")

            # Compute environment settings
            if config.compute_env == ComputeEnvironment.LOCAL:
                f.write("process {\n")
                f.write("  executor = 'local'\n")
                if config.max_cpus:
                    f.write(f"  cpus = {config.max_cpus}\n")
                if config.max_memory:
                    f.write(f"  memory = '{config.max_memory}'\n")
                f.write("}\n\n")

            # Docker settings
            if "docker" in config.profile:
                f.write("docker {\n")
                f.write("  enabled = true\n")
                f.write("  runOptions = '-u $(id -u):$(id -g)'\n")
                f.write("}\n\n")

            # Custom parameters
            if custom_params:
                f.write("params {\n")
                for key, value in custom_params.items():
                    if isinstance(value, str):
                        f.write(f"  {key} = '{value}'\n")
                    else:
                        f.write(f"  {key} = {value}\n")
                f.write("}\n\n")

        logger.info(f"Created custom config: {output_path}")
