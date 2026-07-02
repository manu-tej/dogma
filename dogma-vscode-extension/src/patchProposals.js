"use strict";

function methodIdsFromPreflight(preflight) {
  const methodIds = preflight?.method_chain?.method_ids;
  return Array.isArray(methodIds) ? methodIds : [];
}

function coverageGapsFromPreflight(preflight) {
  const gaps = preflight?.coverage_gaps;
  return Array.isArray(gaps) ? gaps : [];
}

function nextActionsFromPreflight(preflight) {
  const actions = preflight?.next_actions;
  return Array.isArray(actions) ? actions : [];
}

function renderMethodsGraphPreflight(preflight) {
  if (!preflight || typeof preflight !== "object") {
    return [
      "## Methods-Graph Preflight",
      "",
      "- Status: not checked",
      "- Coverage gaps: not reported",
      ""
    ].join("\n");
  }

  const methodIds = methodIdsFromPreflight(preflight);
  const coverageGaps = coverageGapsFromPreflight(preflight);
  const nextActions = nextActionsFromPreflight(preflight);
  const verdict = preflight.verdict || {};

  return [
    "## Methods-Graph Preflight",
    "",
    `- Status: ${preflight.status || "not reported"}`,
    `- Substrate status: ${preflight.substrate_status || "not reported"}`,
    `- Verdict: ${verdict.status || "not available"}`,
    `- Method IDs: ${methodIds.length ? methodIds.join(", ") : "none"}`,
    "",
    "### Coverage Gaps",
    "",
    ...(coverageGaps.length ? coverageGaps.map((gap) => `- ${gap}`) : ["- none"]),
    "",
    "### Next Actions",
    "",
    ...(nextActions.length ? nextActions.map((action) => `- ${action}`) : ["- none"]),
    ""
  ].join("\n");
}

function renderPatchProposals(result) {
  const proposals = result.proposals || [];
  const summary = result.scan_summary || {};
  const sections = proposals.length
    ? proposals.map((proposal) => [
        `## ${proposal.id}: ${proposal.title}`,
        "",
        `- Kind: ${proposal.kind}`,
        `- Severity: ${proposal.severity}`,
        `- Target: ${proposal.target_file}`,
        `- Scope: ${proposal.safety?.scope || "not reported"}`,
        `- Requires review: ${String(Boolean(proposal.safety?.requires_review))}`,
        `- Auto apply: ${String(Boolean(proposal.safety?.auto_apply))}`,
        "",
        "### Rationale",
        "",
        proposal.rationale || "No rationale reported.",
        "",
        "### Diff",
        "",
        "```diff",
        proposal.diff || "",
        "```",
        ""
      ].join("\n")).join("\n")
    : "No Dogma patch proposals are available for the current scan.";

  return [
    "# Dogma Patch Proposals",
    "",
    `Root: ${result.root || "not reported"}`,
    `Proposal count: ${result.proposal_count || proposals.length}`,
    `Scan risk: ${summary.risk_level || "not reported"}`,
    `Errors: ${summary.errors || 0}`,
    `Warnings: ${summary.warnings || 0}`,
    "",
    renderMethodsGraphPreflight(result.methods_graph_preflight),
    "",
    sections,
    "",
    "## Safety",
    "",
    "- Proposals are review-first.",
    "- Applying a proposal requires an explicit command.",
    "- Regenerate proposals if target files change.",
    ""
  ].join("\n");
}

function renderPatchApplyResult(result) {
  const proposal = result.proposal || {};
  const methodsGraph = result.methods_graph_preflight || result.proposal_result?.methods_graph_preflight;
  return [
    "# Dogma Patch Apply Result",
    "",
    `Status: ${result.status || "unknown"}`,
    `Applied: ${String(Boolean(result.applied))}`,
    `Message: ${result.message || "none"}`,
    `Proposal: ${proposal.id || "not selected"}`,
    `Target: ${proposal.target_file || "not selected"}`,
    "",
    renderMethodsGraphPreflight(methodsGraph),
    "",
    "## Diff",
    "",
    "```diff",
    proposal.diff || "",
    "```",
    ""
  ].join("\n");
}

module.exports = {
  renderPatchApplyResult,
  renderMethodsGraphPreflight,
  renderPatchProposals
};
