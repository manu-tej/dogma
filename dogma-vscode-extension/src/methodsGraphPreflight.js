"use strict";

function renderFallback(result) {
  const facts = (result.dataset_facts && result.dataset_facts.facts) || {};
  const factRows = Object.keys(facts).length
    ? Object.entries(facts).map(([key, value]) => `| ${key} | ${value} |`)
    : ["| none | none |"];
  const chain = (result.method_chain && result.method_chain.steps) || [];
  const stepRows = chain.length
    ? chain.map((step) => `| ${step.process || "step"} | ${step.location || "unknown"} | ${step.method_id || "coverage gap"} | ${step.status || "unknown"} |`)
    : ["| none | none | none | coverage_gap |"];
  const gaps = result.coverage_gaps || [];
  const gapRows = gaps.length ? gaps.map((gap) => `- ${gap}`) : ["- none"];

  return [
    "# Dogma Methods-Graph Preflight",
    "",
    "This is a methodological preflight for IDE workflow actions. It is not a biological support/refute verdict.",
    "",
    "## Summary",
    "",
    `- Status: ${result.status || "unknown"}`,
    `- Substrate status: ${result.substrate_status || "unknown"}`,
    `- Verdict: ${(result.verdict && result.verdict.status) || "not available"}`,
    "",
    "## Dataset Facts",
    "",
    "| Fact | Value |",
    "| --- | --- |",
    ...factRows,
    "",
    "## Method Chain",
    "",
    "| Process | Location | Method ID | Status |",
    "| --- | --- | --- | --- |",
    ...stepRows,
    "",
    "## Coverage Gaps",
    "",
    ...gapRows,
    ""
  ].join("\n");
}

function renderMethodsGraphPreflight(result) {
  if (result && typeof result.markdown === "string" && result.markdown.trim()) {
    return result.markdown.endsWith("\n") ? result.markdown : `${result.markdown}\n`;
  }
  return renderFallback(result || {});
}

module.exports = {
  renderMethodsGraphPreflight
};
