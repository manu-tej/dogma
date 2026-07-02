"""Methods-graph substrate report for Dogma.

This keeps methods-graph as an external guardrail authority: Dogma can report
what it expects from the substrate without inventing missing method edges.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Mapping

from .repo_paths import dogma_repo_root, methods_graph_repo_root

METHODS_GRAPH_REPO = methods_graph_repo_root()
DOGMA_REPO = dogma_repo_root()


def env_value(env: Mapping[str, str], names: list[str]) -> tuple[str | None, str | None]:
    for name in names:
        value = env.get(name)
        if value:
            return name, value
    return None, None


def ingest_lock_for(graph_path: str | None) -> str | None:
    if not graph_path:
        return None
    path = Path(graph_path).expanduser()
    candidates = []
    if path.is_dir():
        candidates.append(path / "ingest.lock.json")
        candidates.append(path.parent / "ingest.lock.json")
    else:
        candidates.append(path.parent / "ingest.lock.json")
        candidates.append(path.with_name("ingest.lock.json"))
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())
    return str(candidates[0].resolve()) if candidates else None


def build_methods_graph_substrate(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    values = env or os.environ
    graph_env, graph_path = env_value(values, ["DOGMA_METHODS_GRAPH_DB", "METHODS_GRAPH_DB", "BIOCURSOR_METHODS_GRAPH_DB", "QURATION_METHODS_GRAPH_DB"])
    lock_path = ingest_lock_for(graph_path)
    _, cli_command = env_value(values, ["DOGMA_METHODS_GRAPH_CLI", "BIOCURSOR_METHODS_GRAPH_CLI"])
    cli_path = shutil.which(cli_command or "methods-graph")
    graph_exists = bool(graph_path and Path(graph_path).expanduser().exists())
    lock_exists = bool(lock_path and Path(lock_path).expanduser().exists())

    configured = bool(graph_path)
    audited_ready = configured and graph_exists and lock_exists
    status = "ready" if audited_ready else "configuration_gap" if not configured else "needs_audit_lock"

    result = {
        "service": "dogma-local-service",
        "status": status,
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
                "detail": "Runtime guardrails should come from an audited Kuzu graph plus ingest.lock.json.",
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
        "quration_aspiration": [
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
            "dogma_repo": DOGMA_REPO,
            "methods_graph_repo": METHODS_GRAPH_REPO,
            "quration_repo": DOGMA_REPO,
            "methods_graph_workflow_validator": f"{METHODS_GRAPH_REPO}/src/methods_graph/workflow/validator.py",
            "methods_graph_ledger": f"{METHODS_GRAPH_REPO}/src/methods_graph/workflow/ledger.py",
            "quration_edge_evaluation": f"{DOGMA_REPO}/docs/superpowers/specs/2026-06-19-edge-specific-evaluation-workflow-design.md",
            "quration_llm_provider": f"{DOGMA_REPO}/src/quration/llm/providers.py",
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
    aspiration_rows = [f"- {item}" for item in result.get("quration_aspiration", [])]
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
            f"- Ingest lock: {configured.get('ingest_lock') or 'not configured'}",
            f"- Ingest lock exists: {str(bool(configured.get('ingest_lock_exists'))).lower()}",
            f"- CLI path: {configured.get('cli_path') or 'not found'}",
            "",
            "## Current Guardrail Surface",
            "",
            "| Surface | Status | Detail |",
            "| --- | --- | --- |",
            *surface_rows,
            "",
            "## Quration Aspiration",
            "",
            *aspiration_rows,
            "",
            "## Dogma Policy",
            "",
            *policy_rows,
            "",
            "## Source Anchors",
            "",
            f"- methods-graph repo: `{sources.get('methods_graph_repo')}`",
            f"- quration repo: `{sources.get('quration_repo')}`",
            f"- workflow validator: `{sources.get('methods_graph_workflow_validator')}`",
            f"- append-only ledger: `{sources.get('methods_graph_ledger')}`",
            f"- edge workflow design: `{sources.get('quration_edge_evaluation')}`",
            "",
        ]
    )
