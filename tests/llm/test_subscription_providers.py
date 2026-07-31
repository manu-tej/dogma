"""Run Dogma on a subscription you already pay for, not a metered API key.

Both providers shell out to a locally logged-in coding-agent CLI — `claude -p`
and `codex exec`. That makes them cheap to use and easy to get subtly wrong, so
the properties below are the ones that would fail silently:

  - A stray API key in the environment silently reroutes the CLI to metered
    billing. The whole point of choosing these providers is that they do not
    bill per token, and nothing would surface the switch except an invoice.
  - `codex` is an *agent*, not a completion endpoint. Unpinned, a prompt could
    make it edit files or leave sessions behind.
  - `codex exec` can exit 0 having written no final message. Returning "" for
    that would look to every caller downstream like a valid empty completion.

The tests use a fake executable rather than the real CLIs: these must run in CI,
offline, with nobody logged in. `tests/integration/` is where a real-CLI check
belongs.
"""

from __future__ import annotations

import os
import stat
import textwrap

import pytest

from quration.llm.providers import (
    ClaudeSubscriptionProvider,
    CodexSubscriptionProvider,
    LLMProviderUnavailableError,
    get_llm_provider,
)

MESSAGES = [{"role": "user", "content": "hello"}]


def fake_cli(tmp_path, name, body):
    """A stand-in executable that records its argv and environment."""
    script = tmp_path / name
    script.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(body))
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


#: Writes argv + the presence of OPENAI_API_KEY to a sidecar file, then writes
#: the final message to whatever path followed `-o`, mimicking `codex exec`.
CODEX_RECORDER = """
    import json, os, sys
    argv = sys.argv[1:]
    record = {
        "argv": argv,
        "cwd": os.getcwd(),
        "openai_key_present": "OPENAI_API_KEY" in os.environ,
        "stdin": sys.stdin.read(),
    }
    with open(os.environ["RECORD_TO"], "w") as fh:
        json.dump(record, fh)
    out = argv[argv.index("-o") + 1]
    with open(out, "w") as fh:
        fh.write(os.environ.get("FAKE_REPLY", "fake completion"))
    """


@pytest.fixture
def codex(tmp_path, monkeypatch):
    record_to = tmp_path / "record.json"
    monkeypatch.setenv("RECORD_TO", str(record_to))
    script = fake_cli(tmp_path, "codex", CODEX_RECORDER)
    provider = CodexSubscriptionProvider(codex_executable=str(script))
    return provider, record_to


def read_record(path):
    import json

    return json.loads(path.read_text())


class TestSubscriptionAuthIsNotSilentlyBypassed:
    """The failure this guards has no symptom except a bill."""

    def test_codex_removes_a_stray_openai_key(self, codex, monkeypatch):
        provider, record_to = codex
        monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-reach-the-cli")
        provider.create_message(messages=MESSAGES, model="")
        assert read_record(record_to)["openai_key_present"] is False

    def test_codex_can_be_told_not_to(self, codex, monkeypatch):
        """Opting out must be possible, but explicit."""
        provider, record_to = codex
        provider.force_subscription = False
        monkeypatch.setenv("OPENAI_API_KEY", "sk-deliberate")
        provider.create_message(messages=MESSAGES, model="")
        assert read_record(record_to)["openai_key_present"] is True

    def test_claude_defaults_to_forcing_subscription(self):
        assert ClaudeSubscriptionProvider().force_subscription is True

    def test_codex_defaults_to_forcing_subscription(self):
        assert CodexSubscriptionProvider().force_subscription is True


class TestCodexIsPinnedToACompletion:
    """`codex exec` is an agent. These flags are what stop it acting like one."""

    def test_the_sandbox_is_read_only(self, codex):
        provider, record_to = codex
        provider.create_message(messages=MESSAGES, model="")
        argv = read_record(record_to)["argv"]
        assert argv[argv.index("-s") + 1] == "read-only"

    def test_it_leaves_no_session_behind(self, codex):
        provider, record_to = codex
        provider.create_message(messages=MESSAGES, model="")
        assert "--ephemeral" in read_record(record_to)["argv"]

    def test_it_runs_outside_the_host_project(self, codex, tmp_path):
        """Otherwise the CLI loads the caller's AGENTS.md into every completion,
        which would silently change what the model is answering."""
        provider, record_to = codex
        provider.create_message(messages=MESSAGES, model="")
        record = read_record(record_to)
        assert os.path.realpath(record["cwd"]) != os.path.realpath(os.getcwd())

    def test_the_system_prompt_reaches_the_model(self, codex):
        """There is no --system-prompt on this CLI, so it has to be folded into
        the prompt. If that fold is dropped the model silently loses its
        instructions and nothing errors."""
        provider, record_to = codex
        provider.create_message(
            messages=MESSAGES, model="", system="ANSWER-IN-LATIN"
        )
        assert "ANSWER-IN-LATIN" in read_record(record_to)["stdin"]


class TestFailuresAreLoud:
    def test_an_empty_final_message_raises(self, codex, monkeypatch):
        """Exit 0 with nothing written. Returning "" would be indistinguishable
        from a legitimate empty completion everywhere downstream."""
        provider, _ = codex
        monkeypatch.setenv("FAKE_REPLY", "")
        with pytest.raises(RuntimeError, match="no final message"):
            provider.create_message(messages=MESSAGES, model="")

    def test_a_nonzero_exit_raises(self, tmp_path):
        script = fake_cli(
            tmp_path, "codex", "import sys; sys.stderr.write('not logged in'); sys.exit(2)"
        )
        provider = CodexSubscriptionProvider(codex_executable=str(script))
        with pytest.raises(RuntimeError, match="exited 2"):
            provider.create_message(messages=MESSAGES, model="")

    def test_a_missing_cli_says_how_to_fix_it(self):
        provider = CodexSubscriptionProvider(codex_executable="codex-not-installed")
        with pytest.raises(RuntimeError, match="codex login"):
            provider.create_message(messages=MESSAGES, model="")


class TestTheFactoryKnowsBothProviders:
    def test_codex_subscription_resolves(self):
        assert isinstance(
            get_llm_provider("codex_subscription"), CodexSubscriptionProvider
        )

    def test_claude_subscription_resolves(self):
        assert isinstance(
            get_llm_provider("claude_subscription"), ClaudeSubscriptionProvider
        )

    def test_an_unknown_provider_lists_the_real_ones(self):
        with pytest.raises(ValueError, match="codex_subscription"):
            get_llm_provider("wishful_thinking")


class TestTheRemedyNamesEveryOption:
    """The only way to discover `claude_subscription` existed was to read
    providers.py. An error naming one remedy out of four sends people to buy an
    API key they do not need."""

    @pytest.mark.parametrize(
        "option",
        ["claude_subscription", "codex_subscription", "ANTHROPIC_API_KEY", "demo"],
    )
    def test_the_option_is_named(self, option):
        assert option in LLMProviderUnavailableError.REMEDY

    def test_the_free_options_come_first(self):
        remedy = LLMProviderUnavailableError.REMEDY
        assert remedy.index("claude_subscription") < remedy.index("ANTHROPIC_API_KEY")
