"""Dependency-free MCP stdio adapter for Dogma evidence-control tools.

This module implements the small JSON-RPC subset needed by MCP hosts:
initialize, tools/list, and tools/call. It intentionally wraps existing
deterministic Dogma builders instead of adding a new database or LLM path.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

from .edge_evaluation_plan import build_edge_evaluation_plan
from .evidence_ledger import build_evidence_ledger
from .execution_sandbox import build_run_plan_for_workspace
from .method_guardrails import build_method_guardrails
from .quration_handoff import build_quration_handoff


SERVER_NAME = "dogma-evidence-control-plane"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"


def object_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


ROOT_PROPERTY = {
    "type": "string",
    "description": "Workspace root to inspect. Use an absolute path when called from an external MCP host.",
}

MAX_FILES_PROPERTY = {
    "type": "integer",
    "minimum": 1,
    "maximum": 5000,
    "default": 500,
    "description": "Maximum candidate files to scan.",
}


TOOLS: list[dict[str, Any]] = [
    {
        "name": "create_claim_graph",
        "description": "Create a quration-compatible claim graph from local Dogma workspace facts without assigning support/refute verdicts.",
        "inputSchema": object_schema({"root": ROOT_PROPERTY, "max_files": MAX_FILES_PROPERTY}, ["root"]),
    },
    {
        "name": "record_analysis_run",
        "description": "Return a dry-run/stub-run execution record for a workspace; does not execute commands.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "max_files": MAX_FILES_PROPERTY,
                "run_id": {"type": "string", "description": "Optional caller-provided run identifier."},
            },
            ["root"],
        ),
    },
    {
        "name": "attach_evidence",
        "description": "Attach factual Dogma evidence records and ledger entries to the current claim graph.",
        "inputSchema": object_schema({"root": ROOT_PROPERTY, "max_files": MAX_FILES_PROPERTY}, ["root"]),
    },
    {
        "name": "list_untested_or_stale_claims",
        "description": "List graph edges that remain untested plus explicit stale-detection limitations.",
        "inputSchema": object_schema({"root": ROOT_PROPERTY, "max_files": MAX_FILES_PROPERTY}, ["root"]),
    },
    {
        "name": "check_method_assumptions",
        "description": "Return method assumptions, preconditions, guardrails, and coverage gaps for local review.",
        "inputSchema": object_schema({"root": ROOT_PROPERTY, "max_files": MAX_FILES_PROPERTY}, ["root"]),
    },
    {
        "name": "export_evidence_bundle",
        "description": "Export claim graph, evidence ledger, method assumptions, and quration handoff as one JSON bundle.",
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "max_files": MAX_FILES_PROPERTY,
                "include_markdown": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include rendered Markdown fields in the returned bundle.",
                },
            },
            ["root"],
        ),
    },
]


def tool_names() -> list[str]:
    return [tool["name"] for tool in TOOLS]


def root_arg(arguments: dict[str, Any]) -> Path:
    root = arguments.get("root")
    if not isinstance(root, str) or not root.strip():
        raise ValueError("root is required and must be a non-empty string")
    return Path(root).expanduser().resolve()


def max_files_arg(arguments: dict[str, Any]) -> int:
    raw_value = arguments.get("max_files", 500)
    if not isinstance(raw_value, int):
        raise ValueError("max_files must be an integer")
    if raw_value < 1 or raw_value > 5000:
        raise ValueError("max_files must be between 1 and 5000")
    return raw_value


def strip_markdown(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: strip_markdown(item) for key, item in value.items() if key != "markdown"}
    if isinstance(value, list):
        return [strip_markdown(item) for item in value]
    return value


def create_claim_graph(arguments: dict[str, Any]) -> dict[str, Any]:
    root = root_arg(arguments)
    handoff = build_quration_handoff(root, max_files=max_files_arg(arguments))
    return {
        "contract_version": "dogma-mcp-result.v1",
        "tool": "create_claim_graph",
        "root": str(root),
        "causal_graph": handoff["causal_graph"],
        "evaluation_plans": handoff["evaluation_plans"],
        "dogma": handoff["dogma"],
        "invariants": handoff["invariants"],
    }


def record_analysis_run(arguments: dict[str, Any]) -> dict[str, Any]:
    root = root_arg(arguments)
    run_plan = build_run_plan_for_workspace(root, max_files=max_files_arg(arguments))
    run_id = arguments.get("run_id") or "dogma-local-dry-run-preview"
    if not isinstance(run_id, str):
        raise ValueError("run_id must be a string when provided")
    return {
        "contract_version": "dogma-mcp-result.v1",
        "tool": "record_analysis_run",
        "root": str(root),
        "run": {
            "id": run_id,
            "status": run_plan.get("status"),
            "execution_allowed": run_plan.get("execution_allowed"),
            "commands": run_plan.get("commands", []),
            "safety_notes": run_plan.get("safety_notes", []),
            "record_kind": "dry_run_plan",
            "executed": False,
        },
        "summary": {
            "error_count": run_plan.get("error_count", 0),
            "warning_count": run_plan.get("warning_count", 0),
        },
    }


def attach_evidence(arguments: dict[str, Any]) -> dict[str, Any]:
    root = root_arg(arguments)
    max_files = max_files_arg(arguments)
    ledger = build_evidence_ledger(root, max_files=max_files)
    handoff = build_quration_handoff(root, max_files=max_files)
    return {
        "contract_version": "dogma-mcp-result.v1",
        "tool": "attach_evidence",
        "root": str(root),
        "ledger": strip_markdown(ledger),
        "evidence_records": handoff["evidence_records"],
        "invariants": {
            "stores_biological_verdicts": False,
            "stores_confidence_grades": False,
            "sample_ids_redacted": ledger.get("invariants", {}).get("sample_ids_redacted"),
        },
    }


def list_untested_or_stale_claims(arguments: dict[str, Any]) -> dict[str, Any]:
    root = root_arg(arguments)
    handoff = build_quration_handoff(root, max_files=max_files_arg(arguments))
    graph = handoff["causal_graph"]
    untested = [
        {
            "id": edge.get("id"),
            "source_id": edge.get("source_id"),
            "target_id": edge.get("target_id"),
            "relation": edge.get("relation"),
            "state": edge.get("state"),
            "validation_status": edge.get("validation_status"),
        }
        for edge in graph.get("edges", [])
        if edge.get("state") != "tested" or edge.get("validation_status") != "validated"
    ]
    return {
        "contract_version": "dogma-mcp-result.v1",
        "tool": "list_untested_or_stale_claims",
        "root": str(root),
        "untested_claims": untested,
        "stale_claims": [],
        "stale_detection": {
            "status": "not_available_without_persisted_claim_edit_history",
            "note": "This dependency-free MCP adapter reports untested claims from the current handoff. Stale evidence requires a persisted claim-edit ledger.",
        },
    }


def check_method_assumptions(arguments: dict[str, Any]) -> dict[str, Any]:
    root = root_arg(arguments)
    max_files = max_files_arg(arguments)
    edge_plan = build_edge_evaluation_plan(root, max_files=max_files)
    guardrails = build_method_guardrails(root, max_files=max_files)
    return {
        "contract_version": "dogma-mcp-result.v1",
        "tool": "check_method_assumptions",
        "root": str(root),
        "edge": edge_plan.get("edge"),
        "task_class": edge_plan.get("task_class"),
        "status": edge_plan.get("status"),
        "coverage_gaps": edge_plan.get("coverage_gaps", []),
        "contracts": edge_plan.get("contracts", []),
        "guardrails": strip_markdown(guardrails),
    }


def export_evidence_bundle(arguments: dict[str, Any]) -> dict[str, Any]:
    root = root_arg(arguments)
    max_files = max_files_arg(arguments)
    include_markdown = bool(arguments.get("include_markdown", False))
    handoff = build_quration_handoff(root, max_files=max_files)
    ledger = build_evidence_ledger(root, max_files=max_files)
    edge_plan = build_edge_evaluation_plan(root, max_files=max_files)
    bundle: dict[str, Any] = {
        "contract_version": "dogma-mcp-result.v1",
        "tool": "export_evidence_bundle",
        "root": str(root),
        "quration_handoff": handoff,
        "evidence_ledger": ledger,
        "method_assumptions": edge_plan,
        "invariants": {
            "quration_web_ui_is_canonical": True,
            "dogma_is_local_ide_layer": True,
            "stores_biological_verdicts": False,
            "stores_confidence_grades": False,
            "coverage_gaps_are_explicit": True,
        },
    }
    return bundle if include_markdown else strip_markdown(bundle)


CALLABLE_TOOLS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "create_claim_graph": create_claim_graph,
    "record_analysis_run": record_analysis_run,
    "attach_evidence": attach_evidence,
    "list_untested_or_stale_claims": list_untested_or_stale_claims,
    "check_method_assumptions": check_method_assumptions,
    "export_evidence_bundle": export_evidence_bundle,
}


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    if name not in CALLABLE_TOOLS:
        raise ValueError(f"unknown Dogma MCP tool: {name}")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ValueError("tool arguments must be a JSON object")
    return CALLABLE_TOOLS[name](arguments)


def make_result(message_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def make_error(message_id: Any, code: int, message: str, data: Any | None = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": message_id, "error": error}


def text_content(payload: dict[str, Any]) -> list[dict[str, str]]:
    return [{"type": "text", "text": json.dumps(payload, indent=2, sort_keys=True)}]


def handle_jsonrpc_message(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    message_id = message.get("id")

    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return make_result(
            message_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
    if method == "ping":
        return make_result(message_id, {})
    if method == "tools/list":
        return make_result(message_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params") or {}
        if not isinstance(params, dict):
            return make_error(message_id, -32602, "params must be an object")
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str):
            return make_error(message_id, -32602, "tool name is required")
        try:
            payload = call_tool(name, arguments)
        except ValueError as error:
            return make_result(message_id, {"content": text_content({"error": str(error)}), "isError": True})
        return make_result(message_id, {"content": text_content(payload), "structuredContent": payload, "isError": False})

    return make_error(message_id, -32601, f"method not found: {method}")


def run_stdio(input_stream: Any = None, output_stream: Any = None) -> int:
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    for line in input_stream:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            message = json.loads(stripped)
        except json.JSONDecodeError as error:
            response = make_error(None, -32700, "parse error", str(error))
        else:
            if not isinstance(message, dict):
                response = make_error(None, -32600, "invalid request")
            else:
                response = handle_jsonrpc_message(message)
        if response is not None:
            output_stream.write(json.dumps(response, separators=(",", ":")) + "\n")
            output_stream.flush()
    return 0
