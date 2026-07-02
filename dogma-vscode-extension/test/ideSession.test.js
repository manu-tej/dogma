"use strict";

const assert = require("assert");
const { buildIdeSessionReport, renderIdeSession } = require("../src/ideSession");

const ready = buildIdeSessionReport({
  preparedAt: "2026-06-19T23:45:00.000Z",
  service: {
    ready: true,
    status: "ok",
    url: "http://127.0.0.1:8765",
    already_reachable: true
  },
  scan: {
    completed: true,
    source: "local service",
    issues: []
  },
  readiness: {
    status: "ready",
    gates: [
      { id: "local_service", label: "Local service", state: "ready", detail: "ok" },
      { id: "quration", label: "quration bridge", state: "ready", detail: "ready; import ready: yes" }
    ]
  }
});

assert.strictEqual(ready.contract_version, "dogma-ide-session.v1");
assert.strictEqual(ready.status, "ready");
assert.strictEqual(ready.architecture.ide_surface, "VS Code/Cursor extension");
assert.strictEqual(ready.architecture.graph_surface, "quration web UI");
assert.strictEqual(ready.scan.issue_counts.total, 0);
assert(ready.next_actions.some((action) => action.includes("quration as the graph web UI")));

const blocked = buildIdeSessionReport({
  service: {
    ready: true,
    status: "ok",
    url: "http://127.0.0.1:8765",
    started_by_extension: true
  },
  scan: {
    completed: true,
    source: "local service",
    issues: [
      { severity: "error", message: "Duplicate sample_id" },
      { severity: "warning", message: "Missing annotation release" }
    ]
  },
  readiness: {
    status: "blocked",
    gates: [
      { id: "workspace_trust", label: "Workspace trust", state: "blocked", detail: "untrusted; human data detected" }
    ]
  }
});

assert.strictEqual(blocked.status, "blocked");
assert.strictEqual(blocked.scan.issue_counts.errors, 1);
assert.strictEqual(blocked.scan.issue_counts.warnings, 1);
assert(blocked.next_actions.some((action) => action.includes("error-level Dogma scan findings")));
assert(blocked.next_actions.some((action) => action.includes("ide-readiness.md")));

const markdown = renderIdeSession(blocked);
assert(markdown.includes("# Dogma IDE Session"));
assert(markdown.includes("quration remains the graph-native web UI"));
assert(markdown.includes("- IDE surface: VS Code/Cursor extension"));
assert(markdown.includes("- Graph surface: quration web UI"));
assert(markdown.includes("| Workspace trust | blocked | untrusted; human data detected |"));
assert(markdown.includes("1 errors, 1 warnings"));

console.log("IDE session renderer tests passed");
