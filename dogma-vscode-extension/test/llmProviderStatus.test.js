"use strict";

const assert = require("assert");
const { renderLlmProviderStatus } = require("../src/llmProviderStatus");

const direct = renderLlmProviderStatus({
  markdown: "# Dogma LLM Provider Status\n\n- Provider: claude_subscription"
});
assert(direct.endsWith("\n"));
assert(direct.includes("LLM Provider Status"));

const fallback = renderLlmProviderStatus({
  status: "needs_claude_login_or_cli",
  provider: "claude_subscription",
  claude_subscription: {
    cli_path: "claude",
    resolved_cli_path: null,
    attempted_cli_paths: ["/Users/test/.local/bin/claude", "/opt/homebrew/bin/claude"],
    tools_disabled: true,
    no_session_persistence: true
  }
});

assert(fallback.includes("claude_subscription"));
assert(fallback.includes("Attempted CLI paths: /Users/test/.local/bin/claude, /opt/homebrew/bin/claude"));
assert(fallback.includes("Tools disabled: true"));
assert(fallback.includes("No session persistence: true"));

console.log("LLM provider status renderer tests passed");
