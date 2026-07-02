"use strict";

const { renderEdgeEvaluationPlan } = require("./edgeEvaluationPlan");

function cleanText(value, fallback = "") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function nodeLabelById(context = {}) {
  const labels = new Map();
  const nodes = Array.isArray(context.graph?.nodes) ? context.graph.nodes : [];
  nodes.forEach((node) => {
    const id = cleanText(node.id);
    if (id) labels.set(id, cleanText(node.label, id));
  });
  return labels;
}

function qurationEdges(context = {}) {
  if (Array.isArray(context.edge_dossiers) && context.edge_dossiers.length) {
    return context.edge_dossiers;
  }

  const labels = nodeLabelById(context);
  const edges = Array.isArray(context.graph?.edges) ? context.graph.edges : [];
  return edges.map((edge) => ({
    ...edge,
    source_label: labels.get(edge.source_id) || edge.source_id,
    target_label: labels.get(edge.target_id) || edge.target_id,
    validation_status: edge.validation_status || edge.display_status
  }));
}

function proposedTestText(edge = {}) {
  const proposed = edge.proposed_test || {};
  return cleanText(proposed.expected || proposed.pipeline || proposed.data_accession);
}

function qurationEdgeClaim(edge = {}) {
  const source = cleanText(edge.source_label || edge.source_id, "unknown source");
  const relation = cleanText(edge.relation, "relates to");
  const target = cleanText(edge.target_label || edge.target_id, "unknown target");
  return `${source} ${relation} ${target}`;
}

function coverageGapsForQurationEdge(edge = {}) {
  const gaps = [];
  if (cleanText(edge.state).toLowerCase() === "untested") {
    gaps.push("quration.edge.untested");
  }
  const validation = cleanText(edge.validation_status).toLowerCase();
  if (validation && validation !== "validated") {
    gaps.push(`quration.edge.${validation}`);
  }
  return gaps;
}

function pickQurationEdge(context = {}, edgeId) {
  const edges = qurationEdges(context);
  if (!edges.length) {
    throw new Error("No quration edges are available in .dogma/quration-graph.json.");
  }
  const wanted = cleanText(edgeId);
  if (!wanted) return edges[0];
  const match = edges.find((edge) => cleanText(edge.id) === wanted);
  if (!match) {
    throw new Error(`quration edge ${wanted} was not found in .dogma/quration-graph.json.`);
  }
  return match;
}

function buildQurationSelectedEdge(context = {}, options = {}) {
  const edge = pickQurationEdge(context, options.edgeId);
  const source = cleanText(edge.source_label || edge.source_id, "quration source");
  const target = cleanText(edge.target_label || edge.target_id, "quration target");
  const relation = cleanText(edge.relation, "relates to");
  const claim = qurationEdgeClaim(edge);
  const proposed = proposedTestText(edge);
  const question = proposed || cleanText(context.query) || `Can the quration edge "${claim}" be locally grounded and gated?`;
  const validation = cleanText(edge.validation_status, "unvalidated");
  const state = cleanText(edge.state, "unknown");
  const graphId = cleanText(context.graph_id || context.graph?.id, "unknown");
  const graphUrl = cleanText(context.graph_url);

  return {
    id: cleanText(edge.id, "quration.edge"),
    from: source,
    to: target,
    title: claim,
    status: `${state}/${validation}`,
    source: "quration",
    edge_type: "biological",
    relation,
    question,
    facts: {
      readout: target,
      contrast: source,
      coverageGaps: coverageGapsForQurationEdge(edge),
      methodsGraphStatus: "required_before_execution",
      methodsGraphGrounding: {
        status: "required",
        source: "Dogma methods-graph preflight",
        qurationGraphId: graphId,
        qurationGraphUrl: graphUrl,
        qurationQuery: cleanText(context.query)
      },
      methodsGraphSuggestions: [
        "Run Dogma: Generate Methods-Graph Preflight before execution.",
        "Keep quration as the canonical graph, evidence, and event-history surface."
      ],
      evidencePolicy: "quration remains canonical for graph edits and evidence records; Dogma writes local IDE guardrails only.",
      assumptions: [
        `quration graph: ${graphId}`,
        `quration edge state: ${state}`,
        `quration validation: ${validation}`,
        `proposal source: ${cleanText(edge.proposal_source, "unknown")}`,
        `proposed test: ${question}`
      ]
    },
    next_actions: [
      "Review the edge and evidence in quration.",
      "Run Dogma methods-graph preflight before execution.",
      "Treat this as a local evaluation plan, not a biological verdict."
    ]
  };
}

function stripTopHeading(markdown) {
  return String(markdown || "").replace(/^# Dogma Edge Evaluation Plan\s*\n+/, "");
}

function renderQurationEdgeEvaluationPlan(result = {}, context = {}, selectedEdge = null) {
  const edge = selectedEdge || result.selected_edge || {};
  const graphId = cleanText(context.graph_id || context.graph?.id, "unknown");
  const graphUrl = cleanText(context.graph_url, "not available");
  const query = cleanText(context.query, "Untitled quration graph");
  const localPlan = stripTopHeading(renderEdgeEvaluationPlan(result));

  return [
    "# Dogma quration Edge Evaluation Plan",
    "",
    "Dogma generated this local IDE-side plan from a quration graph edge. quration remains the canonical web UI for graph edits, evidence records, and event history.",
    "",
    "## quration Graph",
    "",
    `- Graph ID: ${graphId}`,
    `- Graph URL: ${graphUrl}`,
    `- Query: ${query}`,
    "",
    "## Selected quration Edge",
    "",
    `- Edge ID: ${cleanText(edge.id, "unknown")}`,
    `- Claim: ${cleanText(edge.title, qurationEdgeClaim(edge))}`,
    `- State: ${cleanText(edge.status, "unknown")}`,
    `- Relation: ${cleanText(edge.relation, "unknown")}`,
    `- Proposed test: ${cleanText(edge.question || result.edge?.question, "not declared")}`,
    "",
    "## Dogma Local Plan",
    "",
    localPlan.trimEnd(),
    ""
  ].join("\n");
}

module.exports = {
  buildQurationSelectedEdge,
  pickQurationEdge,
  proposedTestText,
  qurationEdges,
  qurationEdgeClaim,
  renderQurationEdgeEvaluationPlan
};
