from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from biocursor_service.cli import main
from biocursor_service.llm_provider import build_llm_status, resolve_executable


class LlmProviderTests(unittest.TestCase):
    def test_unconfigured_status(self) -> None:
        result = build_llm_status(env={}, check_cli=False)

        self.assertEqual(result["status"], "not_configured")
        self.assertEqual(result["provider"], "none")
        self.assertFalse(result["local_only"])
        self.assertIn("Dogma LLM Provider Status", result["markdown"])

    def test_claude_subscription_status_without_cli(self) -> None:
        result = build_llm_status(
            env={
                "DOGMA_LLM_PROVIDER": "claude_subscription",
                "DOGMA_CLAUDE_CLI_PATH": "/definitely/missing/claude",
                "DOGMA_CLAUDE_MODEL": "sonnet",
            },
            check_cli=True,
        )

        self.assertEqual(result["status"], "needs_claude_login_or_cli")
        self.assertTrue(result["local_only"])
        self.assertTrue(result["claude_subscription"]["force_subscription_oauth"])
        self.assertTrue(result["claude_subscription"]["tools_disabled"])
        self.assertTrue(result["claude_subscription"]["anthropic_api_key_stripped"])
        self.assertIn("/definitely/missing/claude", result["claude_subscription"]["attempted_cli_paths"])

    def test_claude_subscription_discovers_user_local_bin_without_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_home = Path(tmp)
            bin_dir = fake_home / ".local" / "bin"
            bin_dir.mkdir(parents=True)
            claude = bin_dir / "claude"
            claude.write_text("#!/bin/sh\necho '9.9.9 (Claude Code test)'\n", encoding="utf-8")
            claude.chmod(0o755)

            result = build_llm_status(
                env={
                    "DOGMA_LLM_PROVIDER": "claude_subscription",
                    "DOGMA_CLAUDE_CLI_PATH": "claude",
                    "DOGMA_CLAUDE_MODEL": "sonnet",
                    "HOME": str(fake_home),
                    "PATH": "",
                },
                check_cli=True,
            )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["provider"], "claude_subscription")
        self.assertEqual(result["claude_subscription"]["resolved_cli_path"], str(claude.resolve()))
        self.assertIn(str(claude), result["claude_subscription"]["attempted_cli_paths"])
        self.assertEqual(result["claude_subscription"]["version_check"]["version"], "9.9.9 (Claude Code test)")

    def test_resolve_executable_honors_tilde_home_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_home = Path(tmp)
            bin_dir = fake_home / "bin"
            bin_dir.mkdir()
            tool = bin_dir / "claude"
            tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            tool.chmod(0o755)

            resolved = resolve_executable("~/bin/claude", {"HOME": str(fake_home), "PATH": ""})

        self.assertEqual(resolved, str(tool.resolve()))

    def test_legacy_biocursor_env_alias_still_works(self) -> None:
        result = build_llm_status(
            env={
                "BIOCURSOR_LLM_PROVIDER": "claude_subscription",
                "BIOCURSOR_CLAUDE_CLI_PATH": "/definitely/missing/claude",
            },
            check_cli=True,
        )

        self.assertEqual(result["provider"], "claude_subscription")
        self.assertEqual(result["claude_subscription"]["cli_path"], "/definitely/missing/claude")

    def test_cli_writes_llm_status_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "llm-status.md"
            exit_code = main(["llm-status", "--format", "markdown", "--out", str(out)])
            text = out.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("# Dogma LLM Provider Status", text)
        self.assertIn("Provider", text)


if __name__ == "__main__":
    unittest.main()
