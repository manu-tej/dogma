"""quration-compatible handoff adapter for Dogma workspace facts.

This module deliberately does not import quration. It emits a stable JSON shape
that mirrors quration's current graph, plan, and evidence-record contracts while
keeping Dogma's local service dependency-free.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .biological_graph import build_biological_graph
from .edge_evaluation_plan import build_edge_evaluation_plan
from .evidence_ledger import build_evidence_ledger
from .indexer import scan_workspace
from .repo_paths import dogma_repo_root


QURATION_REPO = dogma_repo_root()
CONTRACT_VERSION = "quration-handoff.v1"
DEFAULT_QURATION_FRONTEND_URL = "http://localhost:3000/canvas"
DEFAULT_QURATION_API_URL = "http://localhost:8000"


def quration_urls() -> dict[str, str]:
    frontend_url = (
        os.environ.get("DOGMA_QURATION_FRONTEND_URL")
        or os.environ.get("QURATION_FRONTEND_URL")
        or DEFAULT_QURATION_FRONTEND_URL
    ).rstrip("/")
    api_url = (
        os.environ.get("DOGMA_QURATION_API_URL")
        or os.environ.get("QURATION_API_URL")
        or DEFAULT_QURATION_API_URL
    ).rstrip("/")
    return {"frontend_url": frontend_url, "api_url": api_url}


def quration_import_hint(root_path: Path) -> dict[str, Any]:
    urls = quration_urls()
    return {
        "frontend_url": urls["frontend_url"],
        "api_url": urls["api_url"],
        "api_health_url": f"{urls['api_url']}/health",
        "hypothesis_graphs_url": f"{urls['api_url']}/hypothesis",
        "handoff_json_path": str(root_path / ".dogma" / "quration-handoff.json"),
        "handoff_markdown_path": str(root_path / ".dogma" / "quration-handoff.md"),
        "import_endpoint": None,
        "status": "handoff_ready_import_endpoint_not_present",
        "next_steps": [
            f"Start the Dogma web graph app with `npm run dev` in {QURATION_REPO}.",
            "Open the graph UI and import or adapt the Dogma handoff JSON when the web app exposes an import endpoint.",
            "Keep the web graph workspace as the canonical graph UI; keep the Dogma extension as the local IDE/editor surface.",
        ],
    }


def node_type_for(kind: str) -> str:
    return {
        "readout": "phenotype",
        "contrast": "other",
        "dataset": "other",
        "reference": "other",
        "methods_graph": "other",
        "guardrail": "other",
    }.get(str(kind), "other")


def modality_for_task(task_class: str, readout: str | None) -> str:
    text = f"{task_class} {readout or ''}".lower()
    if "transcript" in text or "rna" in text:
        return "transcript"
    if "protein" in text:
        return "protein"
    if "phospho" in text:
        return "phospho"
    if "methyl" in text:
        return "methylation"
    if "binding" in text:
        return "binding"
    if "phenotype" in text or "quality" in text:
        return "phenotype"
    return "unknown"


def edge_node_ids(edge: dict[str, Any], graph_nodes: list[dict[str, Any]]) -> tuple[str, str]:
    node_ids = {node.get("id") for node in graph_nodes}
    if "contrast:declared" in node_ids and "readout:primary" in node_ids:
        return "contrast:declared", "readout:primary"
    if "dataset:samples" in node_ids and "readout:primary" in node_ids:
        return "dataset:samples", "readout:primary"
    source = str(edge.get("source") or "source").lower().replace(" ", "_")
    target = str(edge.get("target") or "target").lower().replace(" ", "_")
    return f"dogma:{source}", f"dogma:{target}"


def quration_causal_graph(biological_graph: dict[str, Any]) -> dict[str, Any]:
    nodes = [
        {
            "id": node.get("id"),
            "type": node_type_for(node.get("kind", "other")),
            "label": node.get("label"),
            "grounding": None,
            "position": None,
        }
        for node in biological_graph.get("nodes", [])
    ]
    edges = []
    for edge in biological_graph.get("edges", []):
        source_id, target_id = edge_node_ids(edge, nodes)
        edges.append(
            {
                "id": edge.get("id"),
                "source_id": source_id,
                "target_id": target_id,
                "relation": edge.get("relation") or "relates_to",
                "state": "untested",
                "confidence": 0.0,
                "suggested_by": [],
                "pending": False,
                "proposed_test": {
                    "pipeline": None,
                    "data_accession": None,
                    "expected": edge.get("question"),
                },
                "proposal_source": "system",
                "validation_status": "unvalidated",
                "validations": [],
                "display_status": None,
            }
        )

    first_edge = next(iter(biological_graph.get("edges", [])), {})
    return {
        "id": f"dogma:{Path(str(biological_graph.get('root') or 'workspace')).name}:{biological_graph.get('task_class')}",
        "query": first_edge.get("question") or "Dogma workspace biological graph handoff",
        "nodes": nodes,
        "edges": edges,
    }


def grounding_contract(edge_plan: dict[str, Any]) -> dict[str, Any]:
    return next((item for item in edge_plan.get("contracts", []) if item.get("stage") == "Grounding"), {})


def readout_contract(edge_plan: dict[str, Any]) -> dict[str, Any]:
    return next((item for item in edge_plan.get("contracts", []) if item.get("stage") == "Readout"), {})


def quration_assumptions(edge_plan: dict[str, Any]) -> list[dict[str, Any]]:
    facts = grounding_contract(edge_plan).get("facts", {})
    outcomes: list[dict[str, Any]] = []
    assumption_items = facts.get("assumptions", []) if isinstance(facts.get("assumptions"), list) else []
    for item in assumption_items:
        outcomes.append({"name": str(item), "checkable": "", "threshold": None, "via": [], "status": "unchecked"})

    preconditions = facts.get("methods_graph_preconditions") or []
    if isinstance(preconditions, list):
        for precondition in preconditions:
            if not isinstance(precondition, dict):
                continue
            precondition_assumptions = precondition.get("assumptions", []) if isinstance(precondition.get("assumptions"), list) else []
            for assumption in precondition_assumptions:
                if isinstance(assumption, dict):
                    outcomes.append(
                        {
                            "name": str(assumption.get("name") or assumption.get("id") or "methods-graph assumption"),
                            "checkable": str(assumption.get("checkable") or ""),
                            "threshold": assumption.get("threshold"),
                            "via": assumption.get("via") if isinstance(assumption.get("via"), list) else [],
                            "status": "unchecked",
                        }
                    )
    return outcomes


def quration_evaluation_plan(edge_plan: dict[str, Any]) -> dict[str, Any]:
    edge = edge_plan.get("edge", {})
    readout_facts = readout_contract(edge_plan).get("facts", {})
    readout = readout_facts.get("readout") or edge.get("target") or "typed readout"
    modality = modality_for_task(edge_plan.get("task_class", ""), str(readout))
    not_evaluable = edge_plan.get("status") in {"blocked", "coverage_gap"}
    return {
        "edge_id": edge.get("id"),
        "claim": {
            "source_symbol": edge.get("source"),
            "target_symbol": edge.get("target"),
            "relation": edge.get("relation"),
        },
        "ideal_readout": {
            "claimed_entity": edge.get("target"),
            "modality": modality,
            "ideal_assay_class": str(readout),
        },
        "resolved_readout": None,
        "directness": None,
        "proxy_rationale": "Dogma has not resolved an external dataset in this handoff; it preserves local workspace facts and coverage gaps.",
        "dataset": None,
        "alternatives": [],
        "method": None,
        "assumptions": quration_assumptions(edge_plan),
        "expected_direction": "unknown",
        "not_evaluable": bool(not_evaluable),
        "resolver_provenance": {
            "source": "dogma-local-service",
            "contract_version": CONTRACT_VERSION,
            "coverage_gaps": edge_plan.get("coverage_gaps", []),
        },
    }


def claim_signature(edge_plan: dict[str, Any]) -> list[str]:
    edge = edge_plan.get("edge", {})
    return [str(edge.get("source") or ""), str(edge.get("target") or ""), str(edge.get("relation") or "")]


def quration_evidence_records(ledger: dict[str, Any], edge_plan: dict[str, Any]) -> list[dict[str, Any]]:
    edge_id = edge_plan.get("edge", {}).get("id")
    signature = claim_signature(edge_plan)
    records: list[dict[str, Any]] = []
    for item in ledger.get("entries", []):
        status = item.get("status", "info")
        source = item.get("source") or "dogma-local-service"
        caveats = [f"dogma_status:{status}"] if status in {"blocked", "warning", "gap"} else []
        records.append(
            {
                "edge_id": edge_id,
                "claim_signature": signature,
                "measured_vs_claimed": item.get("title") or item.get("id"),
                "method": None,
                "dataset_context": {
                    "source": source,
                    "entry_type": item.get("type"),
                    "entry_status": status,
                    "workspace_root": ledger.get("root"),
                },
                "raw_result": {"dogma_entry": item},
                "per_assumption_outcomes": [],
                "directness": "not_evaluable",
                "caveats": caveats,
                "provenance": {
                    "kind": "resolver",
                    "model": None,
                    "queries_tried": [],
                    "sources_searched": [source],
                    "n_candidates": 1,
                },
                "created_at": None,
            }
        )
    return records


def render_quration_handoff_markdown(result: dict[str, Any]) -> str:
    graph = result.get("causal_graph", {})
    plan_rows = [
        f"| {plan.get('edge_id')} | {plan.get('not_evaluable')} | {plan.get('ideal_readout', {}).get('modality')} | {len(plan.get('assumptions', []))} |"
        for plan in result.get("evaluation_plans", [])
    ]
    edge_rows = [
        f"| {edge.get('id')} | {edge.get('source_id')} | {edge.get('relation')} | {edge.get('target_id')} | {edge.get('state')} |"
        for edge in graph.get("edges", [])
    ]
    gaps = [f"- {gap}" for gap in result.get("dogma", {}).get("coverage_gaps", [])] or ["- none"]
    import_hint = result.get("quration_import", {})
    return "\n".join(
        [
            "# Dogma quration Handoff",
            "",
            "This artifact maps Dogma local IDE facts into quration-compatible graph, evaluation-plan, and evidence-record shapes.",
            "",
            "## Graph",
            "",
            f"- ID: {graph.get('id')}",
            f"- Query: {graph.get('query')}",
            f"- Nodes: {len(graph.get('nodes', []))}",
            f"- Edges: {len(graph.get('edges', []))}",
            "",
            "| Edge | Source | Relation | Target | State |",
            "| --- | --- | --- | --- | --- |",
            *edge_rows,
            "",
            "## Evaluation Plans",
            "",
            "| Edge | Not Evaluable | Modality | Assumptions |",
            "| --- | --- | --- | --- |",
            *plan_rows,
            "",
            "## Evidence Records",
            "",
            f"- Records: {len(result.get('evidence_records', []))}",
            "- Evidence records are factual handoff records, not support/refute verdicts.",
            "",
            "## Coverage Gaps",
            "",
            *gaps,
            "",
            "## Invariants",
            "",
            "- CausalGraph edge state is untested.",
            "- Confidence is not synthesized.",
            "- EvidenceRecord directness is factual and not a score.",
            "- quration remains the canonical graph web UI.",
            "",
            "## quration Import",
            "",
            f"- Graph UI: {import_hint.get('frontend_url', DEFAULT_QURATION_FRONTEND_URL)}",
            f"- API: {import_hint.get('api_url', DEFAULT_QURATION_API_URL)}",
            f"- Handoff JSON: {import_hint.get('handoff_json_path')}",
            f"- Import status: {import_hint.get('status')}",
            "- quration currently owns the graph canvas; Dogma only exports local IDE facts into that contract.",
            "",
        ]
    )


def build_quration_handoff(root: str | Path, max_files: int = 500) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    scan = scan_workspace(root_path, max_files=max_files)
    biological_graph = build_biological_graph(root_path, max_files=max_files)
    selected_edge = None
    if biological_graph.get("edges"):
        selected_edge = biological_graph["edges"][0].get("selected_edge")
    edge_plan = build_edge_evaluation_plan(root_path, max_files=max_files, selected_edge=selected_edge)
    ledger = build_evidence_ledger(root_path, max_files=max_files)
    causal_graph = quration_causal_graph(biological_graph)
    evaluation_plan = quration_evaluation_plan(edge_plan)
    evidence_records = quration_evidence_records(ledger, edge_plan)
    result = {
        "service": "dogma-local-service",
        "root": str(root_path),
        "contract_version": CONTRACT_VERSION,
        "quration_contract": {
            "repo": QURATION_REPO,
            "models": {
                "CausalGraph": f"{QURATION_REPO}/src/quration/hypothesis/graph.py",
                "EvaluationPlan": f"{QURATION_REPO}/src/quration/hypothesis/orchestrator/evaluation_plan.py",
                "EvidenceRecord": f"{QURATION_REPO}/src/quration/hypothesis/evidence.py",
            },
        },
        "quration_import": quration_import_hint(root_path),
        "causal_graph": causal_graph,
        "evaluation_plans": [evaluation_plan],
        "evidence_records": evidence_records,
        "dogma": {
            "scan_summary": scan.get("summary", {}),
            "trust": scan.get("trust", {}),
            "biological_graph_status": biological_graph.get("status"),
            "task_class": biological_graph.get("task_class"),
            "coverage_gaps": edge_plan.get("coverage_gaps", []),
            "ledger_summary": ledger.get("summary", {}),
        },
        "invariants": {
            "quration_web_ui_is_canonical": True,
            "dogma_is_local_ide_layer": True,
            "stores_biological_verdicts": False,
            "stores_confidence_grades": False,
            "causal_graph_edges_remain_untested": True,
            "coverage_gaps_are_explicit": True,
        },
    }
    result["markdown"] = render_quration_handoff_markdown(result)
    return result
