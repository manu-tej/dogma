"use strict";

const assert = require("assert");
const { renderQurationEvents } = require("../src/qurationEvents");

const graphEvents = {
  contract_version: "dogma-quration-events.v1",
  fetched_at: "2026-06-20T01:20:00.000Z",
  status: "ready",
  scope: "graph",
  graph_id: "graph-1",
  graph_url: "http://localhost:3000/canvas/graph-1",
  query: "Does A alter B?",
  count: 2,
  summary: {
    total: 2,
    failed: 1,
    with_raw_io: 1,
    statuses: { ok: 1, error: 1 },
    operations: { edge_plan: 1, resolve_readout: 1 }
  },
  events: [
    {
      rank: 1,
      ts: "2026-06-20T01:00:00Z",
      op: "edge_plan",
      status: "ok",
      latency_ms: 12,
      detail: { edge_id: "edge-1", modality: "transcript" },
      raw_input: null,
      raw_output: "{\"edge_id\":\"edge-1\"}",
      error: null
    },
    {
      rank: 2,
      ts: "2026-06-20T01:01:00Z",
      op: "resolve_readout",
      status: "error",
      latency_ms: 220,
      detail: { edge_id: "edge-1" },
      raw_input: null,
      raw_output: null,
      error: "dataset search failed"
    }
  ],
  settings: {
    quration_api_url: "http://localhost:8000",
    quration_canvas_url: "http://localhost:3000/canvas",
    graph_contract: "quration-hypothesis-api.v1"
  },
  endpoints: {
    graph_events: "http://localhost:8000/hypothesis/graph-1/events"
  }
};

const graphMarkdown = renderQurationEvents(graphEvents);
assert(graphMarkdown.includes("# Dogma quration Graph Events"));
assert(graphMarkdown.includes("quration remains the canonical graph"));
assert(graphMarkdown.includes("- Graph ID: graph-1"));
assert(graphMarkdown.includes("- Events: 2"));
assert(graphMarkdown.includes("- Failed: 1"));
assert(graphMarkdown.includes("edge_plan: 1"));
assert(graphMarkdown.includes("| 2026-06-20T01:00:00Z | edge_plan | ok | 12 | {\"edge_id\":\"edge-1\",\"modality\":\"transcript\"} | none |"));
assert(graphMarkdown.includes("| 2026-06-20T01:01:00Z | resolve_readout | error | 220 | {\"edge_id\":\"edge-1\"} | dataset search failed |"));
assert(graphMarkdown.includes("as biological support/refute evidence"));

const failedMarkdown = renderQurationEvents({
  contract_version: "dogma-quration-failed-events.v1",
  fetched_at: "2026-06-20T01:30:00.000Z",
  status: "ready",
  scope: "failed",
  limit: 25,
  count: 0,
  summary: {
    total: 0,
    failed: 0,
    with_raw_io: 0,
    statuses: {},
    operations: {}
  },
  events: [],
  settings: {
    quration_api_url: "http://localhost:8000",
    quration_canvas_url: "http://localhost:3000/canvas",
    graph_contract: "quration-hypothesis-api.v1"
  },
  endpoints: {
    failed_events: "http://localhost:8000/hypothesis/events/failed?limit=25"
  }
});

assert(failedMarkdown.includes("# Dogma quration Failed Events"));
assert(failedMarkdown.includes("- Limit: 25"));
assert(failedMarkdown.includes("| none | unknown | unknown | unknown | not available | none |"));
assert(failedMarkdown.includes("read-only and does not mutate quration"));

console.log("quration events renderer tests passed");
