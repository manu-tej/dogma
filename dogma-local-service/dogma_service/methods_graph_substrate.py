"""Methods-graph substrate report for Dogma.

This keeps methods-graph as an external guardrail authority: Dogma can report
what it expects from the substrate without inventing missing method edges.
"""

from __future__ import annotations

import os
import shutil
import json
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Mapping

from .repo_paths import DOGMA_REPOSITORY_URL, dogma_repo_root, dogma_source_url, methods_graph_repo_root

METHODS_GRAPH_REPO = methods_graph_repo_root()
DOGMA_REPO = dogma_repo_root()


def env_value(env: Mapping[str, str], names: list[str]) -> tuple[str | None, str | None]:
    for name in names:
        value = env.get(name)
        if value:
            return name, value
    return None, None


def ingest_lock_for(graph_path: str | None) -> str | None:
    """Find ingest or rebuild provenance, retaining the legacy report field.

    ``mg ingest`` writes ingest.lock.json; ``mg rebuild`` writes
    methods.lock.json beside its database. Discovery is not an integrity audit.
    """
    if not graph_path:
        return None
    path = Path(graph_path).expanduser()
    directories = [path, path.parent] if path.is_dir() else [path.parent]
    # Existing ingest locks keep precedence when both forms are present.
    candidates = [directory / name for name in ("ingest.lock.json", "methods.lock.json")
                  for directory in directories]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return str(candidates[0].resolve()) if candidates else None


def build_methods_graph_substrate(env: Mapping[str, str] | None = None, *, runner=None, timeout_seconds=30) -> dict[str, Any]:
    values = os.environ if env is None else env
    graph_env, graph_path = env_value(values, ["DOGMA_METHODS_GRAPH_DB", "METHODS_GRAPH_DB", "BIOCURSOR_METHODS_GRAPH_DB", "QURATION_METHODS_GRAPH_DB"])
    lock_path = ingest_lock_for(graph_path)
    _, cli_command = env_value(values, ["DOGMA_METHODS_GRAPH_CLI", "BIOCURSOR_METHODS_GRAPH_CLI"])
    try:
        cli_parts = shlex.split(cli_command or "methods-graph")
    except ValueError:
        cli_parts = []
    cli_path = shutil.which(cli_parts[0]) if cli_parts else None
    graph_exists = bool(graph_path and Path(graph_path).expanduser().exists())
    lock_exists = bool(lock_path and Path(lock_path).expanduser().exists())

    configured = bool(graph_path)
    verification = None
    audited_ready = False
    status = "configuration_gap" if not configured else "needs_audit_lock"
    if configured and graph_exists and lock_exists:
        status = "dependency_gap" if not cli_path else "verification_failed"
        if cli_path:
            try:
                completed = (runner or subprocess.run)(
                    [cli_path, *cli_parts[1:], "verify-substrate", "--db", graph_path,
                     "--lock", lock_path, "--json"], capture_output=True, text=True,
                    timeout=timeout_seconds)
                verification = json.loads(completed.stdout)
                audited_ready = (completed.returncode == 0 and isinstance(verification, dict)
                    and type(verification.get("schema")) is int and verification["schema"] == 1 and verification.get("verified") is True
                    and verification.get("status") == "verified"
                    and isinstance(verification.get("audit"), dict)
                    and verification["audit"].get("ok") is True
                    and verification.get("graph_hash") == verification.get("expected_graph_hash")
                    and isinstance(verification.get("graph_hash"), str)
                    and re.fullmatch(r"sha256:[0-9a-f]{64}", verification["graph_hash"]) is not None)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                verification = {"status": "verification_failed", "verified": False}
            status = "ready" if audited_ready else "verification_failed"

    result = {
        "service": "dogma-local-service",
        "status": status,
        "verification": verification,
        "configured_graph": {
            "env_var": graph_env,
            "path": str(Path(graph_path).expanduser()) if graph_path else None,
            "exists": graph_exists,
            "ingest_lock": lock_path,
            "ingest_lock_exists": lock_exists,
            "cli_path": cli_path,
        },
        "authoritative_surface": [
            {
                "name": "audited_kuzu_graph",
                "status": "ready" if audited_ready else "gap",
                "detail": "Runtime guardrails should come from an audited Kuzu graph plus ingest.lock.json or methods.lock.json.",
            },
            {
                "name": "workflow_ir_validator_ledger",
                "status": "usable",
                "detail": "WorkflowIR, validate_workflow, and append-only ledgers are reusable now as Python imports.",
            },
            {
                "name": "planner_expand",
                "status": "advisory_only",
                "detail": "Planner expansion is deterministic one-hop guidance, not a runnable execution plan.",
            },
            {
                "name": "typed_method_edges",
                "status": "guardrail",
                "detail": "Dogma must not invent Method, statistical-method, assumption, or executor edges.",
            },
        ],
        "dogma_execution_aspiration": [
            "Graph canvas and chat are two controls over the same edge-evaluation substrate.",
            "A selected edge opens an EvaluationPlan with readout, grounding, compose, execute, and interpret contracts.",
            "methods-graph grounds method choices, assumptions, preconditions, and COVERAGE_GAP outcomes.",
            "Evidence records remain factual; they do not become support/refute verdicts or confidence grades.",
            "The future moat is agent-proposed workflow specs validated by methods-graph before execution.",
        ],
        "dogma_policy": [
            "Use methods-graph as a guardrail substrate, not as a biological truth oracle.",
            "Treat missing method, container, assumption, dataset, or contrast coverage as an explicit gap.",
            "Require dry-run, trust, validation, container, and provenance gates before real execution.",
            "Expose graph edits and evaluation plans as structured proposals requiring user approval.",
        ],
        "sources": {
            "dogma_repo": DOGMA_REPOSITORY_URL,
            "methods_graph_repo": METHODS_GRAPH_REPO,
            "methods_graph_workflow_validator": f"{METHODS_GRAPH_REPO}/src/methods_graph/workflow/validator.py",
            "methods_graph_ledger": f"{METHODS_GRAPH_REPO}/src/methods_graph/workflow/ledger.py",
            "edge_evaluation_contract": dogma_source_url("src/quration/hypothesis/orchestrator/evaluation_plan.py"),
            "compatibility_llm_provider": dogma_source_url("src/quration/llm/providers.py"),
        },
    }
    result["markdown"] = render_methods_graph_substrate_markdown(result)
    return result


def render_methods_graph_substrate_markdown(result: dict[str, Any]) -> str:
    configured = result["configured_graph"]
    surface_rows = [
        f"| {item['name']} | {item['status']} | {item['detail']} |"
        for item in result.get("authoritative_surface", [])
    ]
    aspiration_rows = [f"- {item}" for item in result.get("dogma_execution_aspiration", [])]
    policy_rows = [f"- {item}" for item in result.get("dogma_policy", [])]
    sources = result.get("sources", {})

    return "\n".join(
        [
            "# Dogma Methods-Graph Substrate",
            "",
            "Dogma treats methods-graph as the guardrail substrate for method grounding, workflow validation, and coverage gaps. It does not use methods-graph as a biological truth oracle.",
            "",
            "## Configuration",
            "",
            f"- Status: {result.get('status')}",
            f"- Graph env var: {configured.get('env_var') or 'not configured'}",
            f"- Graph path: {configured.get('path') or 'not configured'}",
            f"- Graph exists: {str(bool(configured.get('exists'))).lower()}",
            f"- Provenance lock: {configured.get('ingest_lock') or 'not configured'}",
            f"- Provenance lock exists: {str(bool(configured.get('ingest_lock_exists'))).lower()}",
            f"- CLI path: {configured.get('cli_path') or 'not found'}",
            "",
            "## Current Guardrail Surface",
            "",
            "| Surface | Status | Detail |",
            "| --- | --- | --- |",
            *surface_rows,
            "",
            "## Dogma Execution Aspiration",
            "",
            *aspiration_rows,
            "",
            "## Dogma Policy",
            "",
            *policy_rows,
            "",
            "## Source Anchors",
            "",
            f"- Dogma monorepo: `{sources.get('dogma_repo')}`",
            f"- methods-graph repo: `{sources.get('methods_graph_repo')}`",
            f"- workflow validator: `{sources.get('methods_graph_workflow_validator')}`",
            f"- append-only ledger: `{sources.get('methods_graph_ledger')}`",
            f"- edge evaluation contract: `{sources.get('edge_evaluation_contract')}`",
            "",
        ]
    )
