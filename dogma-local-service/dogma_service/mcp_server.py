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
        "name": "open_journal",
        "description": (
            "Read the workspace's append-only bench journal: what this service "
            "actually did (stub/dry runs, applied patches, trust grants) and what "
            "agents reported. Call this at the start of a session so you do not "
            "re-derive what is already recorded."
        ),
        "inputSchema": object_schema({"root": ROOT_PROPERTY}, ["root"]),
    },
    {
        "name": "record_decision",
        "description": (
            "Record a method or analysis decision and its reason in the journal, "
            "for the next agent or the next session. Stored as a self-reported "
            "claim, never as an observation — it does not assert that anything ran."
        ),
        "inputSchema": object_schema(
            {
                "root": ROOT_PROPERTY,
                "agent": {"type": "string", "description": "Who is making the claim, e.g. 'claude-code'."},
                "about": {"type": "string", "description": "What the decision concerns."},
                "chose": {"type": "string", "description": "What was chosen."},
                "because": {"type": "string", "description": "Why. Required: an unexplained choice is not worth recording."},
                "over": {"type": "string", "description": "What was rejected, if anything."},
                "supersedes": {"type": "string", "description": "entry_id this corrects. The earlier entry is kept."},
            },
            ["root", "agent", "about", "chose", "because"],
        ),
    },
    {
        "name": "check_claim_shape",
        "description": (
            "Compare the claim graph against the journal: does any edge claim a "
            "measurement the record cannot support? Call before reporting a "
            "conclusion. Returns facts and explicit limitations, never a verdict."
        ),
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


# Mirrors quration.hypothesis.graph.EdgeState. This adapter stays dependency-free
# on purpose (see quration_handoff.py), so the vocabulary is duplicated rather
# than imported — and that duplication is precisely how the filter below drifted:
# it tested `state != "tested"`, and "tested" has never been a member of
# EdgeState. Being the left side of an `or`, it was unconditionally true, so the
# tool named for listing untested claims returned every edge, always.
#
# It looked correct because quration_handoff.py hardcodes every edge to
# "untested", so the two errors cancelled. It would have started lying the moment
# the handoff learned to emit a measured edge — reporting a measured claim as
# untested, which is the inverse of this tool's purpose.
MEASURED_EDGE_STATE = "examined"  # only a measurement reaches this; see CLAUDE.md
KNOWN_EDGE_STATES = frozenset(
    {
        "untested",  # nothing has looked at it
        "assessed",  # a feasibility verdict exists; nothing measured it
        MEASURED_EDGE_STATE,
        # Deprecated in EdgeState but still accepted, so drift is not misreported
        # as an unknown state.
        "contested",
        "supported",
        "refuted",
    }
)


def edge_is_unmeasured(edge: dict[str, Any]) -> bool:
    """True unless something actually measured this edge.

    An unrecognised state counts as unmeasured: claiming a measurement landed is
    the assertion that needs evidence, so an unknown value must never be the
    reason an edge disappears from this list.
    """
    return edge.get("state") != MEASURED_EDGE_STATE


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
        if edge_is_unmeasured(edge)
    ]
    # Surface vocabulary drift instead of absorbing it. If the handoff starts
    # emitting a state this adapter does not know, that is a contract change the
    # caller should see, not something to silently classify.
    unrecognised = sorted(
        {
            str(edge.get("state"))
            for edge in graph.get("edges", [])
            if edge.get("state") not in KNOWN_EDGE_STATES
        }
    )
    return {
        "contract_version": "dogma-mcp-result.v1",
        "tool": "list_untested_or_stale_claims",
        "root": str(root),
        "untested_claims": untested,
        "unrecognised_edge_states": unrecognised,
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
            "dogma_monorepo_is_canonical": True,
            "dogma_web_ui_is_canonical_graph_surface": True,
            "quration_is_compatibility_namespace": True,
            "stores_biological_verdicts": False,
            "stores_confidence_grades": False,
            "coverage_gaps_are_explicit": True,
        },
    }
    return bundle if include_markdown else strip_markdown(bundle)


def open_journal(arguments: dict[str, Any]) -> dict[str, Any]:
    from . import journal

    root = root_arg(arguments)
    entries = journal.read(root)
    return {
        "contract_version": "dogma-mcp-result.v1",
        "tool": "open_journal",
        "root": str(root),
        "summary": journal.summary(root),
        "entries": entries,
        "reading_guide": {
            "self_reported_true": "an agent's claim; nothing verified it",
            "self_reported_false": "written by the service inside the function "
                                   "that acted, so it means the thing happened",
            "stub_run_and_dry_run": "compile checks, not measurements",
        },
    }


def record_decision(arguments: dict[str, Any]) -> dict[str, Any]:
    from . import journal

    root = root_arg(arguments)
    required = ("agent", "about", "chose", "because")
    missing = [key for key in required if not str(arguments.get(key) or "").strip()]
    if missing:
        # `because` is required on purpose. A recorded choice with no reason is
        # the least useful thing in a notebook and the easiest to fill with
        # filler, so it is refused rather than defaulted.
        raise ValueError(f"record_decision requires non-empty: {', '.join(missing)}")

    entry = journal.append(
        root,
        "decision",
        {
            "about": arguments["about"],
            "chose": arguments["chose"],
            "because": arguments["because"],
            "over": arguments.get("over") or None,
        },
        agent=str(arguments["agent"]),
        supersedes=arguments.get("supersedes") or None,
    )
    return {
        "contract_version": "dogma-mcp-result.v1",
        "tool": "record_decision",
        "root": str(root),
        "entry": entry,
        "note": "recorded as a self-reported claim; it does not assert that anything ran",
    }


def check_claim_shape(arguments: dict[str, Any]) -> dict[str, Any]:
    from .claim_shape import check_claim_shape as _check

    return {
        "contract_version": "dogma-mcp-result.v1",
        "tool": "check_claim_shape",
        **_check(root_arg(arguments), max_files=max_files_arg(arguments)),
    }


CALLABLE_TOOLS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "open_journal": open_journal,
    "record_decision": record_decision,
    "check_claim_shape": check_claim_shape,
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

    # A JSON-RPC notification is any message with no `id`, and the spec forbids
    # replying to one at all. This previously special-cased only
    # `notifications/initialized`; every other notification fell through to the
    # unknown-method branch and got an error response with `"id": null`. That
    # fires the first time a host cancels a request or reports progress — both
    # routine — and a strict client treats the stray reply as a protocol error.
    # Keyed on the absence of `id` rather than on the method name, so a
    # notification added to a later protocol version cannot reintroduce this.
    if message_id is None:
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
