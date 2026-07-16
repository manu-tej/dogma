"""
Nextflow pipeline executor.

This module provides the execution engine for running Nextflow pipelines,
managing their lifecycle, and tracking their status.
"""

import asyncio
import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Any
import logging

from ..models.nextflow import (
    PipelineConfiguration,
    PipelineExecution,
    PipelineInput,
    PipelineStatus,
    NextflowConfig,
)
from .registry import get_pipeline_registry


logger = logging.getLogger(__name__)


class NextflowExecutor:
    """
    Executor for running Nextflow pipelines.

    Manages pipeline execution lifecycle including:
    - Configuration validation
    - Command construction
    - Process management
    - Status tracking
    - Log collection
    """

    def __init__(self, config: Optional[NextflowConfig] = None):
        """
        Initialize the executor.

        Args:
            config: Nextflow configuration (uses defaults if not provided)
        """
        self.config = config or NextflowConfig()
        self.registry = get_pipeline_registry()
        self._executions: Dict[str, PipelineExecution] = {}
        self._processes: Dict[str, subprocess.Popen] = {}

        # Ensure directories exist
        Path(self.config.work_dir).mkdir(parents=True, exist_ok=True)
        Path(self.config.output_dir).mkdir(parents=True, exist_ok=True)

    def _check_nextflow_available(self) -> bool:
        """
        Check if Nextflow is available in the system.

        Returns:
            True if Nextflow is available, False otherwise
        """
        nextflow_path = shutil.which(self.config.nextflow_executable)
        if nextflow_path:
            logger.info(f"Nextflow found at: {nextflow_path}")
            return True
        else:
            logger.warning("Nextflow not found in PATH")
            return False

    def _get_nextflow_version(self) -> Optional[str]:
        """
        Get the installed Nextflow version.

        Returns:
            Version string or None if unable to determine
        """
        try:
            result = subprocess.run(
                [self.config.nextflow_executable, "-version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # Parse version from output
                for line in result.stdout.split('\n'):
                    if 'version' in line.lower():
                        return line.strip()
            return None
        except Exception as e:
            logger.error(f"Failed to get Nextflow version: {e}")
            return None

    def _validate_configuration(
        self,
        config: PipelineConfiguration,
        input_spec: PipelineInput,
    ) -> List[str]:
        """
        Validate pipeline configuration.

        Args:
            config: Pipeline configuration
            input_spec: Input specification

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check if pipeline exists
        pipeline = self.registry.get_pipeline(config.pipeline_id)
        if not pipeline:
            errors.append(f"Pipeline not found: {config.pipeline_id}")
            return errors

        # Validate required parameters
        required_params = [p for p in pipeline.parameters if p.required]
        for param in required_params:
            param_name = param.name.lstrip('-')
            if param_name not in config.parameters:
                errors.append(f"Required parameter missing: {param.name}")

        # Validate input files exist
        for input_file in input_spec.input_files:
            if not Path(input_file).exists():
                errors.append(f"Input file not found: {input_file}")

        # Validate samplesheet if provided
        if input_spec.samplesheet and not Path(input_spec.samplesheet).exists():
            errors.append(f"Samplesheet not found: {input_spec.samplesheet}")

        # Validate profile
        valid_profiles = ["docker", "singularity", "conda", "standard"]
        if config.profile not in valid_profiles:
            errors.append(
                f"Invalid profile: {config.profile}. Must be one of {valid_profiles}"
            )

        return errors

    def _build_nextflow_command(
        self,
        config: PipelineConfiguration,
        input_spec: PipelineInput,
        execution_id: str,
    ) -> List[str]:
        """
        Build the Nextflow command line.

        Args:
            config: Pipeline configuration
            input_spec: Input specification
            execution_id: Execution identifier

        Returns:
            Command line arguments as list
        """
        cmd = [self.config.nextflow_executable]

        # Add run command
        cmd.append("run")

        # Add pipeline identifier
        cmd.append(config.pipeline_id)

        # Add revision/version if specified
        if config.pipeline_version and config.pipeline_version != "latest":
            cmd.extend(["-r", config.pipeline_version])

        # Add profile
        cmd.extend(["-profile", config.profile])

        # Add work directory
        work_dir = config.work_dir or os.path.join(self.config.work_dir, execution_id)
        cmd.extend(["-work-dir", work_dir])

        # Add resume if requested
        if config.resume:
            cmd.append("-resume")

        # Add reports
        if self.config.report_enabled:
            report_dir = Path(config.output_dir) / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            cmd.extend([
                "-with-report", str(report_dir / "execution_report.html"),
            ])

        if self.config.timeline_enabled:
            report_dir = Path(config.output_dir) / "reports"
            cmd.extend([
                "-with-timeline", str(report_dir / "execution_timeline.html"),
            ])

        if self.config.trace_enabled:
            report_dir = Path(config.output_dir) / "reports"
            cmd.extend([
                "-with-trace", str(report_dir / "execution_trace.txt"),
            ])

        if self.config.dag_enabled:
            report_dir = Path(config.output_dir) / "reports"
            cmd.extend([
                "-with-dag", str(report_dir / "pipeline_dag.svg"),
            ])

        # Add pipeline parameters
        for param_name, param_value in config.parameters.items():
            # Ensure parameter starts with --
            if not param_name.startswith("--"):
                param_name = f"--{param_name}"

            # Handle different parameter types
            if isinstance(param_value, bool):
                if param_value:
                    cmd.append(param_name)
            elif isinstance(param_value, (list, tuple)):
                cmd.append(param_name)
                cmd.append(",".join(str(v) for v in param_value))
            else:
                cmd.append(param_name)
                cmd.append(str(param_value))

        # Add resource limits
        if config.max_cpus:
            cmd.extend(["--max_cpus", str(config.max_cpus)])
        if config.max_memory_gb:
            cmd.extend(["--max_memory", f"{config.max_memory_gb}.GB"])
        if config.max_time_hours:
            cmd.extend(["--max_time", f"{config.max_time_hours}.h"])

        return cmd

    async def execute_pipeline(
        self,
        config: PipelineConfiguration,
        input_spec: PipelineInput,
    ) -> PipelineExecution:
        """
        Execute a pipeline asynchronously.

        Args:
            config: Pipeline configuration
            input_spec: Input specification

        Returns:
            PipelineExecution object tracking the execution

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate configuration
        errors = self._validate_configuration(config, input_spec)
        if errors:
            raise ValueError(f"Configuration validation failed: {', '.join(errors)}")

        # Check Nextflow availability
        if not self._check_nextflow_available():
            raise RuntimeError(
                f"Nextflow not found. Please install Nextflow and ensure "
                f"'{self.config.nextflow_executable}' is in your PATH."
            )

        # Create execution record
        execution_id = str(uuid.uuid4())
        execution = PipelineExecution(
            execution_id=execution_id,
            pipeline_id=config.pipeline_id,
            pipeline_version=config.pipeline_version,
            configuration=config,
            input_spec=input_spec,
            status=PipelineStatus.PENDING,
            created_at=datetime.utcnow(),
            work_directory=config.work_dir or os.path.join(self.config.work_dir, execution_id),
            output_directory=config.output_dir,
        )

        # Store execution
        self._executions[execution_id] = execution

        # Build command
        cmd = self._build_nextflow_command(config, input_spec, execution_id)

        # Create log file
        log_dir = Path(config.output_dir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"execution_{execution_id}.log"
        execution.log_file = str(log_file)

        logger.info(f"Starting pipeline execution {execution_id}")
        logger.info(f"Command: {' '.join(cmd)}")

        # Start execution in background
        asyncio.create_task(self._run_pipeline_process(execution, cmd, log_file))

        # Update status
        execution.status = PipelineStatus.QUEUED

        return execution

    async def _run_pipeline_process(
        self,
        execution: PipelineExecution,
        cmd: List[str],
        log_file: Path,
    ):
        """
        Run the pipeline process and track its execution.

        Args:
            execution: Execution record
            cmd: Command line arguments
            log_file: Path to log file
        """
        try:
            # Update status to running
            execution.status = PipelineStatus.RUNNING
            execution.started_at = datetime.utcnow()

            # Open log file
            with open(log_file, "w") as log_fp:
                # Write command to log
                log_fp.write(f"Command: {' '.join(cmd)}\n")
                log_fp.write(f"Started: {execution.started_at}\n")
                log_fp.write("-" * 80 + "\n\n")
                log_fp.flush()

                # Start process
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=log_fp,
                    stderr=subprocess.STDOUT,
                    cwd=os.getcwd(),
                )

                self._processes[execution.execution_id] = process

                # Wait for completion
                return_code = await process.wait()

                # Update execution status
                execution.completed_at = datetime.utcnow()

                if return_code == 0:
                    execution.status = PipelineStatus.COMPLETED
                    execution.progress_percent = 100.0
                    logger.info(f"Pipeline {execution.execution_id} completed successfully")

                    # Collect output files
                    self._collect_output_files(execution)
                else:
                    execution.status = PipelineStatus.FAILED
                    execution.error_message = f"Pipeline failed with exit code {return_code}"
                    logger.error(f"Pipeline {execution.execution_id} failed: {execution.error_message}")

        except Exception as e:
            execution.status = PipelineStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            logger.exception(f"Pipeline {execution.execution_id} failed with exception")

        finally:
            # Clean up process reference
            if execution.execution_id in self._processes:
                del self._processes[execution.execution_id]

    def _collect_output_files(self, execution: PipelineExecution):
        """
        Collect output files from completed pipeline.

        Args:
            execution: Execution record
        """
        output_dir = Path(execution.output_directory)
        if not output_dir.exists():
            return

        # Find common output files
        output_files = []

        # MultiQC report
        multiqc_reports = list(output_dir.glob("**/multiqc_report.html"))
        if multiqc_reports:
            execution.multiqc_report = str(multiqc_reports[0])
            output_files.append(str(multiqc_reports[0]))

        # Pipeline reports
        report_dir = output_dir / "reports"
        if report_dir.exists():
            for report_file in report_dir.glob("*.html"):
                output_files.append(str(report_file))
                if "execution_report" in report_file.name:
                    execution.pipeline_report = str(report_file)

        # Collect all output files (limit to reasonable number)
        all_files = [str(f) for f in output_dir.rglob("*") if f.is_file()]
        execution.output_files = all_files[:1000]  # Limit to 1000 files

        logger.info(f"Collected {len(execution.output_files)} output files")

    def get_execution(self, execution_id: str) -> Optional[PipelineExecution]:
        """
        Get execution by ID.

        Args:
            execution_id: Execution identifier

        Returns:
            PipelineExecution or None if not found
        """
        return self._executions.get(execution_id)

    def list_executions(
        self,
        pipeline_id: Optional[str] = None,
        status: Optional[PipelineStatus] = None,
    ) -> List[PipelineExecution]:
        """
        List executions with optional filtering.

        Args:
            pipeline_id: Filter by pipeline ID
            status: Filter by status

        Returns:
            List of matching executions
        """
        results = list(self._executions.values())

        if pipeline_id:
            results = [e for e in results if e.pipeline_id == pipeline_id]

        if status:
            results = [e for e in results if e.status == status]

        # Sort by creation time (newest first)
        results.sort(key=lambda e: e.created_at, reverse=True)

        return results

    async def cancel_execution(self, execution_id: str) -> bool:
        """
        Cancel a running execution.

        Args:
            execution_id: Execution identifier

        Returns:
            True if cancelled, False if not found or not running
        """
        execution = self._executions.get(execution_id)
        if not execution:
            return False

        if execution.status not in [PipelineStatus.RUNNING, PipelineStatus.QUEUED]:
            return False

        # Terminate process if running
        process = self._processes.get(execution_id)
        if process:
            try:
                process.terminate()
                # Wait for termination
                await asyncio.sleep(2)
                if process.returncode is None:
                    process.kill()  # Force kill if still running
                logger.info(f"Cancelled execution {execution_id}")
            except Exception as e:
                logger.error(f"Failed to cancel execution {execution_id}: {e}")
                return False

        # Update status
        execution.status = PipelineStatus.CANCELLED
        execution.completed_at = datetime.utcnow()

        return True

    def get_execution_logs(
        self,
        execution_id: str,
        tail_lines: Optional[int] = None,
    ) -> Optional[str]:
        """
        Get execution logs.

        Args:
            execution_id: Execution identifier
            tail_lines: Number of lines from end to return (None for all)

        Returns:
            Log content or None if not found
        """
        execution = self._executions.get(execution_id)
        if not execution or not execution.log_file:
            return None

        log_path = Path(execution.log_file)
        if not log_path.exists():
            return None

        try:
            with open(log_path, "r") as f:
                if tail_lines:
                    # Read last N lines
                    lines = f.readlines()
                    return "".join(lines[-tail_lines:])
                else:
                    return f.read()
        except Exception as e:
            logger.error(f"Failed to read log file: {e}")
            return None
