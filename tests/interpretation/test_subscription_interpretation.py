"""Tool-augmented interpretation without an API key.

`ClaudeToolCaller` runs the agentic loop itself against `anthropic.Anthropic`,
so interpretation needed a metered key even on a machine with a logged-in Claude
Code CLI — and `--published` failed all six tasks on authentication.

That was called architectural, on the reasoning that a one-shot `claude -p`
completion cannot run a tool loop. The reasoning was wrong. `claude -p` *is* an
agentic loop; it was only missing Dogma's tools. `--mcp-config` supplies them,
so the loop moves into the CLI and the subscription pays for it.

The properties below are the ones that break quietly:

  - Building a second executor to list tool names raises "Tool
    'search_geo_datasets' is already registered". That surfaced as every task
    failing instantly with a registration error rather than anything about
    interpretation.
  - Without `--allowedTools` the CLI also offers Bash, Write and Edit, so an
    interpreter could edit the analysis it is interpreting.
  - A stray `ANTHROPIC_API_KEY` reroutes the CLI to metered billing.
  - An empty result must be a failure, not an interpretation that found nothing
    to say.
"""

from __future__ import annotations

import pytest

from quration.interpretation.models import InterpretationType
from quration.interpretation.subscription_caller import (
    MCP_SERVER_NAME,
    SubscriptionToolCaller,
)


class _FakeExecutor:
    """Stands in for the shared executor so no tool registration happens."""

    def get_tool_definitions(self):
        return [
            {"name": "get_gene_info", "description": "d", "input_schema": {"type": "object"}},
            {"name": "search_pubmed", "description": "d", "input_schema": {"type": "object"}},
        ]


class TestTheToolBeltIsScopedAndNamespaced:
    def test_tools_are_namespaced_the_way_the_cli_exposes_mcp(self):
        caller = SubscriptionToolCaller(executor=_FakeExecutor())
        assert caller.allowed_tools() == [
            f"mcp__{MCP_SERVER_NAME}__get_gene_info",
            f"mcp__{MCP_SERVER_NAME}__search_pubmed",
        ]

    def test_no_file_editing_tool_is_allowed(self):
        """Left open, the CLI also offers Bash/Write/Edit. An interpreter that
        can edit the analysis it is interpreting is not something to hand out by
        accident."""
        allowed = SubscriptionToolCaller(executor=_FakeExecutor()).allowed_tools()
        for dangerous in ("Bash", "Write", "Edit", "NotebookEdit"):
            assert not any(dangerous in tool for tool in allowed)

    def test_it_reuses_the_given_executor(self):
        """`create_executor(include_all_tools=True)` registers into a
        process-wide registry and is NOT idempotent — a second one raises
        "Tool 'search_geo_datasets' is already registered"."""
        caller = SubscriptionToolCaller(executor=_FakeExecutor())
        assert caller._executor is not None
        assert len(caller.allowed_tools()) == 2


class TestTheMcpConfigPointsAtAnInterpreterThatCanImportQuration:
    def test_it_uses_an_absolute_interpreter(self):
        """`sys.executable`, not "python". The CLI spawns this server from its
        own environment, where a bare name may resolve elsewhere or, on stock
        macOS, to nothing."""
        import os

        config = SubscriptionToolCaller(executor=_FakeExecutor())._mcp_config()
        command = config["mcpServers"][MCP_SERVER_NAME]["command"]
        assert os.path.isabs(command)

    def test_it_serves_the_bio_module(self):
        config = SubscriptionToolCaller(executor=_FakeExecutor())._mcp_config()
        server = config["mcpServers"][MCP_SERVER_NAME]
        assert server["args"] == ["-m", "quration.interpretation.bio_mcp"]
        assert server["type"] == "stdio"


class TestFailuresAreReportedNotSwallowed:
    def _run(self, caller):
        import asyncio

        return asyncio.run(
            caller.interpret(prompt="p", interpretation_type=InterpretationType.DEG_ANALYSIS)
        )

    def test_a_missing_cli_is_a_failure_with_a_remedy(self):
        caller = SubscriptionToolCaller(
            executor=_FakeExecutor(), claude_executable="claude-not-installed"
        )
        result = self._run(caller)
        assert result.failed is True
        assert "claude login" in result.error

    def test_an_empty_result_is_a_failure(self, monkeypatch):
        """Exit 0 with no text. Returning it as an interpretation would look
        like one that found nothing to say."""
        import subprocess

        class _Completed:
            returncode = 0
            stdout = '{"is_error": false, "result": "   "}'
            stderr = ""

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Completed())
        monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/claude")
        result = self._run(SubscriptionToolCaller(executor=_FakeExecutor()))
        assert result.failed is True
        assert "empty" in result.error

    def test_a_reported_cli_error_is_a_failure(self, monkeypatch):
        import subprocess

        class _Completed:
            returncode = 0
            stdout = '{"is_error": true, "result": "usage limit reached"}'
            stderr = ""

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Completed())
        monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/claude")
        result = self._run(SubscriptionToolCaller(executor=_FakeExecutor()))
        assert result.failed is True
        assert "usage limit" in result.error

    def test_a_real_result_is_not_a_failure(self, monkeypatch):
        import subprocess

        class _Completed:
            returncode = 0
            stdout = '{"is_error": false, "result": "EGFR is upregulated (UniProt P00533)."}'
            stderr = ""

        monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Completed())
        monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/claude")
        result = self._run(SubscriptionToolCaller(executor=_FakeExecutor()))
        assert result.failed is False
        assert "P00533" in result.summary
        # Not metered per call, and inventing a dollar figure would be worse
        # than recording none.
        assert result.cost_usd == 0.0


class TestSubscriptionAuthIsForced:
    def test_a_stray_api_key_is_removed(self, monkeypatch):
        import subprocess

        seen = {}

        class _Completed:
            returncode = 0
            stdout = '{"is_error": false, "result": "ok"}'
            stderr = ""

        def fake_run(*args, **kwargs):
            seen["env"] = kwargs.get("env") or {}
            return _Completed()

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-reach-the-cli")
        monkeypatch.setattr(subprocess, "run", fake_run)
        monkeypatch.setattr("shutil.which", lambda _: "/usr/local/bin/claude")

        import asyncio

        asyncio.run(
            SubscriptionToolCaller(executor=_FakeExecutor()).interpret(
                prompt="p", interpretation_type=InterpretationType.DEG_ANALYSIS
            )
        )
        assert "ANTHROPIC_API_KEY" not in seen["env"]


class TestTheBioMcpSurface:
    def test_it_translates_the_schema_key(self):
        """Anthropic says `input_schema`; MCP says `inputSchema`. Same tools,
        one letter apart, and the CLI silently sees no tools if it is wrong."""
        from quration.interpretation.bio_mcp import tool_definitions

        tools = tool_definitions(_FakeExecutor())
        assert all("inputSchema" in tool for tool in tools)
        assert all("input_schema" not in tool for tool in tools)

    def test_a_notification_gets_no_reply(self):
        """Keyed on the missing id, not a list of method names — the same defect
        was found and fixed in the workspace MCP server."""
        from quration.interpretation.bio_mcp import handle_message

        assert handle_message(_FakeExecutor(), {"jsonrpc": "2.0", "method": "notifications/cancelled"}) is None

    def test_an_unknown_method_with_an_id_still_errors(self):
        from quration.interpretation.bio_mcp import handle_message

        response = handle_message(_FakeExecutor(), {"jsonrpc": "2.0", "id": 3, "method": "no/such"})
        assert response["error"]["code"] == -32601

    def test_tools_list_serves_the_executor_s_tools(self):
        from quration.interpretation.bio_mcp import handle_message

        response = handle_message(_FakeExecutor(), {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert {t["name"] for t in response["result"]["tools"]} == {
            "get_gene_info",
            "search_pubmed",
        }


class TestProviderSelectionIsExplicit:
    """Chosen from config, not by sniffing for a key. Switching billing mode
    because an unrelated variable appeared is the silent surprise this codebase
    keeps removing."""

    @pytest.mark.parametrize(
        "provider,expected",
        [("claude_subscription", True), ("anthropic", False), ("demo", False), ("", False)],
    )
    def test_only_a_configured_subscription_selects_the_cli(self, monkeypatch, provider, expected):
        from types import SimpleNamespace

        from quration.interpretation import service as service_module

        monkeypatch.setattr(
            service_module, "get_config",
            lambda: SimpleNamespace(llm=SimpleNamespace(provider=provider)),
        )
        assert service_module._subscription_interpretation_configured() is expected

    def test_codex_does_not_claim_support_it_lacks(self, monkeypatch):
        """Codex drives an agent too, but Dogma's tools are not wired into it.
        Claiming support would mean answering from memory instead of UniProt."""
        from types import SimpleNamespace

        from quration.interpretation import service as service_module

        monkeypatch.setattr(
            service_module, "get_config",
            lambda: SimpleNamespace(llm=SimpleNamespace(provider="codex_subscription")),
        )
        assert service_module._subscription_interpretation_configured() is False
