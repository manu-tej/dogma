"use strict";

function renderMethodsGraphSubstrate(result) {
  if (result && typeof result.markdown === "string" && result.markdown.trim()) {
    return result.markdown.endsWith("\n") ? result.markdown : `${result.markdown}\n`;
  }
  const surface = (result && result.authoritative_surface) || [];
  const rows = surface.length
    ? surface.map((item) => `| ${item.name || "surface"} | ${item.status || "unknown"} | ${String(item.detail || "").replace(/\|/g, "\\|")} |`)
    : ["| audited_kuzu_graph | gap | No methods-graph substrate report was returned. |"];

  return [
    "# Dogma Methods-Graph Substrate",
    "",
    "Dogma treats methods-graph as the guardrail substrate for method grounding, workflow validation, and coverage gaps.",
    "",
    `- Status: ${(result && result.status) || "unknown"}`,
    "",
    "| Surface | Status | Detail |",
    "| --- | --- | --- |",
    ...rows,
    ""
  ].join("\n");
}

module.exports = {
  renderMethodsGraphSubstrate
};
