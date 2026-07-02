"""Biological graph projection for Dogma workspaces.

This graph is a planning surface. Edges describe measurable biological questions
and guardrail gaps; they do not assert biological truth.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .edge_evaluation_plan import compute_coverage_gaps, infer_task_class, sample_id_redactions
from .methods_graph_grounding import dedupe, ground_edge_with_methods_graph
from .indexer import scan_workspace
from .methods_graph_substrate import build_methods_graph_substrate


def graph_status(scan: dict[str, Any], gaps: list[str]) -> str:
    if scan.get("summary", {}).get("errors", 0):
        return "blocked"
    if gaps:
        return "coverage_gap"
    if scan.get("summary", {}).get("warnings", 0):
        return "review"
    return "ready"


def contrast_label(scan: dict[str, Any]) -> str:
    conditions = scan.get("context", {}).get("samples", {}).get("conditions", [])
    if isinstance(conditions, list) and len(conditions) >= 2:
        return " vs ".join(str(item) for item in conditions[:2])
    return "declared condition contrast"


def method_candidates(task_class: str) -> list[str]:
    if task_class == "differential_expression":
        return ["m:fastqc", "m:star", "m:featurecounts", "m:deseq2"]
    if task_class == "variant_review":
        return ["coverage_gap:variant_qc_methods"]
    return ["coverage_gap:analysis_methods"]


def node(node_id: str, label: str, kind: str, status: str, facts: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": node_id,
        "label": label,
        "kind": kind,
        "status": status,
        "facts": facts or {},
    }


def selected_edge_payload(edge: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": edge["id"],
        "from": edge["source"],
        "to": edge["target"],
        "title": edge["title"],
        "status": edge["status"],
        "source": "Dogma Biological Graph",
        "edge_type": "biological",
        "relation": edge["relation"],
        "question": edge["question"],
        "facts": {
            "readout": edge["facts"].get("readout"),
            "contrast": edge["facts"].get("contrast"),
            "methodCandidates": edge["facts"].get("method_candidates", []),
            "coverageGaps": edge["facts"].get("coverage_gaps", []),
            "methodsGraphStatus": edge["facts"].get("methods_graph_status"),
            "methodsGraphGrounding": edge["facts"].get("methods_graph_grounding"),
            "evidencePolicy": "facts_only_no_support_refute_verdicts",
            "assumptions": edge["facts"].get("assumptions", []),
        },
        "nextActions": edge.get("next_actions", []),
    }


def biological_edge(
    edge_id: str,
    source: str,
    relation: str,
    target: str,
    question: str,
    status: str,
    facts: dict[str, Any],
    next_actions: list[str],
) -> dict[str, Any]:
    edge = {
        "id": edge_id,
        "title": f"{source} -> {target}",
        "source": source,
        "relation": relation,
        "target": target,
        "question": question,
        "status": status,
        "facts": facts,
        "next_actions": next_actions,
    }
    edge["selected_edge"] = selected_edge_payload(edge)
    return edge


def build_biological_edges(scan: dict[str, Any], substrate: dict[str, Any], task_class: str, gaps: list[str]) -> list[dict[str, Any]]:
    status = graph_status(scan, gaps)
    context = scan.get("context", {})
    reference = context.get("reference", {})
    contrast = contrast_label(scan)
    methods = method_candidates(task_class)
    common_facts = {
        "sample_count": context.get("samples", {}).get("count", 0),
        "conditions": context.get("samples", {}).get("conditions", []),
        "reference": {"genome_build": reference.get("genome_build"), "annotation": reference.get("annotation")},
        "methods_graph_status": substrate.get("status"),
        "method_candidates": methods,
        "coverage_gaps": gaps,
        "assumptions": [
            "Sample metadata defines the contrast.",
            "Reference genome and annotation match workflow inputs.",
            "methods-graph grounding is required before execution claims.",
        ],
    }

    if task_class == "differential_expression":
        return [
            biological_edge(
                "bioedge.condition_transcript_abundance",
                contrast,
                "changes",
                "transcript abundance",
                f"Does {contrast} change transcript abundance under the declared RNA-seq design?",
                status,
                {**common_facts, "contrast": contrast, "readout": "transcript abundance"},
                [
                    "Resolve Dogma error findings before composing an executable workflow.",
                    "Ground RNA-seq methods and assumptions in an audited methods-graph substrate.",
                    "Record observations as factual evidence, not support/refute verdicts.",
                ],
            )
        ]

    if task_class == "variant_review":
        return [
            biological_edge(
                "bioedge.variant_observation_quality",
                "observed variants",
                "passes",
                "variant quality gates",
                "Do observed variants pass declared quality and provenance gates?",
                status,
                {**common_facts, "readout": "variant quality/provenance"},
                [
                    "Declare variant review methods before interpretation.",
                    "Ground quality gates in methods-graph before execution.",
                    "Keep observations factual and provenance-linked.",
                ],
            )
        ]

    return [
        biological_edge(
            "bioedge.workspace_analysis_readiness",
            "workspace data",
            "supports",
            "typed analysis plan",
            "Can this workspace be converted into a grounded typed analysis plan?",
            status,
            {**common_facts, "readout": "analysis readiness"},
            [
                "Add sample, reference, workflow, and method declarations.",
                "Treat missing graph coverage as work items.",
                "Keep assistant proposals behind review gates.",
            ],
        )
    ]


def build_nodes(scan: dict[str, Any], substrate: dict[str, Any], task_class: str, gaps: list[str]) -> list[dict[str, Any]]:
    context = scan.get("context", {})
    samples = context.get("samples", {})
    reference = context.get("reference", {})
    status = graph_status(scan, gaps)
    contrast_status = "coverage_gap" if "contrast.condition_pair_missing" in gaps else "ready"
    reference_status = "coverage_gap" if any(gap.startswith("reference.") for gap in gaps) else "ready"
    method_status = "coverage_gap" if substrate.get("status") != "ready" or any(gap.startswith("workflow.process.") for gap in gaps) else "ready"

    return [
        node(
            "dataset:samples",
            "Samples",
            "dataset",
            "ready" if context.get("sample_file") else "coverage_gap",
            {"sample_count": samples.get("count", 0), "conditions": samples.get("conditions", []), "sample_ids_redacted": bool(sample_id_redactions(scan))},
        ),
        node("contrast:declared", contrast_label(scan), "contrast", contrast_status, {"conditions": samples.get("conditions", [])}),
        node(
            "readout:primary",
            "Transcript abundance" if task_class == "differential_expression" else "Primary typed readout",
            "readout",
            status,
            {"task_class": task_class},
        ),
        node(
            "reference:declared",
            "Reference",
            "reference",
            reference_status,
            {"genome_build": reference.get("genome_build"), "annotation": reference.get("annotation")},
        ),
        node(
            "methods:grounding",
            "Method grounding",
            "methods_graph",
            method_status,
            {"methods_graph_status": substrate.get("status"), "method_candidates": method_candidates(task_class)},
        ),
        node(
            "execution:gates",
            "Execution gates",
            "guardrail",
            "blocked" if scan.get("summary", {}).get("errors", 0) else "preview",
            {"risk_level": scan.get("summary", {}).get("risk_level"), "trust": scan.get("trust", {}).get("status")},
        ),
    ]


def summarize(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], gaps: list[str]) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    for item in [*nodes, *edges]:
        status = item.get("status", "unknown")
        statuses[status] = statuses.get(status, 0) + 1
    return {
        "nodes": len(nodes),
        "edges": len(edges),
        "coverage_gaps": len(gaps),
        "statuses": statuses,
    }


def merge_grounding_into_edge(edge: dict[str, Any], grounding: dict[str, Any]) -> dict[str, Any]:
    facts = edge.setdefault("facts", {})
    facts["methods_graph_grounding"] = grounding
    facts["methods_graph_status"] = grounding.get("status") or facts.get("methods_graph_status")
    chosen = grounding.get("chosen_method_ids") or []
    if chosen:
        facts["method_candidates"] = dedupe([*facts.get("method_candidates", []), *chosen])
    facts["coverage_gaps"] = dedupe([*facts.get("coverage_gaps", []), *grounding.get("coverage_gaps", [])])
    if grounding.get("suggestions"):
        facts["methods_graph_suggestions"] = grounding.get("suggestions", [])
    if grounding.get("preconditions"):
        facts["methods_graph_preconditions"] = grounding.get("preconditions", [])
    edge["methods_graph_grounding"] = grounding
    if grounding.get("status") == "grounded" and edge.get("status") == "coverage_gap":
        edge["status"] = "ready"
    edge["selected_edge"] = selected_edge_payload(edge)
    return edge


def render_biological_graph_markdown(result: dict[str, Any]) -> str:
    node_rows = [
        f"| {item['id']} | {item['kind']} | {item['status']} | {item['label']} |"
        for item in result.get("nodes", [])
    ]
    edge_rows = [
        f"| {item['id']} | {item['status']} | {item['source']} | {item['relation']} | {item['target']} |"
        for item in result.get("edges", [])
    ]
    gaps = [f"- {gap}" for gap in result.get("coverage_gaps", [])] or ["- none"]
    grounding_rows = [
        f"| {item['id']} | {item.get('methods_graph_grounding', {}).get('status', 'unknown')} | {', '.join(item.get('methods_graph_grounding', {}).get('chosen_method_ids', [])) or 'none'} | {', '.join(item.get('methods_graph_grounding', {}).get('coverage_gaps', [])) or 'none'} |"
        for item in result.get("edges", [])
    ]
    return "\n".join(
        [
            "# Dogma Biological Graph",
            "",
            "This graph models measurable biological edges for planning. It does not store support/refute verdicts.",
            "",
            f"- Status: {result.get('status')}",
            f"- Task class: {result.get('task_class')}",
            f"- Methods-graph status: {result.get('methods_graph_status')}",
            "",
            "## Nodes",
            "",
            "| ID | Kind | Status | Label |",
            "| --- | --- | --- | --- |",
            *node_rows,
            "",
            "## Edges",
            "",
            "| ID | Status | Source | Relation | Target |",
            "| --- | --- | --- | --- | --- |",
            *edge_rows,
            "",
            "## Methods-Graph Grounding",
            "",
            "| Edge | Status | Chosen Methods | Gaps |",
            "| --- | --- | --- | --- |",
            *grounding_rows,
            "",
            "## Coverage Gaps",
            "",
            *gaps,
            "",
            "## Invariants",
            "",
            "- Selected biological edges can seed EvaluationPlans.",
            "- Missing method/data/container/contrast coverage remains explicit.",
            "- Biological support/refute verdicts are not emitted.",
            "- Execution remains behind dry-run, trust, validation, and provenance gates.",
            "",
        ]
    )


def build_biological_graph(root: str | Path, max_files: int = 500) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    scan = scan_workspace(root_path, max_files=max_files)
    substrate = build_methods_graph_substrate()
    task_class = infer_task_class(scan)
    base_gaps = compute_coverage_gaps(scan, task_class, substrate)
    edges = [
        merge_grounding_into_edge(edge, ground_edge_with_methods_graph(edge, scan, substrate=substrate))
        for edge in build_biological_edges(scan, substrate, task_class, base_gaps)
    ]
    gaps = dedupe([*base_gaps, *[gap for edge in edges for gap in edge.get("facts", {}).get("coverage_gaps", [])]])
    nodes = build_nodes(scan, substrate, task_class, gaps)
    status = graph_status(scan, gaps)
    result = {
        "service": "dogma-local-service",
        "root": str(root_path),
        "status": status,
        "task_class": task_class,
        "methods_graph_status": substrate.get("status"),
        "summary": summarize(nodes, edges, gaps),
        "nodes": nodes,
        "edges": edges,
        "coverage_gaps": gaps,
        "invariants": {
            "stores_biological_verdicts": False,
            "selected_edges_seed_evaluation_plans": True,
            "coverage_gaps_are_explicit": True,
            "explicit_execution_gates": True,
        },
    }
    result["markdown"] = render_biological_graph_markdown(result)
    return result
