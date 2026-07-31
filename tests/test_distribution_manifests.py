"""The skill has to be discoverable, and stay discoverable.

Before this, the method-validity skill sat at `dogma-science-skill/method-validity/`
— a path nothing auto-discovers — and its README documented the only install route
as hand-typing `host.skills.edit` calls. Distribution was effectively zero.

It now lives at `.claude/skills/method-validity/`, which a fresh clone picks up with
no copying, and `.claude-plugin/` publishes that same directory as an installable
plugin. One copy, two channels.

These assertions exist because a manifest that points at a moved directory fails
silently: nothing errors, the skill simply never loads. That is the same failure
mode as the `generateMockBio` pattern in check-public-safety, which guarded a
deleted function and so passed vacuously for however long.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PLUGIN_MANIFEST = REPO / ".claude-plugin" / "plugin.json"
MARKETPLACE_MANIFEST = REPO / ".claude-plugin" / "marketplace.json"
MCP_MANIFEST = REPO / ".mcp.json"
SKILL_DIR = REPO / ".claude" / "skills" / "method-validity"


def _load(path: Path) -> dict:
    assert path.exists(), f"{path.relative_to(REPO)} is missing"
    return json.loads(path.read_text())


class TestSkillIsDiscoverable:
    def test_skill_lives_where_a_fresh_clone_looks(self):
        assert SKILL_DIR.is_dir()
        assert (SKILL_DIR / "SKILL.md").exists()

    def test_skill_has_the_frontmatter_discovery_needs(self):
        text = (SKILL_DIR / "SKILL.md").read_text()
        assert text.startswith("---"), "SKILL.md needs YAML frontmatter"
        frontmatter = text.split("---", 2)[1]
        # `description` is what the model matches on to decide whether to load the
        # skill; without it the skill is installed but never triggers.
        for field in ("name:", "description:"):
            assert field in frontmatter, f"SKILL.md frontmatter is missing {field!r}"

    def test_the_kernel_the_skill_calls_is_beside_it(self):
        # SKILL.md tells the model the helpers are auto-injected from kernel.py.
        assert (SKILL_DIR / "kernel.py").exists()

    def test_the_skill_keeps_its_own_tests(self):
        assert list((SKILL_DIR / "tests").glob("test_*.py"))


class TestPluginManifest:
    def test_manifest_parses_and_is_named(self):
        manifest = _load(PLUGIN_MANIFEST)
        assert manifest["name"] == "dogma-method-validity"

    def test_the_declared_skills_path_actually_exists(self):
        """The failure this test is really for. A stale path here means the plugin
        installs cleanly and provides nothing."""
        declared = _load(PLUGIN_MANIFEST)["skills"]
        assert declared.startswith("./"), "plugin paths must be relative and start with ./"
        resolved = (REPO / declared[2:]).resolve()
        assert resolved.is_dir(), f"plugin.json points at {declared}, which does not exist"
        assert any(
            child.joinpath("SKILL.md").exists() for child in resolved.iterdir() if child.is_dir()
        ), f"{declared} contains no skill directory with a SKILL.md"

    def test_no_absolute_paths_leaked_into_the_manifest(self):
        raw = PLUGIN_MANIFEST.read_text()
        assert "/Users/" not in raw, "a developer-local absolute path leaked in"


class TestMarketplaceManifest:
    def test_manifest_parses_and_lists_the_plugin(self):
        marketplace = _load(MARKETPLACE_MANIFEST)
        names = [p["name"] for p in marketplace["plugins"]]
        assert "dogma-method-validity" in names

    def test_every_listed_plugin_source_resolves(self):
        for plugin in _load(MARKETPLACE_MANIFEST)["plugins"]:
            source = plugin["source"]
            assert (REPO / source).is_dir(), f"{plugin['name']} source {source!r} missing"

    def test_listed_names_match_the_plugin_manifest(self):
        """A mismatch installs under one name and resolves under another."""
        marketplace = _load(MARKETPLACE_MANIFEST)
        own = _load(PLUGIN_MANIFEST)["name"]
        sources = {p["name"]: p["source"] for p in marketplace["plugins"]}
        assert sources.get(own) == "./", f"{own} is not listed against this repo root"


class TestTheOldPathIsGone:
    def test_nothing_still_points_at_the_pre_move_location(self):
        """A half-finished move is worse than none: the tests would run against a
        path that no longer exists, and CI would fail for an unrelated-looking
        reason."""
        stale = []
        for pattern in ("*.md", "*.json", "*.yml", "*.yaml"):
            for path in REPO.rglob(pattern):
                parts = set(path.parts)
                if parts & {"node_modules", ".venv", ".git", "dist", "build"}:
                    continue
                try:
                    text = path.read_text()
                except (UnicodeDecodeError, OSError):
                    continue
                # The MIGRATION.md line documents the rename on purpose.
                if "dogma-science-skill" in text and "was `dogma-science-skill" not in text:
                    stale.append(str(path.relative_to(REPO)))
        assert not stale, f"stale references to the old skill path: {stale}"


class TestMcpServerIsRegistered:
    """The server worked and nothing pointed at it.

    `dogma-service mcp` has always spoken JSON-RPC over stdio and exposes six tools,
    but with no `.mcp.json` a clone had no way to reach it — the same gap the skill
    had. Transport choice is settled in
    docs/decisions/2026-07-30-mcp-transport-stays-stdio.md: stdio is correct for a
    tool that reads a local workspace, and HTTP would mean exposing it publicly.
    """

    def test_the_server_is_declared(self):
        servers = _load(MCP_MANIFEST)["mcpServers"]
        assert "dogma-evidence-control-plane" in servers

    def test_it_uses_stdio(self):
        server = _load(MCP_MANIFEST)["mcpServers"]["dogma-evidence-control-plane"]
        assert server["type"] == "stdio"
        # A url would mean the local-workspace tool had been exposed over a network.
        assert "url" not in server

    def test_the_command_matches_a_real_entry_point(self):
        """Declaring the server is not the same as being able to start it.

        This asserted `"command": "python", "args": ["-m", "dogma_service",
        "mcp"]` — a shape that is only launchable from a venv-activated shell
        with one specific working directory. `python` is not a command on stock
        macOS, and MCP hosts launch servers from their own environment, so the
        manifest was registering an entry point no external host could reach.
        The test passed because it checked the string against itself.

        Checking that the command is an executable file is what makes this
        falsifiable: `bin/dogma` resolves its own interpreter and exports the
        PYTHONPATH the service needs.
        """
        server = _load(MCP_MANIFEST)["mcpServers"]["dogma-evidence-control-plane"]
        assert server["args"] == ["mcp"]
        command = (REPO / server["command"]).resolve()
        assert command.is_file(), f"{server['command']} is not a file"
        assert os.access(command, os.X_OK), f"{server['command']} is not executable"
        cli = REPO / "dogma-local-service" / "dogma_service" / "cli.py"
        assert 'add_parser("mcp"' in cli.read_text(), "the `mcp` subcommand is gone"

    def test_the_declared_command_actually_serves_tools(self):
        """The end the manifest exists for, exercised rather than assumed."""
        server = _load(MCP_MANIFEST)["mcpServers"]["dogma-evidence-control-plane"]
        env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "VIRTUAL_ENV"}}
        result = subprocess.run(
            [str((REPO / server["command"]).resolve()), *server["args"]],
            input='{"jsonrpc":"2.0","id":1,"method":"tools/list"}\n',
            cwd=tempfile.gettempdir(),  # never the repo: hosts launch from elsewhere
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        tools = json.loads(result.stdout.strip())["result"]["tools"]
        assert {t["name"] for t in tools} >= {"create_claim_graph", "check_method_assumptions"}

    def test_no_absolute_paths_leaked(self):
        assert "/Users/" not in MCP_MANIFEST.read_text()


@pytest.mark.parametrize("path", [PLUGIN_MANIFEST, MARKETPLACE_MANIFEST, MCP_MANIFEST])
def test_manifests_are_valid_json(path: Path):
    json.loads(path.read_text())
