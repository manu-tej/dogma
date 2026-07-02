"use strict";

const http = require("http");
const https = require("https");
const { DEFAULT_QURATION_CANVAS_URL, normalizeQurationCanvasUrl } = require("./qurationCanvasLink");

const DEFAULT_QURATION_API_URL = "http://localhost:8000";
const REQUIRED_GRAPH_API_CAPABILITIES = [
  { id: "history", label: "Graph history", path: "/hypothesis", method: "get", required: true },
  { id: "start", label: "Graph start", path: "/hypothesis/start", method: "post", required: true },
  { id: "build", label: "Seed graph build/import", path: "/hypothesis/build", method: "post", required: true },
  { id: "fetch", label: "Graph fetch", path: "/hypothesis/{graph_id}", method: "get", required: true },
  { id: "layout", label: "Layout persistence", path: "/hypothesis/{graph_id}/layout", method: "put", required: true },
  { id: "apply_edit", label: "GraphEdit mutation", path: "/hypothesis/{graph_id}/apply-edit", method: "post", required: true },
  { id: "edge_plan", label: "Edge evaluation plan", path: "/hypothesis/{graph_id}/edges/{edge_id}/plan", method: "get", required: true },
  { id: "edge_resolve", label: "Facts-only readout resolve", path: "/hypothesis/{graph_id}/edges/{edge_id}/resolve", method: "post", required: true },
  { id: "graph_events", label: "Graph event trail", path: "/hypothesis/{graph_id}/events", method: "get", required: true },
  { id: "failed_events", label: "Failed event trail", path: "/hypothesis/events/failed", method: "get", required: true },
  { id: "edge_chat", label: "Edge chat", path: "/hypothesis/{graph_id}/edges/{edge_id}/chat", method: "post", required: false },
  { id: "node_chat", label: "Node chat", path: "/hypothesis/{graph_id}/nodes/{node_id}/chat", method: "post", required: false },
  { id: "node_ground", label: "Node grounding", path: "/hypothesis/{graph_id}/nodes/{node_id}/ground", method: "post", required: false },
  { id: "find_data", label: "Edge data search", path: "/hypothesis/{graph_id}/edges/{edge_id}/find-data", method: "post", required: false },
  { id: "edge_known", label: "Edge knowledge lookup", path: "/hypothesis/{graph_id}/edges/{edge_id}/known", method: "post", required: false },
  { id: "approve", label: "Evidence approval loop", path: "/hypothesis/{graph_id}/approve", method: "post", required: false }
];
const ALLOWED_NODE_TYPES = new Set([
  "target",
  "pathway",
  "phenotype",
  "cell_type",
  "tissue",
  "disease",
  "compound",
  "other"
]);
const ALLOWED_EDGE_STATES = new Set(["untested", "examined", "contested", "supported", "refuted"]);

function joinApiEndpoint(baseUrl, endpoint) {
  const raw = String(baseUrl || DEFAULT_QURATION_API_URL).trim() || DEFAULT_QURATION_API_URL;
  const url = new URL(raw);
  const basePath = url.pathname.replace(/\/$/, "");
  url.pathname = `${basePath}${endpoint}`;
  return url.toString();
}

function requestQurationJson(url, options = {}) {
  const timeoutMs = options.timeoutMs || 5000;
  const method = options.method || (options.body ? "POST" : "GET");
  const body = options.body ? JSON.stringify(options.body) : undefined;
  const parsed = new URL(url);
  const transport = parsed.protocol === "https:" ? https : http;

  return new Promise((resolve, reject) => {
    const request = transport.request(
      parsed,
      {
        method,
        headers: {
          Accept: "application/json",
          ...(body ? { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) } : {})
        }
      },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          let payload = {};
          if (text.trim()) {
            try {
              payload = JSON.parse(text);
            } catch (error) {
              reject(new Error(`quration returned invalid JSON: ${error.message}`));
              return;
            }
          }

          if (response.statusCode < 200 || response.statusCode >= 300) {
            const detail = payload.detail || payload.message || payload.error || `HTTP ${response.statusCode}`;
            reject(new Error(`quration API request failed: ${typeof detail === "string" ? detail : JSON.stringify(detail)}`));
            return;
          }

          resolve(payload);
        });
      }
    );

    request.on("error", (error) => reject(error));
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error(`quration API timed out after ${timeoutMs} ms`));
    });
    if (body) request.write(body);
    request.end();
  });
}

function requestQurationPage(url, options = {}) {
  const timeoutMs = options.timeoutMs || 5000;
  const method = options.method || "GET";
  const parsed = new URL(url);
  const transport = parsed.protocol === "https:" ? https : http;

  return new Promise((resolve, reject) => {
    const request = transport.request(
      parsed,
      {
        method,
        headers: { Accept: "text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.5" }
      },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => {
          const body = Buffer.concat(chunks).toString("utf8");
          resolve({
            status_code: response.statusCode,
            reachable: response.statusCode >= 200 && response.statusCode < 400,
            content_type: response.headers["content-type"] || null,
            body_preview: body.slice(0, 200)
          });
        });
      }
    );

    request.on("error", (error) => reject(error));
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error(`quration canvas timed out after ${timeoutMs} ms`));
    });
    request.end();
  });
}

async function checkQurationBackend(options = {}) {
  const request = options.requestJson || requestQurationJson;
  const url = joinApiEndpoint(options.qurationApiUrl, "/health");
  try {
    const payload = await request(url, {
      method: "GET",
      timeoutMs: options.timeoutMs
    });
    return {
      url,
      reachable: true,
      healthy: payload.healthy ?? null,
      status: payload.status || "reachable",
      message: payload.message || null,
      payload
    };
  } catch (error) {
    return {
      url,
      reachable: false,
      healthy: false,
      status: "unreachable",
      message: error.message,
      payload: null
    };
  }
}

async function checkQurationCanvas(options = {}) {
  const request = options.requestPage || requestQurationPage;
  const url = normalizeQurationCanvasUrl(options.qurationCanvasUrl || DEFAULT_QURATION_CANVAS_URL).toString();
  try {
    const result = await request(url, {
      method: "GET",
      timeoutMs: options.timeoutMs
    });
    return {
      url,
      reachable: Boolean(result.reachable),
      status_code: result.status_code || null,
      content_type: result.content_type || null,
      message: result.reachable ? "reachable" : `HTTP ${result.status_code || "unknown"}`
    };
  } catch (error) {
    return {
      url,
      reachable: false,
      status_code: null,
      content_type: null,
      message: error.message
    };
  }
}

function openApiHasOperation(paths, capability) {
  const operations = paths?.[capability.path];
  return Boolean(operations && operations[capability.method]);
}

function graphApiCapabilities(openapi = {}) {
  const paths = openapi.paths || {};
  return REQUIRED_GRAPH_API_CAPABILITIES.map((capability) => ({
    ...capability,
    available: openApiHasOperation(paths, capability)
  }));
}

async function checkQurationGraphApi(options = {}) {
  const request = options.requestJson || requestQurationJson;
  const url = joinApiEndpoint(options.qurationApiUrl, "/openapi.json");
  try {
    const openapi = await request(url, {
      method: "GET",
      timeoutMs: options.timeoutMs
    });
    const capabilities = graphApiCapabilities(openapi);
    const missingRequired = capabilities.filter((item) => item.required && !item.available);
    return {
      url,
      reachable: true,
      ready: missingRequired.length === 0,
      status: missingRequired.length ? "contract_gap" : "ready",
      message: missingRequired.length
        ? `missing ${missingRequired.length} required quration graph API endpoint(s)`
        : "required quration graph API endpoints are available",
      capabilities,
      missing_required: missingRequired.map((item) => ({
        id: item.id,
        label: item.label,
        path: item.path,
        method: item.method
      }))
    };
  } catch (error) {
    return {
      url,
      reachable: false,
      ready: false,
      status: "unreachable",
      message: error.message,
      capabilities: REQUIRED_GRAPH_API_CAPABILITIES.map((capability) => ({
        ...capability,
        available: false
      })),
      missing_required: REQUIRED_GRAPH_API_CAPABILITIES
        .filter((item) => item.required)
        .map((item) => ({
          id: item.id,
          label: item.label,
          path: item.path,
          method: item.method
        }))
    };
  }
}

async function checkQurationConnection(options = {}) {
  const checkedAt = options.checkedAt || new Date().toISOString();
  const [backend, canvas, graphApi] = await Promise.all([
    checkQurationBackend(options),
    checkQurationCanvas(options),
    checkQurationGraphApi(options)
  ]);
  const importReady = backend.reachable && canvas.reachable && graphApi.ready;
  return {
    contract_version: "dogma-quration-status.v1",
    checked_at: checkedAt,
    status: importReady ? "ready" : "degraded",
    import_ready: importReady,
    backend,
    canvas,
    graph_api: graphApi,
    settings: {
      quration_api_url: options.qurationApiUrl || DEFAULT_QURATION_API_URL,
      quration_canvas_url: options.qurationCanvasUrl || DEFAULT_QURATION_CANVAS_URL,
      timeout_ms: options.timeoutMs || 5000,
      graph_contract: "quration-hypothesis-api.v1"
    }
  };
}

function finiteNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function normalizePosition(position) {
  const x = finiteNumber(position?.x);
  const y = finiteNumber(position?.y);
  return x === null || y === null ? null : { x, y };
}

function normalizeNodeType(type) {
  const value = String(type || "other").trim();
  return ALLOWED_NODE_TYPES.has(value) ? value : "other";
}

function normalizeNode(node, index) {
  const id = String(node?.id || `dogma-node-${index + 1}`).trim();
  return {
    id,
    type: normalizeNodeType(node?.type),
    label: String(node?.label || id).trim() || id,
    grounding: node?.grounding || null,
    position: normalizePosition(node?.position)
  };
}

function normalizeProposedTest(proposedTest) {
  if (!proposedTest || typeof proposedTest !== "object") return null;
  const result = {
    pipeline: proposedTest.pipeline || null,
    data_accession: proposedTest.data_accession || null,
    expected: proposedTest.expected || null
  };
  return result.pipeline || result.data_accession || result.expected ? result : null;
}

function normalizeEdge(edge, nodeIds, index) {
  const sourceId = String(edge?.source_id || "").trim();
  const targetId = String(edge?.target_id || "").trim();
  if (!nodeIds.has(sourceId) || !nodeIds.has(targetId)) return null;

  const id = String(edge?.id || `dogma-edge-${index + 1}`).trim();
  const state = String(edge?.state || "untested").trim();
  const confidence = Number(edge?.confidence || 0);
  const proposedTest = normalizeProposedTest(edge?.proposed_test);
  return {
    id,
    source_id: sourceId,
    target_id: targetId,
    relation: String(edge?.relation || "relates to").trim() || "relates to",
    state: ALLOWED_EDGE_STATES.has(state) ? state : "untested",
    confidence: Number.isFinite(confidence) ? confidence : 0,
    suggested_by: Array.isArray(edge?.suggested_by) ? edge.suggested_by : [],
    pending: Boolean(edge?.pending),
    ...(proposedTest ? { proposed_test: proposedTest } : {})
  };
}

function handoffQuery(handoff = {}) {
  return String(handoff.causal_graph?.query || handoff.query || "Dogma workspace graph").trim() || "Dogma workspace graph";
}

function handoffRationale(handoff = {}) {
  const gaps = Array.isArray(handoff.dogma?.coverage_gaps) ? handoff.dogma.coverage_gaps : [];
  const gapText = gaps.length ? ` Coverage gaps: ${gaps.join(", ")}.` : "";
  return `Imported from Dogma workspace handoff as an unvalidated quration seed graph.${gapText}`;
}

function handoffToSeedSkeleton(handoff = {}) {
  const graph = handoff.causal_graph || {};
  const nodes = (Array.isArray(graph.nodes) ? graph.nodes : []).map(normalizeNode);
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = (Array.isArray(graph.edges) ? graph.edges : [])
    .map((edge, index) => normalizeEdge(edge, nodeIds, index))
    .filter(Boolean);

  if (!nodes.length) {
    throw new Error("Dogma quration handoff has no causal graph nodes to import.");
  }

  return {
    nodes,
    edges,
    rationale: handoffRationale(handoff)
  };
}

function buildQurationGraphUrl(canvasUrl, graphId) {
  const id = String(graphId || "").trim();
  if (!id) return null;
  const url = normalizeQurationCanvasUrl(canvasUrl || DEFAULT_QURATION_CANVAS_URL);
  const basePath = url.pathname.replace(/\/$/, "");
  url.pathname = `${basePath}/${encodeURIComponent(id)}`;
  url.search = "";
  return url.toString();
}

function normalizeGraphSummary(summary = {}, index = 0, canvasUrl) {
  const id = String(summary.id || summary.graph_id || "").trim();
  return {
    rank: index + 1,
    id: id || null,
    query: String(summary.query || "Untitled quration graph").trim() || "Untitled quration graph",
    status: String(summary.status || "unknown").trim() || "unknown",
    created_at: summary.created_at || null,
    updated_at: summary.updated_at || null,
    n_nodes: Number.isFinite(Number(summary.n_nodes)) ? Number(summary.n_nodes) : 0,
    n_edges: Number.isFinite(Number(summary.n_edges)) ? Number(summary.n_edges) : 0,
    graph_url: id ? buildQurationGraphUrl(canvasUrl, id) : null
  };
}

function countBy(items, field, fallback = "unknown") {
  return items.reduce((counts, item) => {
    const key = String(item?.[field] || fallback).trim() || fallback;
    counts[key] = (counts[key] || 0) + 1;
    return counts;
  }, {});
}

function nodeLabelById(nodes = []) {
  return Object.fromEntries(nodes.map((node) => [node.id, node.label || node.id]));
}

function summarizeEdge(edge = {}, labels = {}) {
  const source = labels[edge.source_id] || edge.source_id || "unknown";
  const target = labels[edge.target_id] || edge.target_id || "unknown";
  const proposedTest = edge.proposed_test || {};
  return {
    id: edge.id || null,
    source_id: edge.source_id || null,
    target_id: edge.target_id || null,
    source_label: source,
    target_label: target,
    relation: edge.relation || "relates to",
    state: edge.state || "unknown",
    validation_status: edge.display_status || edge.validation_status || "unknown",
    proposal_source: edge.proposal_source || null,
    pending: Boolean(edge.pending),
    proposed_test: {
      pipeline: proposedTest.pipeline || null,
      data_accession: proposedTest.data_accession || null,
      expected: proposedTest.expected || null
    }
  };
}

function normalizeEvent(event = {}, index = 0) {
  const latency = event.latency_ms === null || event.latency_ms === undefined ? NaN : Number(event.latency_ms);
  return {
    rank: index + 1,
    ts: event.ts || null,
    trace_id: event.trace_id || null,
    graph_id: event.graph_id || null,
    query: event.query || null,
    op: String(event.op || "unknown").trim() || "unknown",
    status: String(event.status || "unknown").trim() || "unknown",
    latency_ms: Number.isFinite(latency) ? latency : null,
    detail: event.detail && typeof event.detail === "object" ? event.detail : null,
    raw_input: event.raw_input || null,
    raw_output: event.raw_output || null,
    error: event.error || null
  };
}

function summarizeEvents(events = []) {
  return {
    total: events.length,
    statuses: countBy(events, "status"),
    operations: countBy(events, "op"),
    failed: events.filter((event) => event.status === "error" || event.error).length,
    with_raw_io: events.filter((event) => event.raw_input || event.raw_output).length
  };
}

async function listQurationGraphs(options = {}) {
  const request = options.requestJson || requestQurationJson;
  const endpoint = joinApiEndpoint(options.qurationApiUrl, "/hypothesis");
  const payload = await request(endpoint, {
    method: "GET",
    timeoutMs: options.timeoutMs
  });
  if (!Array.isArray(payload)) {
    throw new Error("quration graph history response was not a list.");
  }
  const graphs = payload.map((summary, index) => normalizeGraphSummary(summary, index, options.qurationCanvasUrl));
  return {
    contract_version: "dogma-quration-graphs.v1",
    fetched_at: options.fetchedAt || new Date().toISOString(),
    status: "ready",
    count: graphs.length,
    graphs,
    settings: {
      quration_api_url: options.qurationApiUrl || DEFAULT_QURATION_API_URL,
      quration_canvas_url: options.qurationCanvasUrl || DEFAULT_QURATION_CANVAS_URL,
      timeout_ms: options.timeoutMs || 5000,
      graph_contract: "quration-hypothesis-api.v1"
    },
    endpoints: {
      history: endpoint
    }
  };
}

async function getQurationGraphEvents(options = {}) {
  const graphId = String(options.graphId || "").trim();
  if (!graphId) {
    throw new Error("quration graph id is required.");
  }

  const request = options.requestJson || requestQurationJson;
  const endpoint = joinApiEndpoint(options.qurationApiUrl, `/hypothesis/${encodeURIComponent(graphId)}/events`);
  const payload = await request(endpoint, {
    method: "GET",
    timeoutMs: options.timeoutMs
  });
  if (!Array.isArray(payload)) {
    throw new Error("quration graph events response was not a list.");
  }
  const events = payload.map(normalizeEvent);
  return {
    contract_version: "dogma-quration-events.v1",
    fetched_at: options.fetchedAt || new Date().toISOString(),
    status: "ready",
    scope: "graph",
    graph_id: graphId,
    graph_url: buildQurationGraphUrl(options.qurationCanvasUrl, graphId),
    query: options.query || null,
    count: events.length,
    summary: summarizeEvents(events),
    events,
    settings: {
      quration_api_url: options.qurationApiUrl || DEFAULT_QURATION_API_URL,
      quration_canvas_url: options.qurationCanvasUrl || DEFAULT_QURATION_CANVAS_URL,
      timeout_ms: options.timeoutMs || 5000,
      graph_contract: "quration-hypothesis-api.v1"
    },
    endpoints: {
      graph_events: endpoint
    }
  };
}

async function getQurationFailedEvents(options = {}) {
  const request = options.requestJson || requestQurationJson;
  const requestedLimit = Number(options.limit || 100);
  const limit = Math.max(1, Math.min(500, Number.isFinite(requestedLimit) ? requestedLimit : 100));
  const endpointUrl = new URL(joinApiEndpoint(options.qurationApiUrl, "/hypothesis/events/failed"));
  endpointUrl.searchParams.set("limit", String(limit));
  const endpoint = endpointUrl.toString();
  const payload = await request(endpoint, {
    method: "GET",
    timeoutMs: options.timeoutMs
  });
  if (!Array.isArray(payload)) {
    throw new Error("quration failed events response was not a list.");
  }
  const events = payload.map(normalizeEvent);
  return {
    contract_version: "dogma-quration-failed-events.v1",
    fetched_at: options.fetchedAt || new Date().toISOString(),
    status: "ready",
    scope: "failed",
    limit,
    count: events.length,
    summary: summarizeEvents(events),
    events,
    settings: {
      quration_api_url: options.qurationApiUrl || DEFAULT_QURATION_API_URL,
      quration_canvas_url: options.qurationCanvasUrl || DEFAULT_QURATION_CANVAS_URL,
      timeout_ms: options.timeoutMs || 5000,
      graph_contract: "quration-hypothesis-api.v1"
    },
    endpoints: {
      failed_events: endpoint
    }
  };
}

async function getQurationGraphContext(options = {}) {
  const graphId = String(options.graphId || "").trim();
  if (!graphId) {
    throw new Error("quration graph id is required.");
  }

  const request = options.requestJson || requestQurationJson;
  const endpoint = joinApiEndpoint(options.qurationApiUrl, `/hypothesis/${encodeURIComponent(graphId)}`);
  const graph = await request(endpoint, {
    method: "GET",
    timeoutMs: options.timeoutMs
  });
  const nodes = Array.isArray(graph.nodes) ? graph.nodes : [];
  const edges = Array.isArray(graph.edges) ? graph.edges : [];
  const labels = nodeLabelById(nodes);
  const edgeDossiers = edges.map((edge) => summarizeEdge(edge, labels));
  return {
    contract_version: "dogma-quration-graph.v1",
    fetched_at: options.fetchedAt || new Date().toISOString(),
    status: "ready",
    graph_id: graph.id || graphId,
    graph_url: buildQurationGraphUrl(options.qurationCanvasUrl, graph.id || graphId),
    query: graph.query || "Untitled quration graph",
    summary: {
      nodes: nodes.length,
      edges: edges.length,
      node_types: countBy(nodes, "type"),
      edge_states: countBy(edges, "state"),
      validation_statuses: countBy(edgeDossiers, "validation_status"),
      pending_edges: edgeDossiers.filter((edge) => edge.pending).length
    },
    graph,
    edge_dossiers: edgeDossiers,
    settings: {
      quration_api_url: options.qurationApiUrl || DEFAULT_QURATION_API_URL,
      quration_canvas_url: options.qurationCanvasUrl || DEFAULT_QURATION_CANVAS_URL,
      timeout_ms: options.timeoutMs || 5000,
      graph_contract: "quration-hypothesis-api.v1"
    },
    endpoints: {
      graph: endpoint
    }
  };
}

async function getQurationEdgePlan(options = {}) {
  const graphId = String(options.graphId || "").trim();
  const edgeId = String(options.edgeId || "").trim();
  if (!graphId) {
    throw new Error("quration graph id is required.");
  }
  if (!edgeId) {
    throw new Error("quration edge id is required.");
  }

  const request = options.requestJson || requestQurationJson;
  const endpoint = joinApiEndpoint(
    options.qurationApiUrl,
    `/hypothesis/${encodeURIComponent(graphId)}/edges/${encodeURIComponent(edgeId)}/plan`
  );
  const plan = await request(endpoint, {
    method: "GET",
    timeoutMs: options.timeoutMs
  });
  return {
    contract_version: "dogma-quration-edge-plan.v1",
    fetched_at: options.fetchedAt || new Date().toISOString(),
    status: "ready",
    graph_id: graphId,
    graph_url: buildQurationGraphUrl(options.qurationCanvasUrl, graphId),
    edge_id: edgeId,
    query: options.query || null,
    plan,
    settings: {
      quration_api_url: options.qurationApiUrl || DEFAULT_QURATION_API_URL,
      quration_canvas_url: options.qurationCanvasUrl || DEFAULT_QURATION_CANVAS_URL,
      timeout_ms: options.timeoutMs || 5000,
      graph_contract: "quration-hypothesis-api.v1"
    },
    endpoints: {
      edge_plan: endpoint
    }
  };
}

async function resolveQurationEdgeReadout(options = {}) {
  const graphId = String(options.graphId || "").trim();
  const edgeId = String(options.edgeId || "").trim();
  if (!graphId) {
    throw new Error("quration graph id is required.");
  }
  if (!edgeId) {
    throw new Error("quration edge id is required.");
  }

  const request = options.requestJson || requestQurationJson;
  const endpoint = joinApiEndpoint(
    options.qurationApiUrl,
    `/hypothesis/${encodeURIComponent(graphId)}/edges/${encodeURIComponent(edgeId)}/resolve`
  );
  const plan = await request(endpoint, {
    method: "POST",
    timeoutMs: options.timeoutMs
  });
  return {
    contract_version: "dogma-quration-edge-resolve.v1",
    resolved_at: options.resolvedAt || new Date().toISOString(),
    status: "ready",
    graph_id: graphId,
    graph_url: buildQurationGraphUrl(options.qurationCanvasUrl, graphId),
    edge_id: edgeId,
    query: options.query || null,
    plan,
    settings: {
      quration_api_url: options.qurationApiUrl || DEFAULT_QURATION_API_URL,
      quration_canvas_url: options.qurationCanvasUrl || DEFAULT_QURATION_CANVAS_URL,
      timeout_ms: options.timeoutMs || 5000,
      graph_contract: "quration-hypothesis-api.v1"
    },
    endpoints: {
      edge_resolve: endpoint
    }
  };
}

async function importQurationHandoff(options) {
  const request = options.requestJson || requestQurationJson;
  const query = String(options.query || handoffQuery(options.handoff)).trim();
  const skeleton = handoffToSeedSkeleton(options.handoff);
  const endpoint = joinApiEndpoint(options.qurationApiUrl, "/hypothesis/build");
  const result = await request(endpoint, {
    method: "POST",
    body: { query, skeleton },
    timeoutMs: options.timeoutMs
  });
  return {
    ...result,
    graph_url: buildQurationGraphUrl(options.qurationCanvasUrl, result.graph_id),
    import_request: { query, skeleton }
  };
}

module.exports = {
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
  requestQurationJson,
  requestQurationPage,
  resolveQurationEdgeReadout
};
