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
    throw new Error("No Dogma browser graph edges are available in .dogma/quration-graph.json.");
  }
  const wanted = cleanText(edgeId);
  if (!wanted) return edges[0];
  const match = edges.find((edge) => cleanText(edge.id) === wanted);
  if (!match) {
    throw new Error(`Dogma browser graph edge ${wanted} was not found in .dogma/quration-graph.json.`);
  }
  return match;
}

function buildQurationSelectedEdge(context = {}, options = {}) {
  const edge = pickQurationEdge(context, options.edgeId);
  const source = cleanText(edge.source_label || edge.source_id, "graph source");
  const target = cleanText(edge.target_label || edge.target_id, "graph target");
  const relation = cleanText(edge.relation, "relates to");
  const claim = qurationEdgeClaim(edge);
  const proposed = proposedTestText(edge);
  const question = proposed || cleanText(context.query) || `Can the Dogma browser graph edge "${claim}" be locally grounded and gated?`;
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
    source: "dogma_browser_graph",
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
        "Keep Dogma's browser workspace as the canonical graph, evidence, and event-history surface; quration is the compatibility namespace."
      ],
      evidencePolicy: "Dogma's browser workspace remains canonical for graph edits and evidence records; the IDE writes local guardrails only.",
      assumptions: [
        `Dogma browser graph: ${graphId}`,
        `browser edge state: ${state}`,
        `browser edge validation: ${validation}`,
        `proposal source: ${cleanText(edge.proposal_source, "unknown")}`,
        `proposed test: ${question}`
      ]
    },
    next_actions: [
      "Review the edge and evidence in Dogma's browser graph workspace.",
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
  const query = cleanText(context.query, "Untitled Dogma graph");
  const localPlan = stripTopHeading(renderEdgeEvaluationPlan(result));

  return [
    "# Dogma Browser Edge Evaluation Plan",
    "",
    "Dogma generated this local IDE-side plan from an edge obtained through the quration compatibility API. Dogma's browser workspace remains the canonical UI for graph edits, evidence records, and event history.",
    "",
    "## Browser Graph",
    "",
    `- Graph ID: ${graphId}`,
    `- Graph URL: ${graphUrl}`,
    `- Query: ${query}`,
    "",
    "## Selected Edge",
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
