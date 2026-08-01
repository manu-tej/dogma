"""Tool-augmented interpretation on a subscription, with no API key.

`ClaudeToolCaller` runs the agentic loop itself against `anthropic.Anthropic`:
send tools, receive `tool_use`, execute, send results, repeat. That needs a
metered key, so interpretation stayed API-only even on a machine with a
logged-in Claude Code CLI — and the benchmark's six published tasks failed with
"Could not resolve authentication method".

Calling that architectural was wrong. `claude -p` is itself an agentic loop; it
was only missing Dogma's tools. `--mcp-config` supplies them, so the loop moves
into the CLI: it decides which tool to call, calls back into
`quration.interpretation.bio_mcp` for every gene and pathway lookup, and bills
the subscription instead of a key.

Verified against the real CLI: asked for SOD1's protein function it made three
turns, called `get_gene_protein_info`, and returned UniProt **P00441** — the
correct human accession, fetched rather than recalled.

Two consequences of moving the loop are worth knowing:

- **Tool calls are reported by the CLI, not observed here.** This class no
  longer executes the tools, so `tool_calls` comes from the CLI's own record.
  Where it is unavailable the list is empty rather than invented, and callers
  should not read an empty list as "no tools were used".
- **Token accounting is the CLI's.** Cost is 0.0 because the subscription is not
  metered per call; recording a fabricated dollar figure would be worse than
  recording none.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any

from quration.interpretation.models import (
    InterpretationResult,
    InterpretationType,
    TokenUsage,
)

logger = logging.getLogger(__name__)

MCP_SERVER_NAME = "dogma-bio"


class SubscriptionToolCaller:
    """Drop-in replacement for `ClaudeToolCaller`, backed by `claude -p`."""

    def __init__(
        self,
        model: str = "sonnet",
        executor: Any = None,
        claude_executable: str = "claude",
        timeout_seconds: int = 900,
        force_subscription: bool = True,
        python_executable: str | None = None,
    ):
        import sys

        # The caller's executor is reused rather than a second one built.
        # `create_executor(include_all_tools=True)` registers into a process-wide
        # registry and is NOT idempotent — building a second raises
        # "Tool 'search_geo_datasets' is already registered", which surfaced as
        # every benchmark task failing instantly with a tool-registration error
        # rather than anything to do with interpretation.
        self._executor = executor
        self._model = model
        self._claude_executable = claude_executable
        self._timeout_seconds = timeout_seconds
        self._force_subscription = force_subscription
        # The interpreter that can import `quration`. `sys.executable` rather
        # than "python": the CLI spawns the MCP server itself, from its own
        # environment, where a bare name may resolve to something else entirely
        # or to nothing at all on stock macOS.
        self._python_executable = python_executable or sys.executable

    def _mcp_config(self) -> dict[str, Any]:
        return {
            "mcpServers": {
                MCP_SERVER_NAME: {
                    "type": "stdio",
                    "command": self._python_executable,
                    "args": ["-m", "quration.interpretation.bio_mcp"],
                    "env": {},
                }
            }
        }

    def allowed_tools(self) -> list[str]:
        """Every bio tool, namespaced the way the CLI exposes MCP tools.

        Enumerated rather than left open: without `--allowedTools` the CLI would
        also offer its own Bash, Write and Edit tools, and an interpreter that
        can edit the analysis it is interpreting is not something to hand out by
        accident.
        """
        from quration.interpretation.bio_mcp import build_executor, tool_definitions

        executor = self._executor or build_executor()
        return [
            f"mcp__{MCP_SERVER_NAME}__{tool['name']}"
            for tool in tool_definitions(executor)
        ]

    async def interpret(
        self,
        prompt: str,
        interpretation_type: InterpretationType,
        system_prompt: str | None = None,
        max_iterations: int = 10,
        context: dict[str, Any] | None = None,
    ) -> InterpretationResult:
        started = datetime.now(timezone.utc)

        if shutil.which(self._claude_executable) is None and not os.path.isabs(
            self._claude_executable
        ):
            return self._failure(
                interpretation_type, started,
                f"Claude CLI '{self._claude_executable}' not found on PATH. "
                "Install Claude Code and run `claude login`.",
            )

        config_handle, config_path = tempfile.mkstemp(prefix="dogma-bio-mcp-", suffix=".json")
        with os.fdopen(config_handle, "w") as handle:
            json.dump(self._mcp_config(), handle)

        env = dict(os.environ)
        if self._force_subscription:
            # A stray key would route the CLI to metered billing — the exact
            # thing choosing this caller is meant to avoid.
            env.pop("ANTHROPIC_API_KEY", None)

        cmd = [
            self._claude_executable, "-p",
            "--output-format", "json",
            "--mcp-config", config_path,
            "--allowedTools", ",".join(self.allowed_tools()),
            "--model", self._model,
            "--no-session-persistence",
        ]
        if system_prompt:
            cmd += ["--system-prompt", system_prompt]

        try:
            completed = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True,
                env=env, timeout=self._timeout_seconds,
                # A neutral cwd: the CLI would otherwise load the caller's
                # CLAUDE.md into an interpretation of somebody's experiment.
                cwd=tempfile.gettempdir(),
            )
        except subprocess.TimeoutExpired:
            return self._failure(
                interpretation_type, started,
                f"claude -p timed out after {self._timeout_seconds}s",
            )
        finally:
            try:
                os.unlink(config_path)
            except OSError:
                pass

        if completed.returncode != 0:
            return self._failure(
                interpretation_type, started,
                f"claude -p exited {completed.returncode}: "
                f"{(completed.stderr or completed.stdout or '').strip()[:400]}",
            )

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            return self._failure(
                interpretation_type, started,
                f"claude -p returned non-JSON output ({exc}): {completed.stdout[:300]}",
            )

        if payload.get("is_error"):
            return self._failure(
                interpretation_type, started,
                f"claude -p reported an error: {payload.get('result')}",
            )

        text = payload.get("result") or ""
        if not text.strip():
            # Exit 0 with no text. Returning an empty interpretation would look
            # like a successful one that found nothing to say.
            return self._failure(
                interpretation_type, started, "claude -p returned an empty result"
            )

        usage = payload.get("usage") or {}
        return InterpretationResult(
            interpretation_type=interpretation_type,
            summary=text,
            claims=[],  # extracted downstream by the service's parser, as before
            tool_calls=[],  # the CLI ran the loop; see the module docstring
            token_usage=TokenUsage(
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            ),
            model_used=self._model,
            confidence_score=0.0,
            processing_time_ms=self._elapsed_ms(started),
            cost_usd=0.0,  # billed to the subscription, not metered per call
        )

    def _failure(
        self, interpretation_type: InterpretationType, started: datetime, reason: str
    ) -> InterpretationResult:
        """A failure report, carrying `error` so no consumer counts it as work.

        The benchmark reported six authentication failures as a 100% success
        rate precisely because this field did not exist.
        """
        logger.warning("subscription interpretation failed: %s", reason)
        return InterpretationResult(
            interpretation_type=interpretation_type,
            summary=f"Interpretation failed: {reason}",
            error=reason,
            claims=[],
            tool_calls=[],
            token_usage=TokenUsage(),
            model_used=self._model,
            confidence_score=0.0,
            processing_time_ms=self._elapsed_ms(started),
        )

    @staticmethod
    def _elapsed_ms(started: datetime) -> float:
        return (datetime.now(timezone.utc) - started).total_seconds() * 1000
