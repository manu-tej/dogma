from __future__ import annotations

import json
import unittest
from pathlib import Path

from dogma_service.mcp_server import (
    KNOWN_EDGE_STATES,
    call_tool,
    edge_is_unmeasured,
    handle_jsonrpc_message,
    tool_names,
)


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
                "open_journal",
                "record_decision",
                "check_claim_shape",
                "export_evidence_bundle",
            ],
        )

    def test_record_decision_is_the_only_writing_tool(self) -> None:
        """Eight of nine tools are read-only. Stating which one writes is worth a
        test, because an MCP host grants all of a server's tools together — a
        reader deciding whether to install this needs the answer to be exact."""
        from dogma_service.mcp_server import TOOLS

        writers = [
            tool["name"] for tool in TOOLS
            if "writes" in tool["description"].lower()
            or tool["name"].startswith("record_decision")
        ]
        self.assertEqual(writers, ["record_decision"])

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


class UnmeasuredEdgeVocabularyTests(unittest.TestCase):
    """`list_untested_or_stale_claims` filtered on a state that does not exist.

    The predicate was `edge.get("state") != "tested"`, and "tested" has never been
    a member of `EdgeState` (untested / assessed / examined, plus three
    deprecated). Being the left side of an `or`, it was unconditionally true: the
    tool named for listing untested claims returned every edge, always.

    It looked correct only because `quration_handoff.py` hardcodes every edge to
    "untested", so the two errors cancelled. The test below is the one that could
    not have passed before — a measured edge was still reported as untested,
    which inverts the tool's purpose and is exactly the failure CLAUDE.md records
    as repaired elsewhere: reporting a claim as examined when nothing measured it,
    run in reverse.
    """

    def test_a_measured_edge_is_not_listed_as_unmeasured(self) -> None:
        self.assertFalse(edge_is_unmeasured({"state": "examined"}))

    def test_an_assessed_edge_is_still_unmeasured(self) -> None:
        """A feasibility verdict is not a measurement. This is the distinction the
        whole epistemics layer exists to hold."""
        self.assertTrue(edge_is_unmeasured({"state": "assessed"}))

    def test_an_untested_edge_is_unmeasured(self) -> None:
        self.assertTrue(edge_is_unmeasured({"state": "untested"}))

    def test_the_state_that_was_filtered_on_is_not_a_real_state(self) -> None:
        """Guards the root cause rather than the symptom."""
        self.assertNotIn("tested", KNOWN_EDGE_STATES)

    def test_an_unknown_state_counts_as_unmeasured(self) -> None:
        """Claiming a measurement landed is the assertion needing evidence, so an
        unrecognised value must never be why an edge drops off this list."""
        self.assertTrue(edge_is_unmeasured({"state": "banana"}))
        self.assertTrue(edge_is_unmeasured({}))

    def test_vocabulary_drift_is_reported_rather_than_absorbed(self) -> None:
        payload = call_tool("list_untested_or_stale_claims", {"root": str(DEMO_ROOT)})
        self.assertIn("unrecognised_edge_states", payload)
        self.assertEqual(payload["unrecognised_edge_states"], [])

    def test_the_deprecated_states_are_still_recognised(self) -> None:
        """So real drift is distinguishable from a state this adapter simply
        has not been taught yet."""
        for deprecated in ("contested", "supported", "refuted"):
            self.assertIn(deprecated, KNOWN_EDGE_STATES)


class JsonRpcNotificationTests(unittest.TestCase):
    """A notification has no `id`, and the spec forbids replying to one.

    Only `notifications/initialized` was special-cased; every other notification
    fell through to the unknown-method branch and produced an error response with
    `"id": null`. That fires the first time a host cancels a request or reports
    progress — both routine — and a strict client treats the unsolicited reply as
    a protocol error, which surfaces to the user as the whole server being broken.
    """

    def test_a_cancellation_notification_gets_no_reply(self) -> None:
        response = handle_jsonrpc_message(
            {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}}
        )
        self.assertIsNone(response)

    def test_the_initialized_notification_still_gets_no_reply(self) -> None:
        self.assertIsNone(
            handle_jsonrpc_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
        )

    def test_an_unknown_notification_gets_no_reply(self) -> None:
        """Keyed on the missing `id`, not on a list of known notification names, so
        a notification added in a later protocol version cannot regress this."""
        self.assertIsNone(
            handle_jsonrpc_message({"jsonrpc": "2.0", "method": "notifications/from_the_future"})
        )

    def test_an_unknown_method_WITH_an_id_still_errors(self) -> None:
        """The fix must not silence real requests: a request is owed a reply."""
        response = handle_jsonrpc_message({"jsonrpc": "2.0", "id": 7, "method": "no/such/method"})
        self.assertIsNotNone(response)
        self.assertEqual(response["id"], 7)
        self.assertEqual(response["error"]["code"], -32601)

    def test_id_zero_is_a_request_not_a_notification(self) -> None:
        """`0` is falsy; keying on truthiness instead of `is None` would drop it."""
        response = handle_jsonrpc_message({"jsonrpc": "2.0", "id": 0, "method": "ping"})
        self.assertIsNotNone(response)
        self.assertEqual(response["id"], 0)


if __name__ == "__main__":
    unittest.main()
