"""Tests for the optional raw-LLM-capture hook in providers.py.

The capture hook lets an outer caller collect the exact prompt+response of
every ``create_message`` call made during a block via the module-level
``llm_capture_var`` contextvar, without changing any call site or return type.

Transports are patched (no real network/subprocess) so these tests are fast
and hermetic.
"""

import json
from unittest.mock import Mock, patch

import pytest

from quration.llm import providers
from quration.llm.providers import (
    AnthropicProvider,
    ClaudeSubscriptionProvider,
    OpenRouterProvider,
    llm_capture_var,
)


@pytest.fixture
def capture_buffer():
    """Activate a fresh capture buffer and reset the contextvar afterward."""
    buf: list = []
    token = llm_capture_var.set(buf)
    try:
        yield buf
    finally:
        llm_capture_var.reset(token)


# --------------------------------------------------------------------------
# ClaudeSubscriptionProvider (the provider used in real subscription mode)
# --------------------------------------------------------------------------


def _fake_cli_result(text: str = "hello"):
    """A fake subprocess.run return for the claude -p JSON output path."""
    fake = Mock()
    fake.returncode = 0
    fake.stdout = json.dumps(
        {"result": text, "usage": {"input_tokens": 3, "output_tokens": 1}, "is_error": False}
    )
    fake.stderr = ""
    return fake


def test_subscription_captures_when_active(capture_buffer):
    provider = ClaudeSubscriptionProvider(claude_executable="claude")

    with patch("subprocess.run", return_value=_fake_cli_result("hello")), patch(
        "shutil.which", return_value="/usr/bin/claude"
    ):
        out = provider.create_message(
            messages=[{"role": "user", "content": "hi there"}],
            model="claude-haiku-4",
            system="be terse",
        )

    assert out == "hello"
    assert len(capture_buffer) == 1
    rec = capture_buffer[0]
    assert rec["provider"] == "claude_subscription"
    assert rec["response"] == "hello"
    assert rec["model"] == "claude-haiku-4"
    assert rec["system"] == "be terse"
    assert "hi there" in rec["prompt"]


def test_subscription_noop_when_inactive():
    provider = ClaudeSubscriptionProvider(claude_executable="claude")

    with patch("subprocess.run", return_value=_fake_cli_result("hello")), patch(
        "shutil.which", return_value="/usr/bin/claude"
    ):
        out = provider.create_message(
            messages=[{"role": "user", "content": "hi"}],
            model="claude-haiku-4",
        )

    assert out == "hello"
    assert llm_capture_var.get() is None


# --------------------------------------------------------------------------
# AnthropicProvider
# --------------------------------------------------------------------------


def _fake_anthropic_message(text: str = "world"):
    msg = Mock()
    block = Mock()
    block.text = text
    msg.content = [block]
    usage = Mock()
    usage.input_tokens = 5
    usage.output_tokens = 2
    usage.cache_read_input_tokens = 0
    usage.cache_creation_input_tokens = 0
    msg.usage = usage
    return msg


def test_anthropic_captures_when_active(capture_buffer):
    with patch.object(AnthropicProvider, "__init__", lambda self, api_key=None: None):
        provider = AnthropicProvider()
        provider.client = Mock()
        provider.client.messages.create.return_value = _fake_anthropic_message("world")

        out = provider.create_message(
            messages=[{"role": "user", "content": "question"}],
            model="claude-sonnet-4",
            system="sys-prompt",
        )

    assert out == "world"
    assert len(capture_buffer) == 1
    rec = capture_buffer[0]
    assert rec["provider"] == "anthropic"
    assert rec["response"] == "world"
    assert rec["model"] == "claude-sonnet-4"
    assert rec["system"] == "sys-prompt"
    assert "question" in rec["prompt"]


def test_anthropic_noop_when_inactive():
    with patch.object(AnthropicProvider, "__init__", lambda self, api_key=None: None):
        provider = AnthropicProvider()
        provider.client = Mock()
        provider.client.messages.create.return_value = _fake_anthropic_message("world")

        out = provider.create_message(
            messages=[{"role": "user", "content": "question"}],
            model="claude-sonnet-4",
        )

    assert out == "world"
    assert llm_capture_var.get() is None


# --------------------------------------------------------------------------
# OpenRouterProvider
# --------------------------------------------------------------------------


def _fake_openrouter_response(text: str = "router-out"):
    resp = Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 4, "completion_tokens": 2},
    }
    return resp


def test_openrouter_captures_when_active(capture_buffer):
    with patch.object(
        OpenRouterProvider, "__init__", lambda self, **kw: None
    ):
        provider = OpenRouterProvider()
        provider.api_key = "x"
        provider.site_url = ""
        provider.app_name = "quration"

        with patch("requests.post", return_value=_fake_openrouter_response("router-out")):
            out = provider.create_message(
                messages=[{"role": "user", "content": "ask"}],
                model="claude-sonnet-4",
                system="router-sys",
            )

    assert out == "router-out"
    assert len(capture_buffer) == 1
    rec = capture_buffer[0]
    assert rec["provider"] == "openrouter"
    assert rec["response"] == "router-out"
    assert rec["model"] == "claude-sonnet-4"
    assert "router-sys" in rec["system"]
    assert "ask" in rec["prompt"]


def test_openrouter_noop_when_inactive():
    with patch.object(
        OpenRouterProvider, "__init__", lambda self, **kw: None
    ):
        provider = OpenRouterProvider()
        provider.api_key = "x"
        provider.site_url = ""
        provider.app_name = "quration"

        with patch("requests.post", return_value=_fake_openrouter_response("router-out")):
            out = provider.create_message(
                messages=[{"role": "user", "content": "ask"}],
                model="claude-sonnet-4",
            )

    assert out == "router-out"
    assert llm_capture_var.get() is None


def test_capture_var_default_is_none():
    """No capture active by default at module load."""
    assert providers.llm_capture_var.get() is None
