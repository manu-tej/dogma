"""Read-only methods-graph grounding adapter for Dogma biological edges."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Mapping

from .methods_graph_substrate import METHODS_GRAPH_REPO, build_methods_graph_substrate


def dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def dataset_format_for_scan(scan: dict[str, Any], env: Mapping[str, str] | None = None) -> tuple[str | None, str]:
    values = env or os.environ
    explicit = values.get("DOGMA_METHODS_GRAPH_DATASET_FORMAT")
    if explicit:
        return explicit, "env:DOGMA_METHODS_GRAPH_DATASET_FORMAT"
    legacy_explicit = values.get("BIOCURSOR_METHODS_GRAPH_DATASET_FORMAT")
    if legacy_explicit:
        return legacy_explicit, "env:BIOCURSOR_METHODS_GRAPH_DATASET_FORMAT"

    context = scan.get("context", {})
    if context.get("sample_file") or context.get("data_inventory", {}).get("fastq"):
        return "fmt:format_1930", "heuristic:fastq_edam_format"
    if context.get("vcf_files"):
        return "fmt:format_3016", "heuristic:vcf_edam_format"
    return None, "none"


def planner_edge(edge: dict[str, Any]) -> dict[str, str]:
    return {
        "source_label": str(edge.get("source") or edge.get("from") or ""),
        "target_label": str(edge.get("target") or edge.get("to") or ""),
        "relation": str(edge.get("relation") or ""),
    }


def import_methods_graph_runtime() -> dict[str, Any]:
    src = Path(METHODS_GRAPH_REPO) / "src"
    if src.exists() and str(src) not in sys.path:
        sys.path.insert(0, str(src))
    import kuzu  # type: ignore
    from methods_graph.extract.seed import method_preconditions  # type: ignore
    from methods_graph.planner import expand, seed_from_edge  # type: ignore

    return {
        "kuzu": kuzu,
        "expand": expand,
        "seed_from_edge": seed_from_edge,
        "method_preconditions": method_preconditions,
    }


def close_quietly(handle: Any) -> None:
    close = getattr(handle, "close", None)
    if callable(close):
        close()


def suggestion_dict(item: Any) -> dict[str, Any]:
    if hasattr(item, "to_dict"):
        return item.to_dict()
    if isinstance(item, dict):
        return item
    return {}


def chosen_method_ids(suggestions: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for suggestion in suggestions:
        executor = suggestion.get("chosen_executor") or {}
        method_id = executor.get("method_id")
        if method_id:
            ids.append(str(method_id))
    return dedupe(ids)


def preconditions_for_methods(runtime: dict[str, Any], conn: Any, method_ids: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    method_preconditions = runtime.get("method_preconditions")
    if not callable(method_preconditions):
        return out
    for method_id in method_ids:
        try:
            out.append(method_preconditions(conn, method_id))
        except KeyError:
            out.append({"method_id": method_id, "status": "coverage_gap", "coverage_gaps": ["methods_graph.method_preconditions_missing"]})
    return out


def ground_edge_with_methods_graph(
    edge: dict[str, Any],
    scan: dict[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    substrate: dict[str, Any] | None = None,
    runtime: dict[str, Any] | None = None,
    limit: int = 6,
) -> dict[str, Any]:
    """Ground a Dogma biological edge through methods-graph when available.

    This is deliberately read-only and advisory. Missing configuration, missing
    Python dependencies, empty seeds, or empty suggestions are coverage gaps.
    """
    values = env or os.environ
    current_substrate = substrate or build_methods_graph_substrate(values)
    dataset_format, dataset_format_source = dataset_format_for_scan(scan, values)
    base = {
        "status": current_substrate.get("status"),
        "methods_graph_status": current_substrate.get("status"),
        "dataset_format": dataset_format,
        "dataset_format_source": dataset_format_source,
        "frontier": [],
        "suggestions": [],
        "chosen_method_ids": [],
        "preconditions": [],
        "coverage_gaps": [],
        "advisory_only": True,
    }

    if current_substrate.get("status") != "ready":
        base["coverage_gaps"] = ["methods_graph.audited_substrate_missing"]
        return base

    graph_path = current_substrate.get("configured_graph", {}).get("path")
    if not graph_path:
        base["status"] = "configuration_gap"
        base["coverage_gaps"] = ["methods_graph.db_path_missing"]
        return base

    try:
        active_runtime = runtime or import_methods_graph_runtime()
    except Exception as error:  # noqa: BLE001 - dependency and ABI failures are explicit gaps.
        base["status"] = "dependency_gap"
        base["coverage_gaps"] = ["methods_graph.python_dependency_missing"]
        base["error"] = f"{type(error).__name__}: {error}"
        return base

    db = conn = None
    try:
        kuzu = active_runtime["kuzu"]
        db = kuzu.Database(str(Path(graph_path).expanduser()), read_only=True)
        conn = kuzu.Connection(db)
        frontier = active_runtime["seed_from_edge"](conn, planner_edge(edge), dataset_format=dataset_format)
        base["frontier"] = frontier
        if not frontier:
            base["status"] = "coverage_gap"
            base["coverage_gaps"] = ["methods_graph.frontier_seed_missing"]
            return base
        suggestions = [suggestion_dict(item) for item in active_runtime["expand"](conn, frontier, limit=limit)]
        base["suggestions"] = suggestions
        method_ids = chosen_method_ids(suggestions)
        base["chosen_method_ids"] = method_ids
        base["preconditions"] = preconditions_for_methods(active_runtime, conn, method_ids)
        if not suggestions:
            base["status"] = "coverage_gap"
            base["coverage_gaps"] = ["methods_graph.suggestions_missing"]
        else:
            base["status"] = "grounded"
        return base
    except Exception as error:  # noqa: BLE001 - graph query/runtime failures are explicit gaps.
        base["status"] = "query_gap"
        base["coverage_gaps"] = ["methods_graph.query_failed"]
        base["error"] = f"{type(error).__name__}: {error}"
        return base
    finally:
        close_quietly(conn)
        close_quietly(db)
