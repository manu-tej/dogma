"""Dogma's 32 bioinformatics tools, served over MCP stdio.

This is what lets the interpretation loop run with **no API key**.

`claude_integration` drives an agentic tool-use loop against `anthropic.Anthropic`,
so interpretation needed a metered key even though the machine already had a
logged-in Claude Code CLI. That looked architectural — the subscription provider
does one-shot completions and cannot run a tool loop — but the conclusion was
wrong. `claude -p` *is* an agentic loop; it was only missing Dogma's tools.
`--mcp-config` supplies them. The CLI runs the loop, calls back into this
server for every gene lookup and pathway query, and bills the subscription.

Deliberately a **separate** server from `dogma_service.mcp_server`. That one is
stdlib-only, which is the property `bin/dogma` exists to guarantee: a fresh
clone with no venv can serve it. These tools reach UniProt, KEGG, Reactome, GEO
and PubMed and need `quration` and its dependencies, so folding them in would
quietly reimpose an install on every external agent. Two servers, two contracts:

    bin/dogma mcp        — workspace guardrails, zero install
    bin/dogma bio-mcp    — the bio tool belt, needs the venv

Nothing here interprets anything. It executes a named tool and returns what the
source returned, so a wrong answer is the data source's, never this layer's.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)

SERVER_NAME = "dogma-bio-tools"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2024-11-05"


def build_executor():
    """The same executor `claude_integration` uses, so both paths call one
    implementation. A second tool registry would drift."""
    from quration.interpretation.executor import create_executor

    return create_executor(include_all_tools=True)


def tool_definitions(executor) -> list[dict[str, Any]]:
    """Anthropic tool shape -> MCP tool shape.

    The only difference that matters is the schema key: `input_schema` there,
    `inputSchema` here. The descriptions are the ones the tools already carry,
    so the model sees the same guidance either way.
    """
    return [
        {
            "name": definition["name"],
            "description": definition.get("description", ""),
            "inputSchema": definition.get("input_schema")
            or {"type": "object", "properties": {}},
        }
        for definition in executor.get_tool_definitions()
    ]


def call_tool(executor, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute one tool and return its result payload."""
    result = asyncio.run(executor.execute(name, **(arguments or {})))
    # ToolResult carries success/data/error. Surfaced as-is: this server reports
    # what the source said and never substitutes a plausible answer for a failed
    # lookup, which is the whole reason a grounded tool belt is worth having.
    payload: dict[str, Any] = {
        "tool": name,
        "success": bool(getattr(result, "success", False)),
    }
    data = getattr(result, "data", None)
    if data is not None:
        payload["data"] = data
    error = getattr(result, "error", None)
    if error:
        payload["error"] = str(error)
    return payload


def make_result(message_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def make_error(message_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def handle_message(executor, message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    message_id = message.get("id")

    # A notification has no id and the spec forbids replying at all. Keyed on the
    # missing id rather than a list of names — the same defect was found and
    # fixed in the other server, and repeating it here would be careless.
    if message_id is None:
        return None
    if method == "initialize":
        return make_result(message_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })
    if method == "ping":
        return make_result(message_id, {})
    if method == "tools/list":
        return make_result(message_id, {"tools": tool_definitions(executor)})
    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        if not isinstance(name, str):
            return make_error(message_id, -32602, "tool name is required")
        try:
            payload = call_tool(executor, name, params.get("arguments") or {})
        except Exception as exc:  # noqa: BLE001 - reported to the caller, not swallowed
            logger.warning("bio tool %s failed", name, exc_info=True)
            return make_result(message_id, {
                "content": [{"type": "text", "text": json.dumps({"tool": name, "error": str(exc)})}],
                "isError": True,
            })
        return make_result(message_id, {
            "content": [{"type": "text", "text": json.dumps(payload, indent=2, default=str)}],
            "structuredContent": payload,
            "isError": not payload["success"],
        })
    return make_error(message_id, -32601, f"method not found: {method}")


def run_stdio(input_stream: Any = None, output_stream: Any = None) -> int:
    # Every diagnostic goes to stderr: stdout is the JSON-RPC channel and one
    # stray line corrupts the session.
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    executor = build_executor()
    input_stream = input_stream or sys.stdin
    output_stream = output_stream or sys.stdout
    for line in input_stream:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            message = json.loads(stripped)
        except json.JSONDecodeError as exc:
            response = make_error(None, -32700, f"parse error: {exc}")
        else:
            response = handle_message(executor, message) if isinstance(message, dict) else \
                make_error(None, -32600, "invalid request")
        if response is not None:
            output_stream.write(json.dumps(response, separators=(",", ":")) + "\n")
            output_stream.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_stdio())
