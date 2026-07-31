"""Methods-graph preflight for Dogma workflow actions.

This module is deliberately a thin consumer of methods-graph. Dogma can derive
the proposed method chain and dataset facts from the local workspace, then ask
methods-graph for a guardrail-chain verdict when an audited graph and CLI are
configured. Missing pieces are explicit coverage gaps.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .indexer import parse_table, read_text_limited, scan_workspace
from .method_guardrails import extract_nextflow_processes
from .methods_graph_substrate import build_methods_graph_substrate, env_value


def escape_table_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def resolve_cli_command(env: Mapping[str, str]) -> dict[str, Any]:
    env_var, configured = env_value(env, ["DOGMA_METHODS_GRAPH_CLI", "BIOCURSOR_METHODS_GRAPH_CLI"])
    raw = configured or "methods-graph"
    try:
        parts = shlex.split(raw)
    except ValueError as error:
        return {
            "env_var": env_var,
            "configured": raw,
            "resolved": None,
            "argv_prefix": [],
            "error": f"invalid command: {error}",
        }

    if not parts:
        return {"env_var": env_var, "configured": raw, "resolved": None, "argv_prefix": [], "error": "empty command"}

    executable = parts[0]
    resolved = shutil.which(executable)
    if resolved is None and Path(executable).expanduser().exists():
        resolved = str(Path(executable).expanduser().resolve())

    return {
        "env_var": env_var,
        "configured": raw,
        "resolved": resolved,
        "argv_prefix": [resolved, *parts[1:]] if resolved else [],
        "error": None if resolved else "command not found",
    }


def condition_counts_from_sample_sheet(root: Path, scan: dict[str, Any]) -> tuple[dict[str, int], dict[str, str]]:
    sample_file = scan.get("context", {}).get("sample_file")
    if not sample_file:
        return {}, {}

    path = root / sample_file
    if not path.exists():
        return {}, {}

    text, _ = read_text_limited(path)
    headers, rows = parse_table(text)
    normalized = {header.strip().lower(): header for header in headers}
    condition_key = normalized.get("condition")
    if not condition_key:
        return {}, {}

    counts = Counter(row.get(condition_key, "").strip() for row in rows if row.get(condition_key, "").strip())
    facts: dict[str, int] = {}
    sources: dict[str, str] = {}
    if len(counts) >= 2:
        facts["replicates_per_group"] = min(counts.values())
        sources["replicates_per_group"] = f"{sample_file}: minimum condition count across {dict(sorted(counts.items()))}"
    return facts, sources


def derive_dataset_facts(root: Path, scan: dict[str, Any]) -> dict[str, Any]:
    facts, sources = condition_counts_from_sample_sheet(root, scan)
    return {
        "facts": facts,
        "sources": sources,
    }


def derive_method_chain(root: Path, scan: dict[str, Any]) -> dict[str, Any]:
    processes = extract_nextflow_processes(root, scan.get("context", {}).get("workflow_files", []))
    steps: list[dict[str, Any]] = []
    method_ids: list[str] = []
    for process in processes:
        contract = process.get("method_contract") or {}
        method_id = contract.get("method_id")
        location = f"{process.get('file')}:{process.get('line')}"
        status = "ready" if method_id else "coverage_gap"
        if method_id:
            method_ids.append(method_id)
        steps.append(
            {
                "process": process.get("name"),
                "location": location,
                "method_id": method_id,
                "container": process.get("container"),
                "status": status,
            }
        )

    return {
        "steps": steps,
        "method_ids": method_ids,
        "coverage_gaps": [] if method_ids else ["workflow.method_chain_missing"],
    }


def build_guardrail_chain_command(cli: dict[str, Any], graph_path: str, method_ids: list[str], facts: dict[str, int]) -> list[str]:
    command = [*cli.get("argv_prefix", []), "guardrail-chain", "--db", graph_path, "--json"]
    for method_id in method_ids:
        command.extend(["--step", method_id])
    for key in sorted(facts):
        command.extend(["--fact", f"{key}={facts[key]}"])
    return command


def run_guardrail_chain(command: list[str], timeout_seconds: int = 30) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired as error:
        return {
            "status": "timeout",
            "exit_code": None,
            "stdout": error.stdout or "",
            "stderr": error.stderr or "",
            "verdict": None,
            "error": f"methods-graph guardrail-chain timed out after {timeout_seconds} seconds",
        }
    except OSError as error:
        return {
            "status": "execution_error",
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "verdict": None,
            "error": f"{type(error).__name__}: {error}",
        }

    verdict = None
    parse_error = None
    if completed.stdout.strip():
        try:
            verdict = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            parse_error = f"{error.msg} at line {error.lineno}"

    return {
        "status": "completed" if verdict is not None else "parse_gap",
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "verdict": verdict,
        "error": parse_error,
    }


def status_from_verdict(verdict: dict[str, Any] | None) -> tuple[str, list[str]]:
    if not verdict:
        return "query_gap", ["methods_graph.guardrail_chain_unavailable"]

    status = verdict.get("status")
    if status == "EVALUABLE":
        return "evaluable", []
    if status == "BLOCKED":
        return "blocked", ["methods_graph.guardrail_chain_blocked"]
    if status == "NOT_EVALUABLE":
        return "not_evaluable", ["methods_graph.guardrail_chain_not_evaluable"]
    return "query_gap", ["methods_graph.guardrail_chain_unknown_status"]


def next_actions_for(status: str, gaps: list[str]) -> list[str]:
    actions = []
    if "methods_graph.audited_substrate_missing" in gaps:
        actions.append("Configure DOGMA_METHODS_GRAPH_DB to an audited Kuzu database with ingest.lock.json.")
    if "methods_graph.cli_missing" in gaps:
        actions.append("Install methods-graph on PATH or set DOGMA_METHODS_GRAPH_CLI to its executable.")
    if "workflow.method_chain_missing" in gaps:
        actions.append("Add or map workflow process method contracts before asking methods-graph for a chain verdict.")
    if status == "blocked":
        actions.append("Treat the proposed method chain as blocked until failed pre-run gates are resolved.")
    if status == "not_evaluable":
        actions.append("Treat the method chain as a coverage gap; do not infer permission to execute.")
    if status == "evaluable":
        actions.append("Continue with Dogma dry-run, trust, container, and patch review gates before any real execution.")
    if not actions:
        actions.append("Resolve the reported preflight gaps before execution planning.")
    return actions


def render_methods_graph_preflight_markdown(result: dict[str, Any]) -> str:
    dataset = result.get("dataset_facts", {})
    facts = dataset.get("facts", {})
    sources = dataset.get("sources", {})
    fact_rows = [
        f"| {key} | {value} | {escape_table_cell(sources.get(key, 'workspace scan'))} |"
        for key, value in sorted(facts.items())
    ] or ["| none | none | No dataset facts could be derived for methods-graph pre-run gates. |"]

    step_rows = [
        f"| {item.get('process')} | {item.get('location')} | {item.get('method_id') or 'coverage gap'} | {item.get('container') or 'missing'} | {item.get('status')} |"
        for item in result.get("method_chain", {}).get("steps", [])
    ] or ["| none | none | none | none | coverage_gap |"]

    gaps = result.get("coverage_gaps", [])
    gap_rows = [f"- {gap}" for gap in gaps] or ["- none"]
    action_rows = [f"- {item}" for item in result.get("next_actions", [])]
    command = result.get("command") or []
    verdict = result.get("verdict") or {}
    cli = result.get("cli", {})

    return "\n".join(
        [
            "# Dogma Methods-Graph Preflight",
            "",
            "This is a methodological preflight for IDE workflow actions. It is not a biological support/refute verdict.",
            "",
            "## Summary",
            "",
            f"- Status: {result.get('status')}",
            f"- Substrate status: {result.get('substrate_status')}",
            f"- Root: `{result.get('root')}`",
            f"- CLI: {cli.get('resolved') or cli.get('error') or 'not resolved'}",
            f"- Verdict: {verdict.get('status') or 'not available'}",
            "",
            "## Dataset Facts",
            "",
            "| Fact | Value | Source |",
            "| --- | --- | --- |",
            *fact_rows,
            "",
            "## Method Chain",
            "",
            "| Process | Location | Method ID | Container | Status |",
            "| --- | --- | --- | --- | --- |",
            *step_rows,
            "",
            "## methods-graph Command",
            "",
            "```bash",
            shlex.join(command) if command else "not run",
            "```",
            "",
            "## Coverage Gaps",
            "",
            *gap_rows,
            "",
            "## Next Actions",
            "",
            *action_rows,
            "",
        ]
    )


def build_methods_graph_preflight(
    root: str | Path,
    max_files: int = 500,
    *,
    env: Mapping[str, str] | None = None,
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    values = env or os.environ
    root_path = Path(root).expanduser().resolve()
    scan = scan_workspace(root_path, max_files=max_files)
    substrate = build_methods_graph_substrate(values)
    cli = resolve_cli_command(values)
    dataset = derive_dataset_facts(root_path, scan)
    method_chain = derive_method_chain(root_path, scan)
    graph_path = substrate.get("configured_graph", {}).get("path")
    coverage_gaps = list(method_chain.get("coverage_gaps", []))
    command: list[str] = []
    command_result: dict[str, Any] | None = None
    verdict: dict[str, Any] | None = None

    if substrate.get("status") != "ready":
        status = "configuration_gap"
        coverage_gaps.append("methods_graph.audited_substrate_missing")
    elif not method_chain.get("method_ids"):
        status = "coverage_gap"
    elif not cli.get("resolved"):
        status = "dependency_gap"
        coverage_gaps.append("methods_graph.cli_missing")
    else:
        command = build_guardrail_chain_command(cli, graph_path, method_chain["method_ids"], dataset["facts"])
        command_result = run_guardrail_chain(command, timeout_seconds=timeout_seconds)
        verdict = command_result.get("verdict")
        status, verdict_gaps = status_from_verdict(verdict)
        coverage_gaps.extend(verdict_gaps)
        if command_result.get("status") != "completed":
            coverage_gaps.append("methods_graph.guardrail_chain_query_failed")

    coverage_gaps = list(dict.fromkeys(coverage_gaps))
    result = {
        "service": "dogma-local-service",
        "root": str(root_path),
        "status": status,
        "substrate_status": substrate.get("status"),
        "configured_graph": substrate.get("configured_graph", {}),
        "cli": {key: value for key, value in cli.items() if key != "argv_prefix"},
        "scan_summary": scan.get("summary", {}),
        "dataset_facts": dataset,
        "method_chain": method_chain,
        "command": command,
        "command_result": command_result,
        "verdict": verdict,
        "coverage_gaps": coverage_gaps,
        "next_actions": next_actions_for(status, coverage_gaps),
    }
    result["markdown"] = render_methods_graph_preflight_markdown(result)
    return result
