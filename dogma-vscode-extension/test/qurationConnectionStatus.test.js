"use strict";

const assert = require("assert");
const { renderQurationConnectionStatus } = require("../src/qurationConnectionStatus");

const ready = renderQurationConnectionStatus({
  status: "ready",
  import_ready: true,
  checked_at: "2026-06-19T23:00:00.000Z",
  backend: {
    url: "http://localhost:8000/health",
    reachable: true,
    healthy: true,
    status: "ok",
    message: "ready"
  },
  canvas: {
    url: "http://localhost:3000/canvas",
    reachable: true,
    status_code: 200,
    content_type: "text/html",
    message: "reachable"
  },
  graph_api: {
    url: "http://localhost:8000/openapi.json",
    reachable: true,
    ready: true,
    status: "ready",
    message: "required quration graph API endpoints are available",
    capabilities: [
      { id: "build", label: "Seed graph build/import", path: "/hypothesis/build", method: "post", required: true, available: true },
      { id: "apply_edit", label: "GraphEdit mutation", path: "/hypothesis/{graph_id}/apply-edit", method: "post", required: true, available: true },
      { id: "edge_chat", label: "Edge chat", path: "/hypothesis/{graph_id}/edges/{edge_id}/chat", method: "post", required: false, available: true }
    ]
  },
  settings: {
    quration_api_url: "http://localhost:8000",
    quration_canvas_url: "http://localhost:3000/canvas",
    timeout_ms: 5000,
    graph_contract: "quration-hypothesis-api.v1"
  }
});

assert(ready.includes("# Dogma quration Status"));
assert(ready.includes("- Status: ready"));
assert(ready.includes("- Import ready: yes"));
assert(ready.includes("- URL: http://localhost:8000/health"));
assert(ready.includes("- URL: http://localhost:3000/canvas"));
assert(ready.includes("## Graph API Contract"));
assert(ready.includes("| GraphEdit mutation | POST /hypothesis/{graph_id}/apply-edit | yes |"));
assert(ready.includes("| Edge chat | POST /hypothesis/{graph_id}/edges/{edge_id}/chat | yes |"));
assert(ready.includes("Dogma: Import Workspace To quration"));

const degraded = renderQurationConnectionStatus({
  status: "degraded",
  import_ready: false,
  backend: {
    url: "http://localhost:8000/health",
    reachable: false,
    healthy: false,
    status: "unreachable",
    message: "connect ECONNREFUSED"
  },
  canvas: {
    url: "http://localhost:3000/canvas",
    reachable: false,
    status_code: null,
    content_type: null,
    message: "connect ECONNREFUSED"
  },
  graph_api: {
    url: "http://localhost:8000/openapi.json",
    reachable: true,
    ready: false,
    status: "contract_gap",
    message: "missing 1 required quration graph API endpoint(s)",
    capabilities: [
      { id: "build", label: "Seed graph build/import", path: "/hypothesis/build", method: "post", required: true, available: false }
    ]
  },
  settings: {
    quration_api_url: "http://localhost:8000",
    quration_canvas_url: "http://localhost:3000/canvas",
    timeout_ms: 5000,
    graph_contract: "quration-hypothesis-api.v1"
  }
});

assert(degraded.includes("- Status: degraded"));
assert(degraded.includes("Start quration's backend"));
assert(degraded.includes("Start quration's frontend"));
assert(degraded.includes("required `/hypothesis` graph contract"));

console.log("quration connection status renderer tests passed");
