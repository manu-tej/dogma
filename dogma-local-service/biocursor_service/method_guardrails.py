"""Quration- and methods-graph-inspired guardrails for Dogma workspaces."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .assistant_context import build_assistant_context
from .execution_sandbox import build_run_plan_for_workspace
from .indexer import read_text_limited, scan_workspace
from .patch_proposals import build_patch_proposals
from .repo_paths import dogma_repo_root, methods_graph_repo_root

DOGMA_REPO = dogma_repo_root()
METHODS_GRAPH_REPO = methods_graph_repo_root()
QURATION_NORTH_STAR = str(Path(DOGMA_REPO) / "docs" / "superpowers" / "specs" / "2026-06-18-agentic-compbio-north-star.md")
METHODS_GRAPH_VALIDATOR = str(Path(METHODS_GRAPH_REPO) / "src" / "methods_graph" / "workflow" / "validator.py")

PROCESS_METHOD_CATALOG: dict[str, dict[str, Any]] = {
    "FASTQC": {
        "method_id": "m:fastqc",
        "operation": "sequencing quality control",
        "inputs": ["FASTQ reads"],
        "outputs": ["QC report"],
        "assumptions": ["Input FASTQ files exist and correspond to declared samples."],
    },
    "ALIGN_STAR": {
        "method_id": "m:star",
        "operation": "splice-aware RNA-seq alignment",
        "inputs": ["paired FASTQ reads", "reference genome index"],
        "outputs": ["BAM alignment"],
        "assumptions": ["Genome build and annotation are declared before interpreting alignments."],
        "requires_reference": True,
    },
    "MULTIQC": {
        "method_id": "m:multiqc",
        "operation": "aggregate sequencing QC",
        "inputs": ["tool QC outputs"],
        "outputs": ["combined QC report"],
        "assumptions": ["Upstream tool outputs are versioned and attributable to samples."],
    },
    "DESEQ2": {
        "method_id": "m:deseq2",
        "operation": "differential expression",
        "inputs": ["count matrix", "sample contrasts"],
        "outputs": ["effect sizes and adjusted p-values"],
        "assumptions": ["Replicates and contrast definitions are declared before interpretation."],
    },
}


def line_number_at(text: str, index: int) -> int:
    return text[:index].count("\n") + 1


def extract_nextflow_processes(root: Path, workflow_files: list[str]) -> list[dict[str, Any]]:
    processes: list[dict[str, Any]] = []
    for workflow_file in workflow_files:
        if not workflow_file.lower().endswith(".nf"):
            continue
        path = root / workflow_file
        if not path.exists():
            continue
        text, _ = read_text_limited(path)
        for match in re.finditer(r"(?ms)^\s*process\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{(.*?)^\s*\}", text):
            name = match.group(1)
            body = match.group(2)
            container_match = re.search(r"(?m)^\s*container\s+['\"]?([^'\"\n]+)", body)
            processes.append(
                {
                    "name": name,
                    "file": workflow_file,
                    "line": line_number_at(text, match.start()),
                    "container": container_match.group(1).strip() if container_match else None,
                    "method_contract": PROCESS_METHOD_CATALOG.get(name),
                }
            )
    return processes


def add_check(checks: list[dict[str, Any]], code: str, status: str, detail: str, principle: str, evidence: dict[str, Any] | None = None) -> None:
    checks.append(
        {
            "code": code,
            "status": status,
            "detail": detail,
            "principle": principle,
            "evidence": evidence or {},
        }
    )


def summarize_checks(checks: list[dict[str, Any]]) -> dict[str, int]:
    statuses = {"pass": 0, "warning": 0, "gap": 0, "blocked": 0}
    for check in checks:
        status = check.get("status", "warning")
        statuses[status] = statuses.get(status, 0) + 1
    return statuses


def escape_table_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def build_guardrail_checks(scan: dict[str, Any], run_plan: dict[str, Any], assistant: dict[str, Any], patches: dict[str, Any], processes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    context = scan.get("context", {})
    summary = scan.get("summary", {})
    trust = scan.get("trust", {})
    reference = context.get("reference", {})

    add_check(
        checks,
        "quration.factual_ledger_not_verdict",
        "pass",
        "Dogma records findings, guardrail checks, proposals, and execution previews as facts; it does not mark biological claims as supported or refuted.",
        "quration: evidence ledgers are facts, never verdicts or grades",
        {"issues": len(scan.get("issues", [])), "patch_proposals": patches.get("proposal_count", 0)},
    )

    if run_plan.get("commands"):
        unsafe = [command for command in run_plan.get("commands", []) if "-stub-run" not in command.get("command", "") and "--dry-run" not in command.get("command", "")]
        add_check(
            checks,
            "methods_graph.compose_before_execute",
            "pass" if not unsafe else "blocked",
            "Runnable commands are advisory dry-run/stub-run previews before any explicit execution request." if not unsafe else "At least one proposed command is not a dry-run/stub-run command.",
            "methods-graph: planning and validation happen before execution",
            {"commands": [command.get("command") for command in run_plan.get("commands", [])], "unsafe": unsafe},
        )
    else:
        add_check(
            checks,
            "methods_graph.compose_before_execute",
            "gap",
            "No workflow dry-run/stub-run command could be composed for this workspace.",
            "methods-graph: execution requires a validated workflow spec",
            {"run_plan_status": run_plan.get("status")},
        )

    if trust.get("human_data") and not trust.get("trusted"):
        add_check(
            checks,
            "privacy.human_data_trust_gate_active",
            "pass",
            "Human data is detected and local execution/patch application remains gated until workspace trust is explicit.",
            "quration: PHI/data-access governance is a named execution-substrate concern",
            {"trust_status": trust.get("status"), "blockers": trust.get("blockers", [])},
        )
    else:
        add_check(
            checks,
            "privacy.human_data_trust_gate_active",
            "pass",
            "No untrusted human-data execution gap is active for this scan.",
            "quration: PHI/data-access governance is a named execution-substrate concern",
            {"trust_status": trust.get("status"), "human_data": trust.get("human_data")},
        )

    add_check(
        checks,
        "privacy.assistant_context_redaction",
        "pass" if assistant.get("redaction", {}).get("sample_ids_redacted") or not trust.get("human_data") or trust.get("trusted") else "blocked",
        "Assistant context redacts sample identifiers when human data is untrusted; trusted/non-human workspaces can disclose according to policy.",
        "quration: local context is useful only when disclosure boundaries are explicit",
        assistant.get("redaction", {}),
    )

    if context.get("workflow_files"):
        add_check(
            checks,
            "workflow.graph_present",
            "pass",
            "Workflow files were indexed and can be rendered as a graph/report before edits or execution.",
            "quration: graph plus chat drive the same workflow engine",
            {"workflow_files": context.get("workflow_files"), "workflow_processes": context.get("workflow_processes", [])},
        )
    else:
        add_check(
            checks,
            "workflow.graph_present",
            "gap",
            "No workflow files were indexed, so no workflow graph can be reviewed.",
            "quration: graph plus chat drive the same workflow engine",
        )

    if not processes:
        add_check(
            checks,
            "methods_graph.method_contracts",
            "gap",
            "No Nextflow process blocks were found to map to method contracts.",
            "methods-graph: every step should ground to a method contract",
        )

    for process in processes:
        contract = process.get("method_contract")
        location = f"{process['file']}:{process['line']}"
        if contract:
            add_check(
                checks,
                f"method.grounded.{process['name']}",
                "pass",
                f"{process['name']} maps to {contract['operation']} ({contract['method_id']}).",
                "methods-graph: a workflow step should resolve to a grounded Method node",
                {"location": location, "contract": contract},
            )
            if contract.get("requires_reference"):
                status = "pass" if reference.get("genome_build") else "gap"
                add_check(
                    checks,
                    f"method.reference_contract.{process['name']}",
                    status,
                    "Reference genome build is declared for this alignment contract." if status == "pass" else "Alignment contract needs a declared reference genome build.",
                    "methods-graph: method assumptions must be surfaced and checked",
                    {"location": location, "genome_build": reference.get("genome_build"), "annotation": reference.get("annotation")},
                )
                if not reference.get("annotation"):
                    add_check(
                        checks,
                        f"method.annotation_contract.{process['name']}",
                        "warning",
                        "Genome build is present, but annotation release is missing; interpretation should record this as an assumption gap.",
                        "quration: assumption outcomes are recorded, never hidden",
                        {"location": location},
                    )
        else:
            add_check(
                checks,
                f"method.coverage_gap.{process['name']}",
                "gap",
                f"{process['name']} has no local Dogma method contract yet; treat it as a coverage gap, not as an inferred method.",
                "quration: honest COVERAGE_GAP when no grounded method exists",
                {"location": location},
            )

        if process.get("container"):
            add_check(
                checks,
                f"method.container.{process['name']}",
                "pass",
                f"{process['name']} declares container {process['container']}.",
                "methods-graph: method execution should resolve to a concrete executor/container",
                {"location": location, "container": process.get("container")},
            )
        else:
            add_check(
                checks,
                f"method.container.{process['name']}",
                "gap",
                f"{process['name']} does not declare a container; execution provenance would be incomplete.",
                "methods-graph: method execution should resolve to a concrete executor/container",
                {"location": location},
            )

    if summary.get("errors", 0):
        add_check(
            checks,
            "workflow.error_findings_block_execution",
            "blocked",
            "Error-level Dogma findings remain; real workflow execution must stay blocked.",
            "methods-graph: validation result gates execution",
            {"errors": summary.get("errors"), "risk_level": summary.get("risk_level")},
        )
    else:
        add_check(
            checks,
            "workflow.error_findings_block_execution",
            "pass",
            "No error-level Dogma findings are currently reported.",
            "methods-graph: validation result gates execution",
            {"risk_level": summary.get("risk_level")},
        )

    return checks


def render_guardrails_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    checks = result["checks"]
    process_rows = [
        f"| {step['name']} | {step['file']}:{step['line']} | {(step.get('method_contract') or {}).get('method_id', 'coverage gap')} | {step.get('container') or 'missing'} |"
        for step in result.get("workflow_steps", [])
    ] or ["| none | none | none | none |"]
    check_rows = [
        f"| {check['status']} | {check['code']} | {check['principle']} | {escape_table_cell(check['detail'])} |"
        for check in checks
    ]

    return "\n".join(
        [
            "# Dogma Method Guardrails",
            "",
            "## Source Philosophy",
            "",
            f"- Quration north star: `{result['sources']['quration_north_star']}`",
            f"- Methods-graph validator: `{result['sources']['methods_graph_validator']}`",
            "",
            "Dogma should act like a Cursor-style compbio workbench: graph and chat drive the same workflow substrate, method grounding is a safety rail, findings are factual ledger entries rather than verdicts, and execution only follows validated dry-run/trust gates.",
            "",
            "## Summary",
            "",
            f"- Pass: {summary.get('pass', 0)}",
            f"- Warning: {summary.get('warning', 0)}",
            f"- Gap: {summary.get('gap', 0)}",
            f"- Blocked: {summary.get('blocked', 0)}",
            "",
            "## Workflow Steps",
            "",
            "| Process | Location | Method contract | Container |",
            "| --- | --- | --- | --- |",
            *process_rows,
            "",
            "## Guardrail Checks",
            "",
            "| Status | Code | Principle | Detail |",
            "| --- | --- | --- | --- |",
            *check_rows,
            "",
            "## Next Dogma Implications",
            "",
            "- Treat missing method contracts as coverage gaps, not inferred support.",
            "- Keep patch proposals and workflow expansion advisory until explicitly selected and reviewed.",
            "- Record assumptions, resource profile, container, dataset/contrast, and provenance before any real execution path.",
            "- Never collapse diagnostics or analysis output into a biological support/refute verdict.",
            "",
        ]
    )


def build_method_guardrails(root: str | Path, max_files: int = 500) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    scan = scan_workspace(root_path, max_files=max_files)
    run_plan = build_run_plan_for_workspace(root_path, max_files=max_files)
    assistant = build_assistant_context(root_path, max_files=max_files)
    patches = build_patch_proposals(root_path, max_files=max_files)
    processes = extract_nextflow_processes(root_path, scan.get("context", {}).get("workflow_files", []))
    checks = build_guardrail_checks(scan, run_plan, assistant, patches, processes)
    result = {
        "service": "dogma-local-service",
        "root": str(root_path),
        "sources": {
            "quration_north_star": QURATION_NORTH_STAR,
            "methods_graph_validator": METHODS_GRAPH_VALIDATOR,
        },
        "summary": summarize_checks(checks),
        "workflow_steps": processes,
        "checks": checks,
        "scan_summary": scan.get("summary", {}),
        "trust": scan.get("trust", {}),
    }
    result["markdown"] = render_guardrails_markdown(result)
    return result
