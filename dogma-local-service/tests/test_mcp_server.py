from __future__ import annotations

import json
import unittest
from pathlib import Path

from biocursor_service.mcp_server import call_tool, handle_jsonrpc_message, tool_names


OUTPUTS_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = OUTPUTS_ROOT / "dogma-demo-workspace"


class McpServerTests(unittest.TestCase):
    def test_tool_list_exposes_evidence_control_plane_tools(self) -> None:
        self.assertEqual(
            tool_names(),
            [
                "create_claim_graph",
                "record_analysis_run",
                "attach_evidence",
                "list_untested_or_stale_claims",
                "check_method_assumptions",
                "export_evidence_bundle",
            ],
        )

    def test_jsonrpc_tools_list_shape(self) -> None:
        response = handle_jsonrpc_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertIsNotNone(response)
        self.assertEqual(response["jsonrpc"], "2.0")
        self.assertEqual(response["id"], 1)
        tools = response["result"]["tools"]
        self.assertEqual(tools[0]["name"], "create_claim_graph")
        self.assertEqual(tools[0]["inputSchema"]["required"], ["root"])

    def test_create_claim_graph_returns_untested_quration_shape(self) -> None:
        result = call_tool("create_claim_graph", {"root": str(DEMO_ROOT), "max_files": 10})
        self.assertEqual(result["contract_version"], "dogma-mcp-result.v1")
        self.assertEqual(result["tool"], "create_claim_graph")
        self.assertIn("causal_graph", result)
        self.assertEqual(result["causal_graph"]["edges"][0]["state"], "untested")
        self.assertFalse(result["invariants"]["stores_biological_verdicts"])

    def test_tools_call_returns_structured_content(self) -> None:
        response = handle_jsonrpc_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "list_untested_or_stale_claims",
                    "arguments": {"root": str(DEMO_ROOT), "max_files": 10},
                },
            }
        )
        self.assertIsNotNone(response)
        result = response["result"]
        self.assertFalse(result["isError"])
        self.assertGreaterEqual(len(result["structuredContent"]["untested_claims"]), 1)
        text_payload = json.loads(result["content"][0]["text"])
        self.assertEqual(text_payload["tool"], "list_untested_or_stale_claims")

    def test_record_analysis_run_never_executes_commands(self) -> None:
        result = call_tool("record_analysis_run", {"root": str(DEMO_ROOT), "max_files": 10, "run_id": "demo-run"})
        self.assertEqual(result["run"]["id"], "demo-run")
        self.assertFalse(result["run"]["executed"])
        self.assertEqual(result["run"]["record_kind"], "dry_run_plan")

    def test_unknown_tool_is_returned_as_mcp_tool_error(self) -> None:
        response = handle_jsonrpc_message(
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "missing", "arguments": {}}}
        )
        self.assertIsNotNone(response)
        self.assertTrue(response["result"]["isError"])
        self.assertIn("unknown Dogma MCP tool", response["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
