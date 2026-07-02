"use strict";

const { proposedTestText, qurationEdgeClaim, qurationEdges } = require("./qurationEdgeEvaluationPlan");

function cleanText(value, fallback = "") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function edgeState(edge = {}) {
  return cleanText(edge.state, "unknown");
}

function edgeValidation(edge = {}) {
  return cleanText(edge.validation_status || edge.display_status, "unvalidated");
}

function edgeLabel(edge = {}) {
  return qurationEdgeClaim(edge);
}

function buildQurationEdgeQuickPickItems(context = {}) {
  return qurationEdges(context).map((edge) => {
    const claim = edgeLabel(edge);
    const proposed = proposedTestText(edge);
    const state = edgeState(edge);
    const validation = edgeValidation(edge);
    return {
      label: claim,
      description: cleanText(edge.id, "quration.edge"),
      detail: [
        `state: ${state}`,
        `validation: ${validation}`,
        proposed ? `proposed: ${proposed}` : "proposed: not declared"
      ].join(" | "),
      edgeId: cleanText(edge.id),
      edge
    };
  });
}

function buildQurationEdgeSelectionRecord({
  context = {},
  edge = {},
  selectedAt = new Date().toISOString(),
  selectionSource = "quick_pick"
} = {}) {
  return {
    contract_version: "dogma-quration-edge-selection.v1",
    selected_at: selectedAt,
    selection_source: selectionSource,
    quration_graph: {
      graph_id: cleanText(context.graph_id || context.graph?.id),
      graph_url: cleanText(context.graph_url),
      query: cleanText(context.query)
    },
    selected_edge: {
      id: cleanText(edge.id, "quration.edge"),
      claim: edgeLabel(edge),
      source_id: cleanText(edge.source_id),
      source_label: cleanText(edge.source_label || edge.source_id),
      target_id: cleanText(edge.target_id),
      target_label: cleanText(edge.target_label || edge.target_id),
      relation: cleanText(edge.relation, "relates to"),
      state: edgeState(edge),
      validation_status: edgeValidation(edge),
      proposal_source: cleanText(edge.proposal_source, "unknown"),
      proposed_test: proposedTestText(edge)
    },
    ide_policy: {
      canonical_graph_surface: "quration",
      local_surface: "Dogma VS Code/Cursor extension",
      evidence_policy: "Selection is local IDE state only; it does not mutate quration or resolve evidence."
    },
    next_actions: [
      "Use Dogma quration edge commands to fetch the edge plan, generate a local guardrail plan, or build a work package for this selected edge.",
      "Use quration's web graph UI for graph edits, evidence records, event history, and biological review."
    ]
  };
}

function renderQurationEdgeSelection(record = {}) {
  const graph = record.quration_graph || {};
  const edge = record.selected_edge || {};
  const policy = record.ide_policy || {};
  const actions = Array.isArray(record.next_actions) ? record.next_actions : [];

  return [
    "# Dogma quration Edge Selection",
    "",
    "Dogma selected this quration edge for local IDE work. quration remains the canonical graph web UI for graph edits, evidence records, and event history.",
    "",
    "## quration Graph",
    "",
    `- Graph ID: ${cleanText(graph.graph_id, "unknown")}`,
    `- Graph URL: ${cleanText(graph.graph_url, "not available")}`,
    `- Query: ${cleanText(graph.query, "not recorded")}`,
    "",
    "## Selected Edge",
    "",
    `- Edge ID: ${cleanText(edge.id, "unknown")}`,
    `- Claim: ${cleanText(edge.claim, "not recorded")}`,
    `- Source: ${cleanText(edge.source_label || edge.source_id, "unknown")}`,
    `- Target: ${cleanText(edge.target_label || edge.target_id, "unknown")}`,
    `- Relation: ${cleanText(edge.relation, "unknown")}`,
    `- State: ${cleanText(edge.state, "unknown")}`,
    `- Validation: ${cleanText(edge.validation_status, "unknown")}`,
    `- Proposed test: ${cleanText(edge.proposed_test, "not declared")}`,
    `- Selected at: ${cleanText(record.selected_at, "unknown")}`,
    `- Selection source: ${cleanText(record.selection_source, "unknown")}`,
    "",
    "## Boundary",
    "",
    `- Canonical graph surface: ${cleanText(policy.canonical_graph_surface, "quration")}`,
    `- Local surface: ${cleanText(policy.local_surface, "Dogma")}`,
    `- Evidence policy: ${cleanText(policy.evidence_policy, "local selection only")}`,
    "",
    "## Next Actions",
    "",
    ...(actions.length ? actions.map((action) => `- ${cleanText(action)}`) : ["- none"]),
    ""
  ].join("\n");
}

module.exports = {
  buildQurationEdgeQuickPickItems,
  buildQurationEdgeSelectionRecord,
  renderQurationEdgeSelection
};
