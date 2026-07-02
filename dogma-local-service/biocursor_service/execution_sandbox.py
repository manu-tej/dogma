"""Safe workflow run plans and explicitly gated execution."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from shlex import quote
from typing import Any

from .indexer import scan_workspace

DEFAULT_TIMEOUT_SECONDS = 30


def has_error_findings(scan_result: dict[str, Any]) -> bool:
    return any(issue.get("severity") == "error" for issue in scan_result.get("issues", []))


def command_text(argv: list[str]) -> str:
    return " ".join(quote(part) for part in argv)


def workflow_engine(file_path: str) -> str | None:
    lower = file_path.lower()
    if lower.endswith(".nf") or lower.endswith("nextflow.config"):
        return "nextflow"
    if lower.endswith("snakefile") or lower.endswith(".smk") or lower.endswith(".snakefile"):
        return "snakemake"
    return None


def build_command(root: Path, workflow_file: str, index: int) -> dict[str, Any] | None:
    engine = workflow_engine(workflow_file)
    if engine == "nextflow":
        argv = ["nextflow", "run", workflow_file, "-stub-run"]
        mode = "stub-run"
        purpose = "Compile the Nextflow graph and execute process stubs without running real tools."
    elif engine == "snakemake":
        argv = ["snakemake", "--snakefile", workflow_file, "--dry-run", "--printshellcmds"]
        mode = "dry-run"
        purpose = "Resolve the Snakemake DAG and print planned shell commands without executing rules."
    else:
        return None

    available = shutil.which(argv[0]) is not None
    return {
        "id": f"{engine}-{index}",
        "engine": engine,
        "workflow_file": workflow_file,
        "mode": mode,
        "label": f"{engine.capitalize()} {mode} for {workflow_file}",
        "argv": argv,
        "command": command_text(argv),
        "cwd": str(root),
        "purpose": purpose,
        "tool_available": available,
        "requires_review": True,
    }


def build_run_plan(scan_result: dict[str, Any]) -> dict[str, Any]:
    root = Path(scan_result["root"]).resolve()
    workflow_files = scan_result.get("context", {}).get("workflow_files", [])
    trust = scan_result.get("trust", {})
    trust_blockers = trust.get("blockers", []) if trust.get("trusted") is False else []
    commands = [
        command
        for index, workflow_file in enumerate(workflow_files, start=1)
        if (command := build_command(root, workflow_file, index)) is not None
    ]
    blocked = has_error_findings(scan_result) or bool(trust_blockers)
    error_count = scan_result.get("summary", {}).get("errors", 0)
    warning_count = scan_result.get("summary", {}).get("warnings", 0)

    for command in commands:
        command["execution_allowed"] = bool(not blocked and command["tool_available"])
        if trust_blockers:
            command["blocked_reason"] = " ".join(trust_blockers)
        elif has_error_findings(scan_result):
            command["blocked_reason"] = "Error-level Dogma findings must be fixed before executing workflow commands."
        elif not command["tool_available"]:
            command["blocked_reason"] = f"{command['engine']} is not available on PATH."
        else:
            command["blocked_reason"] = None

    return {
        "service": "dogma-local-service",
        "root": str(root),
        "status": "blocked" if blocked else "ready_for_review",
        "execution_allowed": bool(commands and all(command["execution_allowed"] for command in commands)),
        "error_count": error_count,
        "warning_count": warning_count,
        "trust": trust,
        "commands": commands,
        "provenance": [
            "Capture command, working directory, timestamp, workflow file, and tool version.",
            "Record genome build, annotation release, reference checksums, sample sheet checksum, and container/Conda environment.",
            "Store stdout, stderr, and exit code for every dry-run or stub-run attempt.",
        ],
        "safety_notes": [
            "Only dry-run and stub-run commands are generated.",
            "Execution requires an explicit execute=true request.",
            "Execution is blocked while error-level Dogma findings remain.",
            "Execution is blocked when human data is detected and the workspace trust policy is missing or does not allow local operations.",
            "Review warnings before moving from dry-run/stub-run to real analysis.",
        ],
    }


def build_run_plan_for_workspace(root: str | Path, max_files: int = 500) -> dict[str, Any]:
    return build_run_plan(scan_workspace(root, max_files=max_files))


def execute_command(root: str | Path, command_id: str | None = None, max_files: int = 500, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS, execute: bool = False) -> dict[str, Any]:
    scan_result = scan_workspace(root, max_files=max_files)
    plan = build_run_plan(scan_result)
    commands = plan["commands"]
    selected = commands[0] if commands and command_id is None else next((command for command in commands if command["id"] == command_id), None)

    if selected is None:
        return {
            "status": "no_command",
            "executed": False,
            "message": "No matching dry-run or stub-run command is available for this workspace.",
            "run_plan": plan,
        }

    if not execute:
        return {
            "status": "preview",
            "executed": False,
            "message": "Command was not executed. Send execute=true after review to run an allowed dry-run/stub-run command.",
            "command": selected,
            "run_plan": plan,
        }

    if not selected["execution_allowed"]:
        return {
            "status": "blocked",
            "executed": False,
            "message": selected["blocked_reason"] or "Command is not allowed.",
            "command": selected,
            "run_plan": plan,
        }

    try:
        completed = subprocess.run(
            selected["argv"],
            cwd=Path(root).expanduser().resolve(),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        return {
            "status": "completed" if completed.returncode == 0 else "failed",
            "executed": True,
            "command": selected,
            "return_code": completed.returncode,
            "stdout": completed.stdout[-20000:],
            "stderr": completed.stderr[-20000:],
            "run_plan": plan,
        }
    except subprocess.TimeoutExpired as error:
        return {
            "status": "timeout",
            "executed": True,
            "command": selected,
            "return_code": None,
            "stdout": (error.stdout or "")[-20000:] if isinstance(error.stdout, str) else "",
            "stderr": (error.stderr or "")[-20000:] if isinstance(error.stderr, str) else "",
            "message": f"Command timed out after {timeout_seconds} seconds.",
            "run_plan": plan,
        }
