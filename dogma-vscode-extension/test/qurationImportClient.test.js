"use strict";

const assert = require("assert");
const {
  DEFAULT_QURATION_API_URL,
  REQUIRED_GRAPH_API_CAPABILITIES,
  buildQurationGraphUrl,
  checkQurationGraphApi,
  checkQurationConnection,
  getQurationEdgePlan,
  getQurationFailedEvents,
  getQurationGraphEvents,
  getQurationGraphContext,
  handoffToSeedSkeleton,
  importQurationHandoff,
  joinApiEndpoint,
  listQurationGraphs,
  resolveQurationEdgeReadout
} = require("../src/qurationImportClient");

const handoff = {
  causal_graph: {
    query: "Does control vs treatment change transcript abundance?",
    nodes: [
      { id: "contrast:declared", label: "control vs treatment", type: "other" },
      { id: "readout:primary", label: "Transcript abundance", type: "phenotype", position: { x: 12, y: "34" } },
      { id: "bad:type", label: "Unknown typed node", type: "not_a_quration_type" }
    ],
    edges: [
      {
        id: "bioedge.condition_transcript_abundance",
        source_id: "contrast:declared",
        target_id: "readout:primary",
        relation: "changes",
        state: "untested",
        confidence: 0,
        proposed_test: {
          expected: "Does control vs treatment change transcript abundance?"
        }
      },
      {
        id: "dangling",
        source_id: "missing",
        target_id: "readout:primary",
        relation: "changes"
      }
    ]
  },
  dogma: {
    coverage_gaps: ["methods_graph.audited_substrate_missing", "reference.annotation_missing"]
  }
};

assert.strictEqual(DEFAULT_QURATION_API_URL, "http://localhost:8000");
assert(REQUIRED_GRAPH_API_CAPABILITIES.some((capability) => capability.id === "apply_edit"));
assert.strictEqual(joinApiEndpoint("http://localhost:8000", "/hypothesis/build"), "http://localhost:8000/hypothesis/build");
assert.strictEqual(joinApiEndpoint("http://localhost:8000/api/", "/hypothesis/build"), "http://localhost:8000/api/hypothesis/build");
assert.strictEqual(
  buildQurationGraphUrl("http://localhost:3000/canvas?q=old", "graph-123"),
  "http://localhost:3000/canvas/graph-123"
);

const skeleton = handoffToSeedSkeleton(handoff);
assert.strictEqual(skeleton.nodes.length, 3);
assert.strictEqual(skeleton.nodes[1].position.x, 12);
assert.strictEqual(skeleton.nodes[1].position.y, 34);
assert.strictEqual(skeleton.nodes[2].type, "other");
assert.strictEqual(skeleton.edges.length, 1);
assert.strictEqual(skeleton.edges[0].id, "bioedge.condition_transcript_abundance");
assert.strictEqual(skeleton.edges[0].proposed_test.expected, "Does control vs treatment change transcript abundance?");
assert(skeleton.rationale.includes("Imported from Dogma workspace handoff"));
assert(skeleton.rationale.includes("methods_graph.audited_substrate_missing"));

let captured;
importQurationHandoff({
  qurationApiUrl: "http://localhost:8000",
  qurationCanvasUrl: "http://localhost:3000/canvas",
  handoff,
  timeoutMs: 7000,
  requestJson: async (url, options) => {
    captured = { url, options };
    return { kind: "investigative", graph_id: "qgraph-456" };
  }
}).then(async (result) => {
  assert.strictEqual(captured.url, "http://localhost:8000/hypothesis/build");
  assert.strictEqual(captured.options.method, "POST");
  assert.strictEqual(captured.options.timeoutMs, 7000);
  assert.strictEqual(captured.options.body.query, "Does control vs treatment change transcript abundance?");
  assert.strictEqual(captured.options.body.skeleton.edges.length, 1);
  assert.strictEqual(result.graph_url, "http://localhost:3000/canvas/qgraph-456");
  assert.strictEqual(result.import_request.skeleton.nodes.length, 3);

  const history = await listQurationGraphs({
    qurationApiUrl: "http://localhost:8000",
    qurationCanvasUrl: "http://localhost:3000/canvas",
    timeoutMs: 6000,
    fetchedAt: "2026-06-19T23:40:00.000Z",
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://localhost:8000/hypothesis");
      assert.strictEqual(options.method, "GET");
      assert.strictEqual(options.timeoutMs, 6000);
      return [
        {
          id: "graph-1",
          query: "Does A alter B?",
          status: "active",
          created_at: "2026-06-19T20:00:00Z",
          updated_at: "2026-06-19T21:00:00Z",
          n_nodes: 2,
          n_edges: 1
        }
      ];
    }
  });
  assert.strictEqual(history.contract_version, "dogma-quration-graphs.v1");
  assert.strictEqual(history.count, 1);
  assert.strictEqual(history.graphs[0].rank, 1);
  assert.strictEqual(history.graphs[0].graph_url, "http://localhost:3000/canvas/graph-1");

  const graphContext = await getQurationGraphContext({
    qurationApiUrl: "http://localhost:8000",
    qurationCanvasUrl: "http://localhost:3000/canvas",
    graphId: "graph-1",
    timeoutMs: 6000,
    fetchedAt: "2026-06-19T23:42:00.000Z",
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://localhost:8000/hypothesis/graph-1");
      assert.strictEqual(options.method, "GET");
      assert.strictEqual(options.timeoutMs, 6000);
      return {
        id: "graph-1",
        query: "Does A alter B?",
        nodes: [
          { id: "a", label: "A", type: "target" },
          { id: "b", label: "B", type: "phenotype" }
        ],
        edges: [
          {
            id: "edge-1",
            source_id: "a",
            target_id: "b",
            relation: "changes",
            state: "untested",
            display_status: "unvalidated",
            proposal_source: "llm",
            proposed_test: { expected: "Measure B after A perturbation" }
          }
        ]
      };
    }
  });
  assert.strictEqual(graphContext.contract_version, "dogma-quration-graph.v1");
  assert.strictEqual(graphContext.graph_url, "http://localhost:3000/canvas/graph-1");
  assert.strictEqual(graphContext.summary.nodes, 2);
  assert.strictEqual(graphContext.summary.edges, 1);
  assert.strictEqual(graphContext.summary.node_types.target, 1);
  assert.strictEqual(graphContext.summary.validation_statuses.unvalidated, 1);
  assert.strictEqual(graphContext.edge_dossiers[0].source_label, "A");
  assert.strictEqual(graphContext.edge_dossiers[0].target_label, "B");

  const edgePlan = await getQurationEdgePlan({
    qurationApiUrl: "http://localhost:8000",
    qurationCanvasUrl: "http://localhost:3000/canvas",
    graphId: "graph-1",
    edgeId: "edge-1",
    query: "Does A alter B?",
    timeoutMs: 6000,
    fetchedAt: "2026-06-19T23:43:00.000Z",
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://localhost:8000/hypothesis/graph-1/edges/edge-1/plan");
      assert.strictEqual(options.method, "GET");
      assert.strictEqual(options.timeoutMs, 6000);
      return {
        edge_id: "edge-1",
        claim: { source_symbol: "A", relation: "changes", target_symbol: "B" },
        ideal_readout: { claimed_entity: "B", modality: "transcript", ideal_assay_class: "RNA-seq" },
        resolved_readout: null,
        directness: null,
        proxy_rationale: "",
        dataset: null,
        alternatives: [],
        method: null,
        assumptions: [],
        expected_direction: "unknown",
        not_evaluable: false,
        resolver_provenance: {}
      };
    }
  });
  assert.strictEqual(edgePlan.contract_version, "dogma-quration-edge-plan.v1");
  assert.strictEqual(edgePlan.graph_url, "http://localhost:3000/canvas/graph-1");
  assert.strictEqual(edgePlan.edge_id, "edge-1");
  assert.strictEqual(edgePlan.query, "Does A alter B?");
  assert.strictEqual(edgePlan.plan.claim.target_symbol, "B");

  const edgeResolve = await resolveQurationEdgeReadout({
    qurationApiUrl: "http://localhost:8000",
    qurationCanvasUrl: "http://localhost:3000/canvas",
    graphId: "graph-1",
    edgeId: "edge-1",
    query: "Does A alter B?",
    timeoutMs: 6000,
    resolvedAt: "2026-06-20T02:40:00.000Z",
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://localhost:8000/hypothesis/graph-1/edges/edge-1/resolve");
      assert.strictEqual(options.method, "POST");
      assert.strictEqual(options.timeoutMs, 6000);
      return {
        edge_id: "edge-1",
        claim: { source_symbol: "A", relation: "changes", target_symbol: "B" },
        ideal_readout: { claimed_entity: "B", modality: "transcript", ideal_assay_class: "RNA-seq" },
        resolved_readout: {
          measured_entity: "B",
          measured_modality: "transcript",
          assay: "bulk RNA-seq",
          source: "geo",
          accession: "GSE000000"
        },
        directness: "direct",
        proxy_rationale: "",
        dataset: { source: "geo", accession: "GSE000000", title: "A perturbation RNA-seq" },
        alternatives: [],
        method: null,
        assumptions: [],
        expected_direction: "unknown",
        not_evaluable: false,
        resolver_provenance: { resolver: "demo" }
      };
    }
  });
  assert.strictEqual(edgeResolve.contract_version, "dogma-quration-edge-resolve.v1");
  assert.strictEqual(edgeResolve.resolved_at, "2026-06-20T02:40:00.000Z");
  assert.strictEqual(edgeResolve.graph_url, "http://localhost:3000/canvas/graph-1");
  assert.strictEqual(edgeResolve.edge_id, "edge-1");
  assert.strictEqual(edgeResolve.endpoints.edge_resolve, "http://localhost:8000/hypothesis/graph-1/edges/edge-1/resolve");
  assert.strictEqual(edgeResolve.plan.resolved_readout.accession, "GSE000000");

  const graphEvents = await getQurationGraphEvents({
    qurationApiUrl: "http://localhost:8000",
    qurationCanvasUrl: "http://localhost:3000/canvas",
    graphId: "graph-1",
    query: "Does A alter B?",
    timeoutMs: 6000,
    fetchedAt: "2026-06-20T01:20:00.000Z",
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://localhost:8000/hypothesis/graph-1/events");
      assert.strictEqual(options.method, "GET");
      assert.strictEqual(options.timeoutMs, 6000);
      return [
        {
          ts: "2026-06-20T01:00:00Z",
          trace_id: "trace-1",
          graph_id: "graph-1",
          query: "Does A alter B?",
          op: "edge_plan",
          status: "ok",
          latency_ms: "12",
          detail: { edge_id: "edge-1" },
          raw_input: null,
          raw_output: "{}",
          error: null
        },
        {
          ts: "2026-06-20T01:01:00Z",
          graph_id: "graph-1",
          op: "resolve_readout",
          status: "error",
          latency_ms: null,
          detail: null,
          error: "dataset search failed"
        }
      ];
    }
  });
  assert.strictEqual(graphEvents.contract_version, "dogma-quration-events.v1");
  assert.strictEqual(graphEvents.graph_url, "http://localhost:3000/canvas/graph-1");
  assert.strictEqual(graphEvents.count, 2);
  assert.strictEqual(graphEvents.summary.failed, 1);
  assert.strictEqual(graphEvents.summary.with_raw_io, 1);
  assert.strictEqual(graphEvents.summary.operations.edge_plan, 1);
  assert.strictEqual(graphEvents.events[0].rank, 1);
  assert.strictEqual(graphEvents.events[0].latency_ms, 12);
  assert.strictEqual(graphEvents.events[1].latency_ms, null);

  const failedEvents = await getQurationFailedEvents({
    qurationApiUrl: "http://localhost:8000",
    qurationCanvasUrl: "http://localhost:3000/canvas",
    timeoutMs: 6000,
    limit: 999,
    fetchedAt: "2026-06-20T01:21:00.000Z",
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://localhost:8000/hypothesis/events/failed?limit=500");
      assert.strictEqual(options.method, "GET");
      assert.strictEqual(options.timeoutMs, 6000);
      return [
        {
          ts: "2026-06-20T01:02:00Z",
          trace_id: null,
          graph_id: null,
          query: "bad seed",
          op: "seed",
          status: "error",
          latency_ms: 45,
          detail: { stage: "seed" },
          raw_input: "bad seed",
          raw_output: null,
          error: "seed failed"
        }
      ];
    }
  });
  assert.strictEqual(failedEvents.contract_version, "dogma-quration-failed-events.v1");
  assert.strictEqual(failedEvents.limit, 500);
  assert.strictEqual(failedEvents.count, 1);
  assert.strictEqual(failedEvents.summary.failed, 1);
  assert.strictEqual(failedEvents.events[0].op, "seed");
  assert.strictEqual(failedEvents.endpoints.failed_events, "http://localhost:8000/hypothesis/events/failed?limit=500");

  const graphApi = await checkQurationGraphApi({
    qurationApiUrl: "http://localhost:8000",
    timeoutMs: 5000,
    requestJson: async (url, options) => {
      assert.strictEqual(url, "http://localhost:8000/openapi.json");
      assert.strictEqual(options.method, "GET");
      return {
        paths: Object.fromEntries(REQUIRED_GRAPH_API_CAPABILITIES.map((capability) => [
          capability.path,
          { [capability.method]: {} }
        ]))
      };
    }
  });
  assert.strictEqual(graphApi.status, "ready");
  assert.strictEqual(graphApi.ready, true);
  assert.strictEqual(graphApi.missing_required.length, 0);
  assert(graphApi.capabilities.some((capability) => capability.id === "edge_resolve" && capability.available));

  const graphGap = await checkQurationGraphApi({
    qurationApiUrl: "http://localhost:8000",
    requestJson: async () => ({
      paths: {
        "/hypothesis": { get: {} },
        "/hypothesis/build": { post: {} }
      }
    })
  });
  assert.strictEqual(graphGap.status, "contract_gap");
  assert.strictEqual(graphGap.ready, false);
  assert(graphGap.missing_required.some((item) => item.id === "apply_edit"));

  const status = await checkQurationConnection({
    qurationApiUrl: "http://localhost:8000",
    qurationCanvasUrl: "http://localhost:3000/canvas",
    timeoutMs: 5000,
    checkedAt: "2026-06-19T23:00:00.000Z",
    requestJson: async (url, options) => {
      assert.strictEqual(options.method, "GET");
      if (url === "http://localhost:8000/health") {
        return { healthy: true, status: "ok", message: "ready" };
      }
      assert.strictEqual(url, "http://localhost:8000/openapi.json");
      return {
        paths: Object.fromEntries(REQUIRED_GRAPH_API_CAPABILITIES.map((capability) => [
          capability.path,
          { [capability.method]: {} }
        ]))
      };
    },
    requestPage: async (url, options) => {
      assert.strictEqual(url, "http://localhost:3000/canvas");
      assert.strictEqual(options.method, "GET");
      return { reachable: true, status_code: 200, content_type: "text/html" };
    }
  });
  assert.strictEqual(status.contract_version, "dogma-quration-status.v1");
  assert.strictEqual(status.status, "ready");
  assert.strictEqual(status.import_ready, true);
  assert.strictEqual(status.backend.message, "ready");
  assert.strictEqual(status.canvas.status_code, 200);
  assert.strictEqual(status.graph_api.ready, true);

  const degraded = await checkQurationConnection({
    qurationApiUrl: "http://localhost:8000",
    qurationCanvasUrl: "http://localhost:3000/canvas",
    requestJson: async () => {
      throw new Error("connect ECONNREFUSED");
    },
    requestPage: async () => ({ reachable: true, status_code: 200, content_type: "text/html" })
  });
  assert.strictEqual(degraded.status, "degraded");
  assert.strictEqual(degraded.import_ready, false);
  assert.strictEqual(degraded.backend.reachable, false);
  console.log("quration import client tests passed");
}).catch((error) => {
  console.error(error);
  process.exit(1);
});
