"""Local-only LLM provider status and Claude Code subscription adapter."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping


CLAUDE_SUBSCRIPTION_COMMAND = ["-p", "--output-format", "json", "--safe-mode", "--allowedTools", "", "--no-session-persistence"]
COMMON_CLAUDE_BIN_DIRS = (
    "{home}/.local/bin",
    "{home}/Library/pnpm",
    "{home}/.npm-global/bin",
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/pkg/env/global/bin",
)


def env_get(env: Mapping[str, str], *names: str, default: str | None = None) -> str | None:
    for name in names:
        value = env.get(name)
        if value:
            return value
    return default


def _home_from_env(env: Mapping[str, str] | None = None) -> str:
    if env and env.get("HOME"):
        return env["HOME"]
    return str(Path.home())


def _expand_command_path(command: str, env: Mapping[str, str] | None = None) -> str:
    if command == "~":
        return _home_from_env(env)
    if command.startswith("~/"):
        return str(Path(_home_from_env(env)) / command[2:])
    return str(Path(command).expanduser()) if "/" in command else command


def executable_candidates(command: str, env: Mapping[str, str] | None = None) -> list[str]:
    expanded = _expand_command_path(command, env)
    if "/" in expanded:
        return [expanded]

    candidates: list[str] = []
    seen: set[str] = set()

    def add(candidate: str | None) -> None:
        if candidate and candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)

    add(shutil.which(expanded, path=env.get("PATH") if env is not None else None))
    home = _home_from_env(env)
    for template in COMMON_CLAUDE_BIN_DIRS:
        add(str(Path(template.format(home=home)) / expanded))
    return candidates


def resolve_executable(command: str, env: Mapping[str, str] | None = None) -> str | None:
    for candidate in executable_candidates(command, env):
        path = Path(candidate)
        if path.exists() and os.access(path, os.X_OK):
            return str(path.resolve())
    return None


def resolve_executable_with_attempts(command: str, env: Mapping[str, str] | None = None) -> tuple[str | None, list[str]]:
    candidates = executable_candidates(command, env)
    for candidate in candidates:
        path = Path(candidate)
        if path.exists() and os.access(path, os.X_OK):
            return str(path.resolve()), candidates
    return None, candidates


def check_version(executable: str | None) -> dict[str, Any]:
    if not executable:
        return {"ok": False, "version": None, "error": "claude executable not found"}
    try:
        completed = subprocess.run(
            [executable, "--version"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"ok": False, "version": None, "error": str(error)}

    output = (completed.stdout or completed.stderr).strip()
    return {
        "ok": completed.returncode == 0,
        "version": output or None,
        "error": None if completed.returncode == 0 else output or f"exit {completed.returncode}",
    }


def build_llm_status(env: Mapping[str, str] | None = None, check_cli: bool = True) -> dict[str, Any]:
    values = os.environ if env is None else env
    provider = env_get(values, "DOGMA_LLM_PROVIDER", "BIOCURSOR_LLM_PROVIDER", "QURATION_PROVIDER", default="none")
    claude_cli = env_get(values, "DOGMA_CLAUDE_CLI_PATH", "BIOCURSOR_CLAUDE_CLI_PATH", "CLAUDE_CLI_PATH", default="claude") or "claude"
    model = env_get(values, "DOGMA_CLAUDE_MODEL", "BIOCURSOR_CLAUDE_MODEL", "QURATION_CLAUDE_MODEL", default="sonnet")
    timeout_seconds = int(env_get(values, "DOGMA_LLM_TIMEOUT_SECONDS", "BIOCURSOR_LLM_TIMEOUT_SECONDS", "CLAUDE_TIMEOUT_SECONDS", default="180") or "180")
    executable, attempted_paths = resolve_executable_with_attempts(claude_cli, values)
    version = check_version(executable) if check_cli and provider == "claude_subscription" else {"ok": bool(executable), "version": None, "error": None if executable else "claude executable not found"}
    configured = provider != "none"

    status = "not_configured"
    if provider == "claude_subscription":
        status = "ready" if version.get("ok") else "needs_claude_login_or_cli"
    elif configured:
        status = "configured_external_provider"

    result = {
        "service": "dogma-local-service",
        "status": status,
        "provider": provider,
        "local_only": provider == "claude_subscription",
        "configured": configured,
        "claude_subscription": {
            "cli_path": claude_cli,
            "resolved_cli_path": executable,
            "attempted_cli_paths": attempted_paths,
            "model": model,
            "timeout_seconds": timeout_seconds,
            "force_subscription_oauth": provider == "claude_subscription",
            "tools_disabled": True,
            "no_session_persistence": True,
            "anthropic_api_key_stripped": provider == "claude_subscription",
            "version_check": version,
        },
        "policy": [
            "Use Claude Code subscription mode only for local single-operator Dogma service calls.",
            "Keep LLM output typed: the model proposes JSON/text decisions; Python executes only whitelisted biomedical actions.",
            "Do not expose raw Claude tool access or project-level agent prompts to the extension.",
            "Redact human-data context before sending prompts unless workspace trust and policy allow disclosure.",
            "Hosted or shared Dogma deployments should use API-key providers instead of Claude Code subscription auth.",
        ],
    }
    result["markdown"] = render_llm_status_markdown(result)
    return result


class ClaudeSubscriptionProvider:
    """Minimal Claude Code subscription adapter following quration's local pattern."""

    def __init__(self, cli_path: str = "claude", model: str = "sonnet", timeout_seconds: int = 180) -> None:
        executable = resolve_executable(cli_path)
        if not executable:
            raise FileNotFoundError(f"Claude CLI executable not found: {cli_path}")
        self.cli_path = executable
        self.model = model
        self.timeout_seconds = timeout_seconds

    def create_message(self, prompt: str) -> str:
        command = [self.cli_path, *CLAUDE_SUBSCRIPTION_COMMAND, "--model", self.model]
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        with tempfile.TemporaryDirectory(prefix="dogma-claude-") as tmp:
            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=tmp,
                env=env,
                timeout=self.timeout_seconds,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout or f"Claude CLI exited {completed.returncode}").strip())
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Claude CLI returned invalid JSON: {error.msg}") from error
        result = payload.get("result")
        if not isinstance(result, str):
            raise RuntimeError("Claude CLI JSON response did not include a string result.")
        return result


def render_llm_status_markdown(result: dict[str, Any]) -> str:
    subscription = result.get("claude_subscription", {})
    version = subscription.get("version_check", {})
    policy_rows = [f"- {item}" for item in result.get("policy", [])]
    return "\n".join(
        [
            "# Dogma LLM Provider Status",
            "",
            "Dogma follows quration's provider pattern: the local service owns typed biomedical actions, while the LLM proposes structured decisions.",
            "",
            "## Provider",
            "",
            f"- Status: {result.get('status')}",
            f"- Provider: {result.get('provider')}",
            f"- Configured: {str(bool(result.get('configured'))).lower()}",
            f"- Local-only mode: {str(bool(result.get('local_only'))).lower()}",
            "",
            "## Claude Code Subscription",
            "",
            f"- CLI path: {subscription.get('cli_path')}",
            f"- Resolved CLI path: {subscription.get('resolved_cli_path') or 'not found'}",
            f"- Attempted CLI paths: {', '.join(subscription.get('attempted_cli_paths') or []) or 'none'}",
            f"- Model alias: {subscription.get('model')}",
            f"- Timeout seconds: {subscription.get('timeout_seconds')}",
            f"- Tools disabled: {str(bool(subscription.get('tools_disabled'))).lower()}",
            f"- No session persistence: {str(bool(subscription.get('no_session_persistence'))).lower()}",
            f"- ANTHROPIC_API_KEY stripped: {str(bool(subscription.get('anthropic_api_key_stripped'))).lower()}",
            f"- Version check: {'ok' if version.get('ok') else version.get('error') or 'not checked'}",
            "",
            "## Policy",
            "",
            *policy_rows,
            "",
        ]
    )
