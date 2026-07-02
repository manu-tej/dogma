"use strict";

const assert = require("assert");
const { buildIdeReadinessReport, renderIdeReadiness } = require("../src/ideReadiness");

const ready = buildIdeReadinessReport({
  checkedAt: "2026-06-19T23:30:00.000Z",
  settings: {
    service_url: "http://127.0.0.1:8765",
    quration_canvas_url: "http://localhost:3000/canvas",
    quration_api_url: "http://localhost:8000",
    agent_provider: "claude_subscription"
  },
  localService: { ok: true, result: { status: "ok", url: "http://127.0.0.1:8765" } },
  trust: { ok: true, result: { trust: { status: "trusted", trusted: true, human_data: true } } },
  llmProvider: { ok: true, result: { status: "ready", provider: "claude_subscription" } },
  methodsGraph: { ok: true, result: { status: "evaluable", substrate_status: "ready" } },
  quration: { ok: true, result: { status: "ready", import_ready: true, graph_api: { ready: true } } }
});

assert.strictEqual(ready.contract_version, "dogma-ide-readiness.v1");
assert.strictEqual(ready.status, "ready");
assert(ready.gates.every((gate) => gate.state === "ready"));
assert(ready.gates.some((gate) => gate.id === "quration" && gate.detail.includes("graph API ready: yes")));

const blocked = buildIdeReadinessReport({
  localService: { ok: false, error: "connect ECONNREFUSED" },
  trust: { ok: true, result: { trust: { status: "untrusted", trusted: false, human_data: true } } },
  llmProvider: { ok: true, result: { status: "needs_claude_login_or_cli", provider: "claude_subscription" } },
  methodsGraph: { ok: true, result: { status: "configuration_gap", substrate_status: "configuration_gap" } },
  quration: { ok: true, result: { status: "degraded", import_ready: false, graph_api: { ready: false } } }
});

assert.strictEqual(blocked.status, "blocked");
assert(blocked.next_actions.some((action) => action.includes("Start the Dogma local service")));
assert(blocked.next_actions.some((action) => action.includes("trust the workspace")));

const markdown = renderIdeReadiness(blocked);
assert(markdown.includes("# Dogma IDE Readiness"));
assert(markdown.includes("| Local service | blocked | connect ECONNREFUSED |"));
assert(markdown.includes("| Workspace trust | blocked | untrusted; human data detected |"));
assert(markdown.includes("quration backend/frontend"));

console.log("IDE readiness renderer tests passed");
