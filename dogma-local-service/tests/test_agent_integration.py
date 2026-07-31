"""Dogma has to be usable BY other coding agents, not just worked on by them.

That promise reduces to four mechanical properties, and every one of them was
broken before this file existed:

  1. The launcher works from any working directory. `.mcp.json` used to say
     `"command": "python", "args": ["-m", "dogma_service", "mcp"]`. That
     works in a venv-activated shell and nowhere else: `python` is not a command
     on stock macOS, and MCP hosts launch servers from their own environment
     rather than the user's login shell. The server simply never started, and a
     server that never starts looks to the user like a tool with no biology
     tools rather than like a misconfiguration.

  2. The launcher needs no virtualenv. The MCP server imports only the standard
     library, so a fresh clone with no `.venv` can still serve tools. Nothing
     enforced that, and one third-party import would have silently reimposed the
     install step on every external host.

  3. The launcher never writes to stdout. In `mcp` mode stdout *is* the JSON-RPC
     channel; one stray `echo` corrupts the stream and the host reports a
     protocol error that names neither the shell nor the line.

  4. When it cannot start, it says so on stderr and exits non-zero. The previous
     failure mode was a server that silently did not appear, which reads to a
     user as "this tool has no biology tools" rather than "this tool is
     misconfigured".
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "bin" / "dogma"
DEMO_WORKSPACE = REPO_ROOT / "dogma-demo-workspace"


def foreign_env() -> dict[str, str]:
    """An environment with every hint about this repo removed.

    Without this the test can pass on a PYTHONPATH the launcher did not set,
    which is precisely the accident that hid the original bug.
    """
    env = dict(os.environ)
    for leaked in ("PYTHONPATH", "VIRTUAL_ENV", "DOGMA_PYTHON"):
        env.pop(leaked, None)
    return env


def system_python() -> str | None:
    """An interpreter that CANNOT import `dogma_service` unaided.

    That is the requirement stated directly, rather than via the proxy "is it
    outside the venv" — which was wrong twice over. `npm run install:python`
    editable-installs `dogma-local-service` into `.venv`, so a set-up machine
    imports `dogma_service` with no PYTHONPATH at all and the launcher's
    export becomes invisible; deleting it leaves every other test in this file
    green. And the documented workflow puts `.venv/bin` on PATH, so a PATH
    lookup for `python3` returns the venv copy and the proxy check skipped the
    only two tests that catch the regression.

    So: probe candidates and return the first that genuinely fails the import.
    Absolute well-known paths are included because PATH may contain nothing but
    the venv.
    """
    candidates = [shutil.which(name) for name in ("python3", "python")]
    candidates += [
        "/usr/bin/python3",
        "/usr/local/bin/python3",
        "/opt/homebrew/bin/python3",
    ]
    unimportable = foreign_env()  # foreign_env() already drops PYTHONPATH
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen or not os.path.exists(candidate):
            continue
        seen.add(candidate)
        probe = subprocess.run(
            [candidate, "-c", "import dogma_service"],
            env=unimportable,
            # Neutral cwd: the suite runs from `dogma-local-service/`, which puts
            # `dogma_service` on sys.path implicitly, so probing in place
            # makes every candidate look capable and skips these tests.
            cwd=tempfile.gettempdir(),
            capture_output=True,
            timeout=60,
        )
        if probe.returncode != 0:
            return candidate
    return None


def run_launcher(args, stdin_text="", cwd=None, env=None):
    return subprocess.run(
        [str(LAUNCHER), *args],
        input=stdin_text,
        cwd=str(cwd) if cwd else tempfile.gettempdir(),
        env=env if env is not None else foreign_env(),
        capture_output=True,
        text=True,
        timeout=120,
    )


def rpc(method, message_id=1, params=None):
    message = {"jsonrpc": "2.0", "id": message_id, "method": method}
    if params is not None:
        message["params"] = params
    return json.dumps(message) + "\n"


class TestLauncherExists(unittest.TestCase):
    def test_the_launcher_is_present_and_executable(self):
        self.assertTrue(LAUNCHER.is_file(), f"{LAUNCHER} is missing")
        self.assertTrue(
            os.access(LAUNCHER, os.X_OK),
            f"{LAUNCHER} is not executable; git tracks the executable bit, so "
            "this breaks for every fresh clone, not just this one",
        )


class TestWorksFromAnyDirectory(unittest.TestCase):
    """Property 1. The regression this file exists for."""

    def test_tools_list_answers_from_an_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            result = run_launcher(["mcp"], rpc("tools/list"), cwd=elsewhere)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout.strip())
        names = {tool["name"] for tool in payload["result"]["tools"]}
        self.assertIn("check_method_assumptions", names)

    def test_a_tool_call_answers_from_an_unrelated_directory(self):
        call = rpc(
            "tools/call",
            message_id=2,
            params={
                "name": "check_method_assumptions",
                "arguments": {"root": str(DEMO_WORKSPACE)},
            },
        )
        with tempfile.TemporaryDirectory() as elsewhere:
            result = run_launcher(["mcp"], call, cwd=elsewhere)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout.strip())
        self.assertFalse(payload["result"]["isError"], payload)
        self.assertEqual(
            payload["result"]["structuredContent"]["tool"], "check_method_assumptions"
        )

    def test_the_cli_mode_also_answers_from_an_unrelated_directory(self):
        """Agents that cannot speak MCP reach the same facts over argv."""
        with tempfile.TemporaryDirectory() as elsewhere:
            result = run_launcher(
                ["guardrails", str(DEMO_WORKSPACE)], cwd=elsewhere
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("workflow_steps", json.loads(result.stdout))


class TestNeedsNoVirtualenv(unittest.TestCase):
    """Property 2. The zero-install promise, stated as an import constraint.

    The two tests below are the ones that actually fail when the launcher stops
    exporting PYTHONPATH — every other test in this file keeps passing on a
    developer machine, because the venv's editable install covers the gap.
    """

    def setUp(self):
        interpreter = system_python()
        if interpreter is None:
            self.skipTest("no interpreter outside the repo venv on this machine")
        self.interpreter: str = interpreter

    def _foreign_interpreter_env(self) -> dict[str, str]:
        env = foreign_env()
        env["DOGMA_PYTHON"] = self.interpreter
        return env

    def test_an_interpreter_that_never_installed_dogma_can_still_serve_tools(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            result = run_launcher(
                ["mcp"],
                rpc("tools/list"),
                cwd=elsewhere,
                env=self._foreign_interpreter_env(),
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout.strip())
        self.assertIn(
            "create_claim_graph",
            {tool["name"] for tool in payload["result"]["tools"]},
            "the launcher only works when the venv already has the package, "
            "which is exactly the install step external agents cannot perform",
        )

    def test_an_interpreter_that_never_installed_dogma_can_answer_a_tool_call(self):
        call = rpc(
            "tools/call",
            message_id=2,
            params={
                "name": "check_method_assumptions",
                "arguments": {"root": str(DEMO_WORKSPACE)},
            },
        )
        with tempfile.TemporaryDirectory() as elsewhere:
            result = run_launcher(
                ["mcp"], call, cwd=elsewhere, env=self._foreign_interpreter_env()
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout.strip())["result"]["isError"])

    @unittest.skipIf(
        not hasattr(sys, "stdlib_module_names"), "needs Python 3.10+ to enumerate stdlib"
    )
    def test_the_mcp_server_imports_only_the_standard_library(self):
        probe = (
            "import sys, importlib\n"
            "before = set(sys.modules)\n"
            "importlib.import_module('dogma_service.mcp_server')\n"
            "roots = {m.split('.')[0] for m in set(sys.modules) - before}\n"
            "std = set(sys.stdlib_module_names)\n"
            "print(sorted(m for m in roots if m not in std "
            "and not m.startswith('_') and m != 'dogma_service'))\n"
        )
        env = foreign_env()
        env["PYTHONPATH"] = str(REPO_ROOT / "dogma-local-service")
        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=tempfile.gettempdir(),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        third_party = json.loads(result.stdout.replace("'", '"'))
        self.assertEqual(
            third_party,
            [],
            "the MCP server grew a third-party import. That silently reimposes "
            "`pip install` on every external MCP host, which is the coupling "
            "bin/dogma exists to remove.",
        )


class TestStdoutStaysClean(unittest.TestCase):
    """Property 3. stdout is the protocol; the shell must stay off it."""

    def test_every_stdout_line_is_json_rpc(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            result = run_launcher(
                ["mcp"], rpc("initialize", params={}) + rpc("tools/list", 2), cwd=elsewhere
            )
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 2, f"unexpected stdout: {result.stdout!r}")
        for line in lines:
            message = json.loads(line)
            self.assertEqual(message["jsonrpc"], "2.0")

    def test_a_bad_interpreter_hint_does_not_pollute_stdout(self):
        """A diagnostic printed to stdout would be indistinguishable from a
        reply, so the host would fail to parse rather than report the cause."""
        env = foreign_env()
        env["DOGMA_PYTHON"] = "/nonexistent/python"
        with tempfile.TemporaryDirectory() as elsewhere:
            result = run_launcher(["mcp"], rpc("tools/list"), cwd=elsewhere, env=env)
        for line in result.stdout.splitlines():
            if line.strip():
                json.loads(line)  # raises if the shell wrote anything here


class TestFailsLoudly(unittest.TestCase):
    """Property 4. Silence is the failure mode being designed out."""

    def test_a_launcher_moved_away_from_the_repo_explains_itself(self):
        with tempfile.TemporaryDirectory() as orphanage:
            stranded = Path(orphanage) / "bin" / "dogma"
            stranded.parent.mkdir()
            shutil.copy2(LAUNCHER, stranded)
            result = subprocess.run(
                [str(stranded), "mcp"],
                input="",
                capture_output=True,
                text=True,
                env=foreign_env(),
                timeout=60,
            )
        self.assertNotEqual(result.returncode, 0, "a stranded launcher exited 0")
        self.assertEqual(result.stdout, "", "diagnostics belong on stderr")
        self.assertIn("dogma-local-service", result.stderr)


class TestConfiguredEntryPointsAreReal(unittest.TestCase):
    """The configs shipped to other agents must name things that exist."""

    def test_mcp_json_points_at_the_launcher(self):
        config = json.loads((REPO_ROOT / ".mcp.json").read_text())
        server = config["mcpServers"]["dogma-evidence-control-plane"]
        command = (REPO_ROOT / server["command"]).resolve()
        self.assertTrue(command.is_file(), f"{server['command']} does not exist")
        self.assertTrue(os.access(command, os.X_OK), f"{server['command']} is not executable")
        self.assertEqual(server["args"], ["mcp"])

    def test_agents_md_documents_the_real_tool_names(self):
        """Other agents act on this file without reading the source."""
        from dogma_service.mcp_server import tool_names

        agents_md = (REPO_ROOT / "AGENTS.md").read_text()
        for name in tool_names():
            self.assertIn(name, agents_md, f"AGENTS.md omits the {name} tool")

    def test_agents_md_cli_examples_name_real_subcommands(self):
        from dogma_service.cli import build_parser

        agents_md = (REPO_ROOT / "AGENTS.md").read_text()
        known: set[str] = set()
        for action in build_parser()._actions:
            if isinstance(action, argparse._SubParsersAction):
                known.update(action.choices or {})
        cited = {
            line.split("bin/dogma ", 1)[1].split()[0]
            for line in agents_md.splitlines()
            if "bin/dogma " in line and not line.strip().startswith("|")
        }
        for subcommand in cited - {"--help"}:
            self.assertIn(subcommand, known, f"AGENTS.md cites `bin/dogma {subcommand}`, which does not exist")


if __name__ == "__main__":
    unittest.main()
