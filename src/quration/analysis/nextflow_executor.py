"""
Nextflow pipeline executor.

This module provides a wrapper for executing Nextflow pipelines with
proper configuration, monitoring, and error handling.
"""

import logging
import shlex
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .models import (
    ComputeEnvironment,
    ExecutionResult,
    ExecutionStatus,
    PipelineConfig,
    PipelineType,
)

logger = logging.getLogger(__name__)


class NextflowExecutor:
    """Execute and monitor Nextflow pipelines."""

    def __init__(
        self,
        nextflow_bin: str = "nextflow",
        work_dir: Optional[Path] = None,
    ):
        """
        Initialize the Nextflow executor.

        Args:
            nextflow_bin: Path to nextflow executable
            work_dir: Default work directory for Nextflow
        """
        self.nextflow_bin = nextflow_bin
        self.work_dir = work_dir or Path.cwd() / "work"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        # The Nextflow binary is verified lazily on first pipeline run, not at
        # construction — so callers that only build an executor (or a DataFetcher) don't
        # need Nextflow installed.
        self._nextflow_verified = False

    def _check_nextflow_installation(self) -> None:
        """Check if Nextflow is installed and accessible (verified once, then cached)."""
        if self._nextflow_verified:
            return
        try:
            result = subprocess.run(
                [self.nextflow_bin, "-version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.info(f"Nextflow version: {result.stdout.strip()}")
                self._nextflow_verified = True
            else:
                raise RuntimeError(f"Nextflow check failed: {result.stderr}")
        except FileNotFoundError:
            raise RuntimeError(
                f"Nextflow not found at {self.nextflow_bin}. "
                "Please install Nextflow: https://www.nextflow.io/docs/latest/getstarted.html"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Nextflow version check timed out")

    def execute_pipeline(
        self,
        config: PipelineConfig,
        dataset_id: str,
        wait: bool = True,
        log_file: Optional[Path] = None,
    ) -> ExecutionResult:
        """
        Execute an nf-core pipeline.

        Args:
            config: Pipeline configuration
            dataset_id: Dataset identifier
            wait: Whether to wait for completion
            log_file: Path to log file (optional)

        Returns:
            ExecutionResult with execution details
        """
        # Verify Nextflow is available before actually running anything.
        self._check_nextflow_installation()
        started_at = datetime.now()
        logger.info(
            f"Executing {config.pipeline_type.value} pipeline for dataset {dataset_id}"
        )

        # Build Nextflow command
        cmd = self._build_nextflow_command(config)

        # Set up logging
        if not log_file:
            log_dir = Path(config.parameters.outdir) / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"nextflow_{config.pipeline_type.value}_{int(time.time())}.log"

        # Execute command
        try:
            logger.info(f"Running command: {' '.join(cmd)}")
            logger.info(f"Logging to: {log_file}")

            with open(log_file, "w") as log_f:
                process = subprocess.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

                if wait:
                    exit_code = process.wait()
                    completed_at = datetime.now()

                    if exit_code == 0:
                        status = ExecutionStatus.COMPLETED
                        logger.info(
                            f"Pipeline completed successfully for {dataset_id}"
                        )
                    else:
                        status = ExecutionStatus.FAILED
                        logger.error(
                            f"Pipeline failed with exit code {exit_code}"
                        )
                else:
                    status = ExecutionStatus.RUNNING
                    completed_at = None
                    exit_code = None

        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            status = ExecutionStatus.FAILED
            completed_at = datetime.now()
            exit_code = -1

        # Get Nextflow version
        nextflow_version = self._get_nextflow_version()

        # Build result
        result = ExecutionResult(
            pipeline_type=config.pipeline_type,
            dataset_id=dataset_id,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            work_dir=str(config.work_dir or self.work_dir),
            output_dir=config.parameters.outdir,
            log_file=str(log_file) if log_file else None,
            exit_code=exit_code,
            nextflow_version=nextflow_version,
            pipeline_version=config.pipeline_version,
        )

        return result

    def _build_nextflow_command(self, config: PipelineConfig) -> List[str]:
        """Build the Nextflow command from configuration."""
        cmd = [self.nextflow_bin, "run"]

        # Pipeline name and version
        pipeline_name = self._get_pipeline_name(config.pipeline_type)
        if config.pipeline_version:
            pipeline_name += f" -r {config.pipeline_version}"
        cmd.append(pipeline_name)

        # Profiles
        if config.profile:
            cmd.extend(["-profile", ",".join(config.profile)])

        # Work directory
        work_dir = config.work_dir or self.work_dir
        cmd.extend(["-work-dir", str(work_dir)])

        # Resume option
        if config.resume:
            cmd.append("-resume")

        # Add parameters
        params = self._build_parameters(config)
        for key, value in params.items():
            if value is not None:
                if isinstance(value, bool):
                    if value:
                        cmd.append(f"--{key}")
                else:
                    cmd.extend([f"--{key}", str(value)])

        # Resource limits
        if config.max_cpus:
            cmd.extend(["--max_cpus", str(config.max_cpus)])
        if config.max_memory:
            cmd.extend(["--max_memory", config.max_memory])
        if config.max_time:
            cmd.extend(["--max_time", config.max_time])

        return cmd

    def _build_parameters(self, config: PipelineConfig) -> Dict[str, any]:
        """Extract parameters from config."""
        params = config.parameters.model_dump(exclude={"extra_params"})

        # Add extra parameters
        if hasattr(config.parameters, "extra_params"):
            params.update(config.parameters.extra_params)

        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        return params

    def _get_pipeline_name(self, pipeline_type: PipelineType) -> str:
        """Get the full nf-core pipeline name."""
        pipeline_map = {
            PipelineType.FETCHNGS: "nf-core/fetchngs",
            PipelineType.RNASEQ: "nf-core/rnaseq",
            PipelineType.SAREK: "nf-core/sarek",
            PipelineType.CHIPSEQ: "nf-core/chipseq",
            PipelineType.ATACSEQ: "nf-core/atacseq",
            PipelineType.SCRNASEQ: "nf-core/scrnaseq",
            PipelineType.METHYLSEQ: "nf-core/methylseq",
            PipelineType.AMPLISEQ: "nf-core/ampliseq",
        }
        return pipeline_map.get(pipeline_type, f"nf-core/{pipeline_type.value}")

    def _get_nextflow_version(self) -> Optional[str]:
        """Get the installed Nextflow version."""
        try:
            result = subprocess.run(
                [self.nextflow_bin, "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse version from output
                for line in result.stdout.split("\n"):
                    if "version" in line.lower():
                        return line.strip()
            return None
        except Exception:
            return None

    def check_pipeline_status(
        self, result: ExecutionResult
    ) -> ExecutionStatus:
        """
        Check the status of a running pipeline.

        Args:
            result: Previous execution result

        Returns:
            Updated execution status
        """
        # Check if .nextflow.log or .exitcode file exists
        work_dir = Path(result.work_dir)

        # Look for completion markers
        if (work_dir / ".exitcode").exists():
            with open(work_dir / ".exitcode") as f:
                exit_code = int(f.read().strip())
                if exit_code == 0:
                    return ExecutionStatus.COMPLETED
                else:
                    return ExecutionStatus.FAILED

        # If log file exists and hasn't been updated recently, might be stuck
        if result.log_file and Path(result.log_file).exists():
            log_age = time.time() - Path(result.log_file).stat().st_mtime
            if log_age > 3600:  # No updates for 1 hour
                logger.warning("Pipeline appears to be stuck (no log updates for 1 hour)")

        return ExecutionStatus.RUNNING

    def clean_work_directory(self, work_dir: Path, keep_latest: bool = True) -> None:
        """
        Clean up Nextflow work directory.

        Args:
            work_dir: Work directory to clean
            keep_latest: Whether to keep the latest run for resumption
        """
        if not work_dir.exists():
            return

        if keep_latest:
            # Only remove old runs, keep .nextflow* files
            import shutil

            for item in work_dir.iterdir():
                if item.is_dir() and not item.name.startswith(".nextflow"):
                    shutil.rmtree(item)
                    logger.info(f"Removed {item}")
        else:
            # Remove entire work directory
            import shutil

            shutil.rmtree(work_dir)
            logger.info(f"Removed entire work directory: {work_dir}")


def check_nextflow_available() -> bool:
    """Check if Nextflow is available in the system."""
    try:
        result = subprocess.run(
            ["nextflow", "-version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def install_nextflow_instructions() -> str:
    """Return instructions for installing Nextflow."""
    return """
Nextflow is not installed. To install Nextflow:

1. Using conda (recommended):
   conda install -c bioconda nextflow

2. Using curl:
   curl -s https://get.nextflow.io | bash
   sudo mv nextflow /usr/local/bin/

3. Manual installation:
   Visit https://www.nextflow.io/docs/latest/getstarted.html

After installation, verify with:
   nextflow -version
"""
