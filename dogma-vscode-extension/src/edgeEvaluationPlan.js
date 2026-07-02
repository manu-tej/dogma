"use strict";

function escapeCell(value) {
  return String(value ?? "").replace(/\|/g, "\\|");
}

function renderFallback(result) {
  const edge = result.edge || {};
  const selectedEdge = result.selected_edge || result.selectedEdge;
  const selectedHeading = selectedEdge && (selectedEdge.edge_type === "biological" || selectedEdge.edgeType === "biological")
    ? "Selected Biological Edge"
    : "Selected Workbench Edge";
  const rows = (result.contracts || []).length
    ? result.contracts.map((item) => `| ${item.stage || "stage"} | ${item.status || "unknown"} | ${escapeCell(item.detail || "")} |`)
    : ["| coverage_gap | missing | No edge evaluation contracts were returned. |"];
  const gaps = (result.coverage_gaps || []).length
    ? result.coverage_gaps.map((gap) => `- ${gap}`)
    : ["- none"];

  return [
    "# Dogma Edge Evaluation Plan",
    "",
    "This is a typed plan for evaluating one biological edge. It is not a biological verdict.",
    "",
    "## Edge",
    "",
    `- ID: ${edge.id || "not reported"}`,
    `- Question: ${edge.question || "not reported"}`,
    `- Status: ${result.status || "unknown"}`,
    "",
    ...(selectedEdge ? [
      `## ${selectedHeading}`,
      "",
      `- Title: ${selectedEdge.title || "not reported"}`,
      `- From: ${selectedEdge.from || "not reported"}`,
      `- To: ${selectedEdge.to || "not reported"}`,
      `- Status: ${selectedEdge.status || "unknown"}`,
      ""
    ] : []),
    "## Contracts",
    "",
    "| Stage | Status | Detail |",
    "| --- | --- | --- |",
    ...rows,
    "",
    "## Coverage Gaps",
    "",
    ...gaps,
    "",
    "## Invariants",
    "",
    "- Stores support/refute verdicts: false",
    "- Stores confidence grades: false",
    "- Requires explicit execution gates: true",
    ""
  ].join("\n");
}

function renderEdgeEvaluationPlan(result) {
  if (result && typeof result.markdown === "string" && result.markdown.trim()) {
    return result.markdown.endsWith("\n") ? result.markdown : `${result.markdown}\n`;
  }
  return renderFallback(result || {});
}

module.exports = {
  renderEdgeEvaluationPlan
};
