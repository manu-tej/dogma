"""Quration-style edge evaluation plan for Dogma workspaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .execution_sandbox import build_run_plan_for_workspace
from .indexer import scan_workspace
from .method_guardrails import build_method_guardrails
from .methods_graph_substrate import build_methods_graph_substrate


SELECTED_EDGE_FACT_KEYS = {
    "fromMethod",
    "toMethod",
    "fromContainer",
    "toContainer",
    "blockers",
    "warnings",
    "missingContainers",
    "missingMethods",
    "methodCandidates",
    "coverageGaps",
    "readout",
    "contrast",
    "methodsGraphStatus",
    "methodsGraphGrounding",
    "methodsGraphSuggestions",
    "methodsGraphPreconditions",
    "evidencePolicy",
    "assumptions",
}


def sample_id_redactions(scan: dict[str, Any]) -> dict[str, str]:
    ids = scan.get("context", {}).get("samples", {}).get("ids", [])
    if not isinstance(ids, list):
        return {}
    return {str(sample_id): f"<sample:{index}>" for index, sample_id in enumerate(ids, start=1) if sample_id}


def bounded_text(value: Any, limit: int = 240, redactions: dict[str, str] | None = None) -> str:
    text = str(value if value is not None else "")[:limit]
    for raw, alias in (redactions or {}).items():
        text = text.replace(raw, alias)
    return text


def bounded_text_list(value: Any, limit: int = 12, redactions: dict[str, str] | None = None) -> list[str]:
    if not isinstance(value, list):
        return []
    return [bounded_text(item, redactions=redactions) for item in value[:limit] if item is not None]


def sanitize_fact_value(value: Any, redactions: dict[str, str] | None = None, depth: int = 0) -> Any:
    if depth > 3:
        return bounded_text(value, redactions=redactions)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, str):
        return bounded_text(value, redactions=redactions)
    if isinstance(value, list):
        return [sanitize_fact_value(item, redactions=redactions, depth=depth + 1) for item in value[:20]]
    if isinstance(value, dict):
        return {
            bounded_text(key, limit=80, redactions=redactions): sanitize_fact_value(item, redactions=redactions, depth=depth + 1)
            for key, item in list(value.items())[:30]
        }
    return bounded_text(value, redactions=redactions)


def sanitize_selected_edge(selected_edge: dict[str, Any] | None, redactions: dict[str, str] | None = None) -> dict[str, Any] | None:
    if not isinstance(selected_edge, dict):
        return None

    facts = selected_edge.get("facts") if isinstance(selected_edge.get("facts"), dict) else {}
    sanitized_facts: dict[str, Any] = {}
    for key in SELECTED_EDGE_FACT_KEYS:
        if key not in facts:
            continue
        value = facts[key]
        sanitized_facts[key] = sanitize_fact_value(value, redactions=redactions)

    return {
        "id": bounded_text(selected_edge.get("id") or "selected.workflow.edge", redactions=redactions),
        "from": bounded_text(selected_edge.get("from") or "upstream workflow step", redactions=redactions),
        "to": bounded_text(selected_edge.get("to") or "downstream workflow step", redactions=redactions),
        "title": bounded_text(selected_edge.get("title") or "Selected workflow edge", redactions=redactions),
        "status": bounded_text(selected_edge.get("status") or "unknown", redactions=redactions),
        "source": bounded_text(selected_edge.get("source") or "Dogma Graph Workbench", redactions=redactions),
        "edge_type": bounded_text(selected_edge.get("edge_type") or selected_edge.get("edgeType") or "workflow", redactions=redactions),
        "relation": bounded_text(selected_edge.get("relation") or "feeds", redactions=redactions),
        "question": bounded_text(selected_edge.get("question") or "", redactions=redactions),
        "facts": sanitized_facts,
        "next_actions": bounded_text_list(selected_edge.get("nextActions") or selected_edge.get("next_actions"), redactions=redactions),
    }


def plan_status(scan: dict[str, Any], coverage_gaps: list[str]) -> str:
    if scan.get("summary", {}).get("errors", 0):
        return "blocked"
    if coverage_gaps:
        return "coverage_gap"
    if scan.get("summary", {}).get("warnings", 0):
        return "review"
    return "ready"


def infer_task_class(scan: dict[str, Any]) -> str:
    context = scan.get("context", {})
    assay = str(context.get("assay") or "").lower()
    processes = {str(item).upper() for item in context.get("workflow_processes", [])}
    if "rna" in assay or {"ALIGN_STAR", "DESEQ2", "FEATURECOUNTS"} & processes:
        return "differential_expression"
    if context.get("vcf_files"):
        return "variant_review"
    return "workspace_edge_evaluation"


def build_edge(scan: dict[str, Any], task_class: str, selected_edge: dict[str, Any] | None = None) -> dict[str, Any]:
    context = scan.get("context", {})
    conditions = context.get("samples", {}).get("conditions", [])
    condition_label = " vs ".join(conditions[:2]) if len(conditions) >= 2 else "declared condition contrast"
    if selected_edge:
        edge_type = selected_edge.get("edge_type") or "workflow"
        question = selected_edge.get("question") or f"Can the selected {selected_edge['from']} -> {selected_edge['to']} edge be grounded, composed, and gated for {task_class}?"
        return {
            "id": selected_edge["id"],
            "source": selected_edge["from"],
            "relation": selected_edge.get("relation") or "feeds",
            "target": selected_edge["to"],
            "question": question,
            "selection_source": "Dogma Biological Graph" if edge_type == "biological" else "Dogma Graph Workbench",
            "selected_edge_type": edge_type,
            "selected_edge_title": selected_edge["title"],
        }
    if task_class == "differential_expression":
        return {
            "id": "edge.condition_transcript_abundance",
            "source": condition_label,
            "relation": "changes",
            "target": "transcript abundance",
            "question": f"Does {condition_label} change transcript abundance under the declared RNA-seq design?",
        }
    if task_class == "variant_review":
        return {
            "id": "edge.variant_observation_quality",
            "source": "observed variants",
            "relation": "passes",
            "target": "variant quality gates",
            "question": "Do observed variants pass declared quality and provenance gates?",
        }
    return {
        "id": "edge.workspace_analysis_readiness",
        "source": "workspace data",
        "relation": "supports",
        "target": "typed analysis plan",
        "question": "Can this workspace be converted into a grounded typed analysis plan?",
    }


def workflow_process_set(scan: dict[str, Any]) -> set[str]:
    return {str(item).upper() for item in scan.get("context", {}).get("workflow_processes", [])}


def compute_coverage_gaps(scan: dict[str, Any], task_class: str, substrate: dict[str, Any], selected_edge: dict[str, Any] | None = None) -> list[str]:
    context = scan.get("context", {})
    conditions = context.get("samples", {}).get("conditions", [])
    processes = workflow_process_set(scan)
    gaps: list[str] = []

    if substrate.get("status") != "ready":
        gaps.append("methods_graph.audited_substrate_missing")
    if not context.get("sample_file"):
        gaps.append("dataset.sample_sheet_missing")
    if len(conditions) < 2 and task_class == "differential_expression":
        gaps.append("contrast.condition_pair_missing")
    if task_class == "differential_expression":
        for required in ["ALIGN_STAR", "FEATURECOUNTS", "DESEQ2"]:
            if required not in processes:
                gaps.append(f"workflow.process.{required}.missing")
    if context.get("reference", {}).get("genome_build") is None:
        gaps.append("reference.genome_build_missing")
    if context.get("reference", {}).get("annotation") is None and task_class == "differential_expression":
        gaps.append("reference.annotation_missing")
    if selected_edge:
        facts = selected_edge.get("facts", {})
        for gap in facts.get("coverageGaps", []) if isinstance(facts.get("coverageGaps"), list) else []:
            if gap not in gaps:
                gaps.append(gap)
        for method in facts.get("missingMethods", []) if isinstance(facts.get("missingMethods"), list) else []:
            gaps.append(f"selected_edge.method.{method}.missing")
        for container in facts.get("missingContainers", []) if isinstance(facts.get("missingContainers"), list) else []:
            gaps.append(f"selected_edge.container.{container}.missing")
    return gaps


def contract(stage: str, status: str, detail: str, facts: dict[str, Any]) -> dict[str, Any]:
    return {"stage": stage, "status": status, "detail": detail, "facts": facts}


def selected_method_candidates(selected_edge: dict[str, Any] | None, task_class: str) -> list[str]:
    if selected_edge:
        facts = selected_edge.get("facts", {})
        method_candidates = facts.get("methodCandidates")
        if isinstance(method_candidates, list) and method_candidates:
            return [str(item) for item in method_candidates]
        candidates = [
            item
            for item in [facts.get("fromMethod"), facts.get("toMethod")]
            if isinstance(item, str) and item and item != "coverage gap"
        ]
        if candidates:
            return candidates
    return ["m:fastqc", "m:star", "m:featurecounts", "m:deseq2"] if task_class == "differential_expression" else ["coverage_gap"]


def build_contracts(
    scan: dict[str, Any],
    run_plan: dict[str, Any],
    guardrails: dict[str, Any],
    substrate: dict[str, Any],
    task_class: str,
    gaps: list[str],
    selected_edge: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    context = scan.get("context", {})
    samples = context.get("samples", {})
    reference = context.get("reference", {})
    processes = sorted(workflow_process_set(scan))
    guardrail_summary = guardrails.get("summary", {})
    runnable_commands = [
        {
            "id": command.get("id"),
            "command": command.get("command"),
            "mode": command.get("mode"),
            "execution_allowed": command.get("execution_allowed"),
            "blocked_reason": command.get("blocked_reason"),
        }
        for command in run_plan.get("commands", [])
    ]

    readout_status = "coverage_gap" if "contrast.condition_pair_missing" in gaps else "ready"
    compose_status = "blocked" if scan.get("summary", {}).get("errors", 0) else "coverage_gap" if any(gap.startswith("workflow.process") for gap in gaps) else "ready"
    selected_facts = selected_edge.get("facts", {}) if selected_edge else {}
    selected_grounding = selected_facts.get("methodsGraphGrounding") if isinstance(selected_facts.get("methodsGraphGrounding"), dict) else None
    grounding_status = (
        "ready"
        if selected_grounding and selected_grounding.get("status") == "grounded"
        else "coverage_gap"
        if selected_grounding and selected_grounding.get("status") != "grounded"
        else "coverage_gap"
        if substrate.get("status") != "ready"
        else "ready"
    )
    execute_status = "blocked" if run_plan.get("status") == "blocked" else "preview"

    return [
        contract(
            "Readout",
            readout_status,
            "Resolve the biological edge into a measurable readout without deciding whether the edge is true.",
            {
                "task_class": task_class,
                "sample_count": samples.get("count", 0),
                "conditions": samples.get("conditions", []),
                "contrast": selected_facts.get("contrast"),
                "readout": selected_facts.get("readout") or ("transcript abundance" if task_class == "differential_expression" else "typed quality/readiness readout"),
                "directness": "direct assay readout for expression; biological causality remains ungraded",
                "selected_edge": selected_edge,
                "selected_workflow_edge": selected_edge,
            },
        ),
        contract(
            "Grounding",
            grounding_status,
            "Ground method choices and assumptions through methods-graph when an audited substrate is configured.",
            {
                "methods_graph_status": substrate.get("status"),
                "method_candidates": selected_method_candidates(selected_edge, task_class),
                "methods_graph_grounding": selected_grounding,
                "methods_graph_suggestions": selected_facts.get("methodsGraphSuggestions"),
                "methods_graph_preconditions": selected_facts.get("methodsGraphPreconditions"),
                "assumptions": [
                    "Sample metadata defines the contrast.",
                    "Reference genome and annotation match workflow inputs.",
                    "Method/container coverage is available before execution.",
                ],
                "guardrail_summary": guardrail_summary,
            },
        ),
        contract(
            "Compose",
            compose_status,
            "Compose a workflow spec only from known files, method contracts, and declared artifacts.",
            {
                "workflow_processes": processes,
                "missing_workflow_processes": [gap.removeprefix("workflow.process.").removesuffix(".missing") for gap in gaps if gap.startswith("workflow.process.")],
                "workflow_files": context.get("workflow_files", []),
                "coverage_gaps": gaps,
                "selected_edge": selected_edge,
                "selected_workflow_edge": selected_edge,
            },
        ),
        contract(
            "Execute",
            execute_status,
            "Execution remains dry-run/stub-run and explicit until validation, trust, provenance, and coverage gates pass.",
            {
                "run_plan_status": run_plan.get("status"),
                "execution_allowed": run_plan.get("execution_allowed"),
                "commands": runnable_commands,
                "trust": scan.get("trust", {}),
            },
        ),
        contract(
            "Interpret",
            "facts_only",
            "Interpretation records factual evidence records, caveats, assumptions, and provenance; it does not emit support/refute verdicts.",
            {
                "stores_biological_verdicts": False,
                "stores_confidence_grades": False,
                "evidence_record_fields": ["edge_id", "readout", "method", "artifacts", "parameters", "observations", "caveats", "provenance"],
                "reference": {"genome_build": reference.get("genome_build"), "annotation": reference.get("annotation")},
            },
        ),
    ]


def summarize_contracts(contracts: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {"total": len(contracts)}
    for item in contracts:
        status = item.get("status", "unknown")
        summary[status] = summary.get(status, 0) + 1
    return summary


def escape_table_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")


def render_edge_evaluation_plan_markdown(result: dict[str, Any]) -> str:
    edge = result.get("edge", {})
    selected_edge = result.get("selected_edge")
    rows = [
        f"| {item['stage']} | {item['status']} | {escape_table_cell(item['detail'])} |"
        for item in result.get("contracts", [])
    ]
    gaps = [f"- {gap}" for gap in result.get("coverage_gaps", [])] or ["- none"]
    next_actions = [f"- {item}" for item in result.get("next_actions", [])]
    parts = [
            "# Dogma Edge Evaluation Plan",
            "",
            "This is a typed plan for evaluating one biological edge. It is not a biological verdict.",
            "",
            "## Edge",
            "",
            f"- ID: {edge.get('id')}",
            f"- Question: {edge.get('question')}",
            f"- Source: {edge.get('source')}",
            f"- Relation: {edge.get('relation')}",
            f"- Target: {edge.get('target')}",
            f"- Status: {result.get('status')}",
            "",
    ]
    if selected_edge:
        facts = selected_edge.get("facts", {})
        heading = "Selected Biological Edge" if selected_edge.get("edge_type") == "biological" else "Selected Workbench Edge"
        parts.extend(
            [
                f"## {heading}",
                "",
                f"- Title: {selected_edge.get('title')}",
                f"- Status: {selected_edge.get('status')}",
                f"- Source: {selected_edge.get('source')}",
                f"- Relation: {selected_edge.get('relation')}",
                f"- Question: {selected_edge.get('question') or edge.get('question')}",
                f"- Readout: {facts.get('readout', 'not declared')}",
                f"- Method candidates: {', '.join(facts.get('methodCandidates') or []) or 'not grounded'}",
                f"- Methods-graph grounding: {(facts.get('methodsGraphGrounding') or {}).get('status', facts.get('methodsGraphStatus', 'not configured'))}",
                f"- From method: {facts.get('fromMethod', 'not grounded')}",
                f"- To method: {facts.get('toMethod', 'not grounded')}",
                f"- Missing containers: {', '.join(facts.get('missingContainers') or []) or 'none'}",
                f"- Missing methods: {', '.join(facts.get('missingMethods') or []) or 'none'}",
                "",
            ]
        )
    parts.extend(
        [
            "## Contracts",
            "",
            "| Stage | Status | Detail |",
            "| --- | --- | --- |",
            *rows,
            "",
            "## Coverage Gaps",
            "",
            *gaps,
            "",
            "## Next Actions",
            "",
            *next_actions,
            "",
            "## Invariants",
            "",
            "- Stores support/refute verdicts: false",
            "- Stores confidence grades: false",
            "- Requires explicit execution gates: true",
            "- Treats missing method/data/container/contrast coverage as a gap: true",
            "",
        ]
    )
    return "\n".join(parts)


def build_edge_evaluation_plan(root: str | Path, max_files: int = 500, selected_edge: dict[str, Any] | None = None) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    scan = scan_workspace(root_path, max_files=max_files)
    run_plan = build_run_plan_for_workspace(root_path, max_files=max_files)
    guardrails = build_method_guardrails(root_path, max_files=max_files)
    substrate = build_methods_graph_substrate()
    task_class = infer_task_class(scan)
    selected = sanitize_selected_edge(selected_edge, redactions=sample_id_redactions(scan))
    edge = build_edge(scan, task_class, selected)
    gaps = compute_coverage_gaps(scan, task_class, substrate, selected)
    contracts = build_contracts(scan, run_plan, guardrails, substrate, task_class, gaps, selected)
    status = plan_status(scan, gaps)
    result = {
        "service": "dogma-local-service",
        "root": str(root_path),
        "status": status,
        "task_class": task_class,
        "edge": edge,
        "selected_edge": selected,
        "summary": summarize_contracts(contracts),
        "coverage_gaps": gaps,
        "contracts": contracts,
        "next_actions": [
            "Fix blocked Dogma findings before composing an executable workflow spec." if scan.get("summary", {}).get("errors", 0) else "Review warning-level findings before execution.",
            "Configure an audited methods-graph database plus ingest.lock.json for stronger method grounding." if substrate.get("status") != "ready" else "Use audited methods-graph grounding for method and assumption checks.",
            "Add missing workflow steps or explicit coverage-gap records before real execution." if any(gap.startswith("workflow.process") for gap in gaps) else "Keep workflow expansion behind explicit review and dry-run gates.",
            "Record only factual observations and provenance after execution.",
        ],
        "invariants": {
            "stores_biological_verdicts": False,
            "stores_confidence_grades": False,
            "explicit_execution_gates": True,
            "coverage_gaps_are_explicit": True,
        },
    }
    result["markdown"] = render_edge_evaluation_plan_markdown(result)
    return result
