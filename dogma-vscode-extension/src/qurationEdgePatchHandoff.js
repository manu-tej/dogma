"use strict";

function cleanText(value, fallback = "") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function arrayOrEmpty(value) {
  return Array.isArray(value) ? value : [];
}

function proposalFrom(previewResult = {}, applyResult = {}) {
  return applyResult?.proposal || previewResult?.proposal || {};
}

function pipelineReferenceForTarget(targetFile) {
  const target = cleanText(targetFile);
  if (!target) return null;
  if (/\.(nf|smk|snakefile)$/i.test(target) || /(^|\/)Snakefile$/i.test(target)) {
    return `local:${target}`;
  }
  return null;
}

function expectedFromWorkPackage(workPackage = {}) {
  const direction = cleanText(workPackage.quration_edge_plan?.plan?.expected_direction);
  if (!direction || direction === "unknown") return null;
  return direction;
}

function buildGraphEditCandidate(workPackage = {}, proposal = {}) {
  const edgeId = cleanText(workPackage.selected_edge?.id || workPackage.edge_id);
  const pipeline = pipelineReferenceForTarget(proposal.target_file);
  if (!edgeId || !pipeline) return null;
  return {
    op: "set_test",
    edge_id: edgeId,
    pipeline,
    data_accession: null,
    expected: expectedFromWorkPackage(workPackage)
  };
}

function compactContract(contract = {}) {
  return {
    stage: cleanText(contract.stage, "stage"),
    status: cleanText(contract.status, "unknown"),
    detail: cleanText(contract.detail, "not reported")
  };
}

function buildQurationEdgePatchHandoff({
  workPackage = {},
  patchPreview = {},
  patchApply = null,
  generatedAt = new Date().toISOString()
} = {}) {
  const proposal = proposalFrom(patchPreview, patchApply || {});
  const graph = workPackage.quration_graph || {};
  const selected = workPackage.selected_edge || {};
  const dogmaPlan = workPackage.dogma_edge_evaluation?.plan || {};
  const graphEditCandidate = buildGraphEditCandidate(workPackage, proposal);
  const previewStatus = cleanText(patchPreview.status);
  const applyStatus = cleanText(patchApply?.status);
  const applied = Boolean(patchApply?.applied || patchPreview.applied);
  const proposalId = cleanText(proposal.id || patchPreview.proposal_id || patchApply?.proposal_id);
  const sourceArtifacts = [
    ".dogma/quration-edge-work-package.json",
    ".dogma/quration-edge-work-package.md",
    ".dogma/quration-edge-agent-suggestion.md",
    ".dogma/patch-apply-preview.md"
  ];
  if (patchApply) sourceArtifacts.push(".dogma/patch-apply-result.md");

  return {
    contract_version: "dogma-quration-edge-patch-handoff.v1",
    generated_at: generatedAt,
    quration_graph: {
      graph_id: cleanText(graph.graph_id),
      graph_url: cleanText(graph.graph_url),
      query: cleanText(graph.query)
    },
    selected_edge: {
      id: cleanText(selected.id || workPackage.edge_id),
      title: cleanText(selected.title),
      relation: cleanText(selected.relation),
      status: cleanText(selected.status)
    },
    local_patch: {
      proposal_id: proposalId,
      title: cleanText(proposal.title),
      kind: cleanText(proposal.kind),
      target_file: cleanText(proposal.target_file),
      preview_status: previewStatus || null,
      apply_status: applyStatus || null,
      applied,
      message: cleanText(patchApply?.message || patchPreview.message),
      diff: cleanText(proposal.diff),
      safety: proposal.safety || null
    },
    dogma_guardrails: {
      status: cleanText(dogmaPlan.status, "unknown"),
      task_class: cleanText(dogmaPlan.task_class),
      coverage_gaps: arrayOrEmpty(dogmaPlan.coverage_gaps).map((gap) => cleanText(gap)).filter(Boolean),
      contracts: arrayOrEmpty(dogmaPlan.contracts).map(compactContract)
    },
    quration_review: {
      canonical_surface: "quration web graph workspace",
      evidence_policy: "Facts-only handoff. This does not support, refute, resolve, or validate the quration edge.",
      graph_edit_contract: "GraphEdit.set_test",
      graph_edit_candidate_status: graphEditCandidate ? "review_only_not_applied" : "not_available_for_this_patch",
      graph_edit_candidate: graphEditCandidate,
      next_actions: [
        "Review this local patch handoff on the selected quration edge.",
        "If the local workflow target is appropriate, attach it in quration as a proposed test using GraphEdit.set_test.",
        "Run quration's edge resolve/evidence workflow only after dataset, method, and execution evidence exist.",
        "Keep biological support/refute decisions in quration, not in Dogma."
      ]
    },
    source_artifacts: sourceArtifacts
  };
}

function bulletList(items = [], fallback = "none") {
  const cleaned = arrayOrEmpty(items).map((item) => cleanText(item)).filter(Boolean);
  if (!cleaned.length) return [`- ${fallback}`];
  return cleaned.map((item) => `- ${item}`);
}

function renderGraphEditCandidate(candidate) {
  if (!candidate) {
    return [
      "- Candidate: not available for this patch.",
      "- Reason: Dogma only proposes `GraphEdit.set_test` when the local patch target looks like a workflow file."
    ].join("\n");
  }
  return [
    "- Candidate status: review only; not applied to quration.",
    "- Candidate op: `set_test`",
    "",
    "```json",
    JSON.stringify(candidate, null, 2),
    "```"
  ].join("\n");
}

function renderContractRows(contracts = []) {
  if (!Array.isArray(contracts) || !contracts.length) {
    return ["| none | unknown | not reported |"];
  }
  return contracts.map((contract) => [
    `| ${cleanText(contract.stage, "stage")}`,
    cleanText(contract.status, "unknown"),
    cleanText(contract.detail, "not reported").replace(/\|/g, "\\|")
  ].join(" | ") + " |");
}

function renderQurationEdgePatchHandoff(record = {}) {
  const graph = record.quration_graph || {};
  const edge = record.selected_edge || {};
  const patch = record.local_patch || {};
  const guardrails = record.dogma_guardrails || {};
  const review = record.quration_review || {};

  return [
    "# Dogma quration Edge Patch Handoff",
    "",
    "This is a return package from Dogma's VS Code/Cursor IDE surface to quration's graph web UI. It describes local code patch state only; it is not biological evidence and does not resolve the edge.",
    "",
    "## quration Target",
    "",
    `- Graph ID: ${cleanText(graph.graph_id, "unknown")}`,
    `- Graph URL: ${cleanText(graph.graph_url, "not available")}`,
    `- Query: ${cleanText(graph.query, "not recorded")}`,
    `- Edge ID: ${cleanText(edge.id, "unknown")}`,
    `- Edge: ${cleanText(edge.title, "not recorded")}`,
    `- Edge status: ${cleanText(edge.status, "unknown")}`,
    "",
    "## Local Patch",
    "",
    `- Proposal ID: ${cleanText(patch.proposal_id, "not selected")}`,
    `- Title: ${cleanText(patch.title, "not recorded")}`,
    `- Kind: ${cleanText(patch.kind, "not recorded")}`,
    `- Target file: ${cleanText(patch.target_file, "not selected")}`,
    `- Preview status: ${cleanText(patch.preview_status, "not generated")}`,
    `- Apply status: ${cleanText(patch.apply_status, "not applied")}`,
    `- Applied: ${String(Boolean(patch.applied))}`,
    `- Message: ${cleanText(patch.message, "none")}`,
    "",
    "## quration Review Boundary",
    "",
    `- Canonical surface: ${cleanText(review.canonical_surface, "quration")}`,
    `- Evidence policy: ${cleanText(review.evidence_policy, "facts-only")}`,
    `- Graph edit contract: ${cleanText(review.graph_edit_contract, "not declared")}`,
    `- Candidate status: ${cleanText(review.graph_edit_candidate_status, "unknown")}`,
    "",
    renderGraphEditCandidate(review.graph_edit_candidate),
    "",
    "## Dogma Guardrails",
    "",
    `- Status: ${cleanText(guardrails.status, "unknown")}`,
    `- Task class: ${cleanText(guardrails.task_class, "unknown")}`,
    "",
    "### Coverage Gaps",
    "",
    ...bulletList(guardrails.coverage_gaps),
    "",
    "### Contracts",
    "",
    "| Stage | Status | Detail |",
    "| --- | --- | --- |",
    ...renderContractRows(guardrails.contracts),
    "",
    "## Next Actions",
    "",
    ...bulletList(review.next_actions),
    "",
    "## Diff",
    "",
    "```diff",
    cleanText(patch.diff),
    "```",
    "",
    "## Source Artifacts",
    "",
    ...bulletList(record.source_artifacts),
    ""
  ].join("\n");
}

module.exports = {
  buildGraphEditCandidate,
  buildQurationEdgePatchHandoff,
  renderQurationEdgePatchHandoff
};
