"""Factual Dogma evidence ledger.

The ledger records what Dogma observed, planned, proposed, and gated. It does
not decide whether a biological claim is supported or refuted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .assistant_context import build_assistant_context
from .execution_sandbox import build_run_plan_for_workspace
from .method_guardrails import build_method_guardrails
from .patch_proposals import build_patch_proposals


def entry(entry_id: str, entry_type: str, status: str, title: str, facts: dict[str, Any], source: str) -> dict[str, Any]:
    return {
        "id": entry_id,
        "type": entry_type,
        "status": status,
        "title": title,
        "facts": facts,
        "source": source,
    }


def finding_status(severity: str) -> str:
    if severity == "error":
        return "blocked"
    if severity == "warning":
        return "warning"
    return "info"


def risk_status(risk_level: str | None) -> str:
    return {
        "blocked": "blocked",
        "review": "warning",
        "ready": "pass",
    }.get(str(risk_level or ""), "info")


def ledger_summary(entries: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"total": len(entries), "blocked": 0, "warning": 0, "gap": 0, "pass": 0, "info": 0, "preview": 0}
    for item in entries:
        status = item.get("status", "info")
        summary[status] = summary.get(status, 0) + 1
    return summary


def patch_proposal_facts(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposal_id": proposal.get("id"),
        "kind": proposal.get("kind"),
        "target_file": proposal.get("target_file"),
        "severity": proposal.get("severity"),
        "rationale": proposal.get("rationale"),
        "safety": proposal.get("safety", {}),
    }


def command_facts(command: dict[str, Any]) -> dict[str, Any]:
    return {
        "command_id": command.get("id"),
        "engine": command.get("engine"),
        "workflow_file": command.get("workflow_file"),
        "mode": command.get("mode"),
        "command": command.get("command"),
        "tool_available": command.get("tool_available"),
        "execution_allowed": command.get("execution_allowed"),
        "blocked_reason": command.get("blocked_reason"),
        "requires_review": command.get("requires_review"),
    }


def build_entries(assistant: dict[str, Any], guardrails: dict[str, Any], run_plan: dict[str, Any], patches: dict[str, Any]) -> list[dict[str, Any]]:
    context = assistant.get("context", {})
    summary = assistant.get("summary", {})
    samples = context.get("samples", {})
    reference = context.get("reference", {})
    entries: list[dict[str, Any]] = [
        entry(
            "workspace-context",
            "workspace_context",
            risk_status(summary.get("risk_level")),
            "Workspace context extracted from parsed bioinformatics files.",
            {
                "risk_level": summary.get("risk_level"),
                "errors": summary.get("errors", 0),
                "warnings": summary.get("warnings", 0),
                "sample_file": context.get("sample_file"),
                "sample_count": samples.get("count", 0),
                "sample_ids": samples.get("ids", []),
                "conditions": samples.get("conditions", []),
                "strandedness": samples.get("strandedness", []),
                "genome_build": reference.get("genome_build"),
                "annotation": reference.get("annotation"),
                "workflow_files": context.get("workflow_files", []),
                "workflow_processes": context.get("workflow_processes", []),
                "bed_files": [item.get("path") for item in context.get("bed_files", [])],
                "vcf_files": [item.get("path") for item in context.get("vcf_files", [])],
            },
            "assistant-context",
        ),
        entry(
            "privacy-boundary",
            "privacy",
            "pass" if assistant.get("redaction", {}).get("sample_ids_redacted") or not assistant.get("trust", {}).get("human_data") or assistant.get("trust", {}).get("trusted") else "blocked",
            "Privacy boundary for assistant and ledger context.",
            {
                "trust": assistant.get("trust", {}),
                "redaction": assistant.get("redaction", {}),
            },
            "assistant-context",
        ),
        entry(
            "run-plan",
            "execution_plan",
            run_plan.get("status", "info"),
            "Workflow execution plan is dry-run/stub-run only until explicitly executed.",
            {
                "execution_allowed": run_plan.get("execution_allowed"),
                "error_count": run_plan.get("error_count"),
                "warning_count": run_plan.get("warning_count"),
                "commands": [command_facts(command) for command in run_plan.get("commands", [])],
                "safety_notes": run_plan.get("safety_notes", []),
            },
            "run-plan",
        ),
    ]

    for index, issue in enumerate(assistant.get("issues", []), start=1):
        entries.append(
            entry(
                f"finding-{index}",
                "finding",
                finding_status(issue.get("severity", "info")),
                issue.get("message", "Dogma finding."),
                {
                    "severity": issue.get("severity"),
                    "code": issue.get("code"),
                    "file": issue.get("file"),
                    "line": issue.get("line"),
                    "message": issue.get("message"),
                },
                "scan",
            )
        )

    for index, check in enumerate(guardrails.get("checks", []), start=1):
        entries.append(
            entry(
                f"guardrail-{index}",
                "guardrail_check",
                check.get("status", "warning"),
                check.get("detail", "Dogma guardrail check."),
                {
                    "code": check.get("code"),
                    "principle": check.get("principle"),
                    "detail": check.get("detail"),
                    "evidence": check.get("evidence", {}),
                },
                "guardrails",
            )
        )

    for index, proposal in enumerate(patches.get("proposals", []), start=1):
        entries.append(
            entry(
                f"patch-proposal-{index}",
                "patch_proposal",
                "preview",
                proposal.get("title", proposal.get("id", "Dogma patch proposal")),
                patch_proposal_facts(proposal),
                "patch-proposals",
            )
        )

    return entries


def escape_table_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def render_ledger_markdown(result: dict[str, Any]) -> str:
    summary = result.get("summary", {})
    rows = [
        f"| {item['status']} | {item['type']} | {item['id']} | {escape_table_cell((item.get('facts') or {}).get('code') or (item.get('facts') or {}).get('proposal_id') or '')} | {escape_table_cell(item['title'])} | {item['source']} |"
        for item in result.get("entries", [])
    ]
    invariants = result.get("invariants", {})
    return "\n".join(
        [
            "# Dogma Evidence Ledger",
            "",
            "This is a factual ledger of workspace observations, guardrails, proposals, and execution gates. It is not a biological verdict system.",
            "",
            "## Invariants",
            "",
            f"- Stores support/refute verdicts: {str(bool(invariants.get('stores_biological_verdicts'))).lower()}",
            f"- Stores confidence grades: {str(bool(invariants.get('stores_confidence_grades'))).lower()}",
            f"- Uses sample ID redaction: {str(bool(invariants.get('sample_ids_redacted'))).lower()}",
            f"- Requires explicit execution/apply gates: {str(bool(invariants.get('explicit_gates_required'))).lower()}",
            "",
            "## Summary",
            "",
            f"- Total entries: {summary.get('total', 0)}",
            f"- Blocked: {summary.get('blocked', 0)}",
            f"- Warning: {summary.get('warning', 0)}",
            f"- Gap: {summary.get('gap', 0)}",
            f"- Pass: {summary.get('pass', 0)}",
            f"- Preview: {summary.get('preview', 0)}",
            f"- Info: {summary.get('info', 0)}",
            "",
            "## Entries",
            "",
            "| Status | Type | ID | Code | Title | Source |",
            "| --- | --- | --- | --- | --- | --- |",
            *rows,
            "",
            "## Use",
            "",
            "- Use this ledger as the evidence handoff to an AI coding assistant.",
            "- Treat blocked/gap entries as work items, not as biological conclusions.",
            "- Add real execution records only after dry-run, trust, validation, container, and provenance requirements are satisfied.",
            "",
        ]
    )


def build_evidence_ledger(root: str | Path, max_files: int = 500) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    assistant = build_assistant_context(root_path, max_files=max_files)
    guardrails = build_method_guardrails(root_path, max_files=max_files)
    run_plan = build_run_plan_for_workspace(root_path, max_files=max_files)
    patches = build_patch_proposals(root_path, max_files=max_files)
    entries = build_entries(assistant, guardrails, run_plan, patches)
    invariants = {
        "stores_biological_verdicts": False,
        "stores_confidence_grades": False,
        "sample_ids_redacted": bool(assistant.get("redaction", {}).get("sample_ids_redacted")),
        "explicit_gates_required": True,
        "deterministic_without_timestamp": True,
    }
    result = {
        "service": "dogma-local-service",
        "root": str(root_path),
        "invariants": invariants,
        "summary": ledger_summary(entries),
        "entries": entries,
    }
    result["markdown"] = render_ledger_markdown(result)
    return result
