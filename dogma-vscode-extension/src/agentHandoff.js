"use strict";

function cleanText(value, fallback = "not available") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function compact(value, fallback = "not available", maxChars = 180) {
  const text = cleanText(value, fallback).replace(/\s+/g, " ");
  return text.length > maxChars ? `${text.slice(0, maxChars - 1)}...` : text;
}

function artifactStatus(value) {
  return value ? "present" : "missing";
}

function graphId(artifacts = {}) {
  return artifacts.qurationGraph?.graph_id ||
    artifacts.qurationEdgeSelection?.quration_graph?.graph_id ||
    artifacts.qurationEdgeWorkPackage?.quration_graph?.graph_id ||
    null;
}

function selectedEdge(artifacts = {}) {
  return artifacts.qurationEdgeSelection?.selected_edge ||
    artifacts.qurationEdgeWorkPackage?.selected_edge ||
    artifacts.qurationEdgePatchHandoff?.selected_edge ||
    null;
}

function methodsGraphGate(artifacts = {}) {
  return (artifacts.ideReadiness?.gates || []).find((gate) => gate.id === "methods_graph") || {};
}

function boundedList(values, limit = 8) {
  return Array.isArray(values) ? values.filter(Boolean).slice(0, limit) : [];
}

function methodsGraphPreflightSummary(artifacts = {}) {
  const preflight = artifacts.methodsGraphPreflight || {};
  const gate = methodsGraphGate(artifacts);
  const verdict = preflight.verdict || {};
  const methodIds = boundedList(preflight.method_chain?.method_ids, 8);
  const coverageGaps = boundedList(preflight.coverage_gaps, 12);
  const nextActions = boundedList(preflight.next_actions, 8);
  return {
    status: preflight.status || gate.state || "not checked",
    substrate_status: preflight.substrate_status || "not checked",
    verdict_status: verdict.status || "not available",
    method_ids: methodIds,
    coverage_gaps: coverageGaps,
    next_actions: nextActions,
    artifact: preflight.service ? ".dogma/methods-graph-preflight.json" : null
  };
}

function buildAgentHandoffRecord({ workspaceName, scan = {}, artifacts = {}, activeEditor = null, settings = {}, generatedAt } = {}) {
  const edge = selectedEdge(artifacts);
  const issueCounts = scan.issue_counts || {};
  const methodsGraph = methodsGraphPreflightSummary(artifacts);
  return {
    contract_version: "dogma-agent-handoff.v1",
    generated_at: generatedAt || new Date().toISOString(),
    workspace: {
      name: cleanText(workspaceName, "workspace"),
      scan_source: scan.scan_source || "not scanned",
      issue_count: Number(scan.issue_count || 0),
      errors: Number(issueCounts.errors || 0),
      warnings: Number(issueCounts.warnings || 0),
      trust_status: scan.trust_status || "unknown",
      human_data: Boolean(scan.human_data)
    },
    active_editor: activeEditor ? {
      path: activeEditor.path || null,
      language_id: activeEditor.language_id || null,
      has_selection: activeEditor.selection?.is_empty === false
    } : null,
    quration: {
      status: artifacts.qurationStatus?.status || "not checked",
      graph_id: graphId(artifacts),
      graph_url: artifacts.qurationGraph?.graph_url || artifacts.qurationEdgeSelection?.quration_graph?.graph_url || null,
      selected_edge_id: edge?.id || null,
      selected_edge_claim: edge?.claim || edge?.title || null,
      selected_edge_state: edge?.state || edge?.validation_status || null
    },
    guardrails: {
      ide_readiness: artifacts.ideReadiness?.status || "not checked",
      llm_provider: artifacts.llmProviderStatus?.provider || settings.agentProvider || "not configured",
      llm_status: artifacts.llmProviderStatus?.status || "not checked",
      methods_graph: methodsGraph.status,
      workspace_trust: (artifacts.ideReadiness?.gates || []).find((gate) => gate.id === "workspace_trust")?.state || scan.trust_status || "unknown"
    },
    methods_graph_preflight: methodsGraph,
    artifacts: {
      ide_readiness: artifactStatus(artifacts.ideReadiness),
      methods_graph_preflight: artifactStatus(artifacts.methodsGraphPreflight),
      quration_status: artifactStatus(artifacts.qurationStatus),
      quration_graph: artifactStatus(artifacts.qurationGraph),
      quration_edge_selection: artifactStatus(artifacts.qurationEdgeSelection),
      quration_edge_work_package: artifactStatus(artifacts.qurationEdgeWorkPackage),
      quration_edge_agent_suggestion: artifactStatus(artifacts.qurationEdgeAgentSuggestion),
      quration_edge_patch_handoff: artifactStatus(artifacts.qurationEdgePatchHandoff),
      llm_provider_status: artifactStatus(artifacts.llmProviderStatus)
    },
    output_paths: {
      markdown: ".dogma/agent-handoff.md",
      json: ".dogma/agent-handoff.json",
      cursor_rules: ".cursor/rules/dogma-bioinformatics.mdc"
    },
    policy: {
      graph_surface: "quration web graph workspace",
      ide_surface: "Dogma VS Code/Cursor extension",
      local_service_boundary: "Dogma local Python sidecar",
      methods_graph: "methods-graph is the authority for method grounding, assumptions, workflow validation, and coverage gaps.",
      biological_verdicts: "Do not assert support/refute/resolved verdicts from IDE context.",
      execution: "Do not run real workflow execution; use dry-run/stub-run previews unless the user explicitly confirms a trusted local operation.",
      privacy: "Preserve Dogma redaction and workspace trust policy, especially for detected human data."
    }
  };
}

function renderArtifactRows(artifacts = {}) {
  return Object.entries(artifacts).map(([key, value]) => `| ${key} | ${value} |`).join("\n");
}

function renderBulletRows(values = [], fallback = "- none") {
  return values.length ? values.map((value) => `- ${value}`) : [fallback];
}

function renderAgentHandoffMarkdown(record = {}) {
  const workspace = record.workspace || {};
  const quration = record.quration || {};
  const guardrails = record.guardrails || {};
  const methodsGraph = record.methods_graph_preflight || {};
  const policy = record.policy || {};
  return [
    "# Dogma Agent Handoff",
    "",
    "This is the durable handoff from Dogma to Cursor or another coding agent. It keeps the coding agent scoped to local IDE/co-scientist work while quration remains the canonical graph/evidence UI and methods-graph remains the guardrail authority.",
    "",
    "## Workspace",
    "",
    `- Name: ${cleanText(workspace.name)}`,
    `- Scan source: ${cleanText(workspace.scan_source)}`,
    `- Findings: ${Number(workspace.issue_count || 0)} total, ${Number(workspace.errors || 0)} error(s), ${Number(workspace.warnings || 0)} warning(s)`,
    `- Trust: ${cleanText(workspace.trust_status)}`,
    `- Human data detected: ${workspace.human_data ? "yes" : "no"}`,
    "",
    "## Active quration Context",
    "",
    `- quration status: ${cleanText(quration.status)}`,
    `- Graph: ${cleanText(quration.graph_id)}`,
    `- Graph URL: ${cleanText(quration.graph_url)}`,
    `- Selected edge: ${cleanText(quration.selected_edge_id)}`,
    `- Edge claim: ${cleanText(quration.selected_edge_claim)}`,
    `- Edge state: ${cleanText(quration.selected_edge_state)}`,
    "",
    "## Guardrails",
    "",
    `- IDE readiness: ${cleanText(guardrails.ide_readiness)}`,
    `- Workspace trust gate: ${cleanText(guardrails.workspace_trust)}`,
    `- methods-graph gate: ${cleanText(guardrails.methods_graph)}`,
    `- LLM provider: ${cleanText(guardrails.llm_provider)} (${cleanText(guardrails.llm_status)})`,
    "",
    "## methods-graph Preflight",
    "",
    `- Status: ${cleanText(methodsGraph.status)}`,
    `- Substrate: ${cleanText(methodsGraph.substrate_status)}`,
    `- Verdict: ${cleanText(methodsGraph.verdict_status)}`,
    `- Method IDs: ${methodsGraph.method_ids?.length ? methodsGraph.method_ids.join(", ") : "none"}`,
    `- Artifact: ${cleanText(methodsGraph.artifact)}`,
    "",
    "### Coverage Gaps",
    "",
    ...renderBulletRows(methodsGraph.coverage_gaps || []),
    "",
    "### Next Actions",
    "",
    ...renderBulletRows(methodsGraph.next_actions || []),
    "",
    "## Available Artifacts",
    "",
    "| Artifact | Status |",
    "| --- | --- |",
    renderArtifactRows(record.artifacts || {}),
    "",
    "## Coding Agent Contract",
    "",
    `- Graph surface: ${policy.graph_surface}`,
    `- IDE surface: ${policy.ide_surface}`,
    `- Local service boundary: ${policy.local_service_boundary}`,
    `- methods-graph: ${policy.methods_graph}`,
    `- Biological verdicts: ${policy.biological_verdicts}`,
    `- Execution: ${policy.execution}`,
    `- Privacy: ${policy.privacy}`,
    "",
    "## Use This Next",
    "",
    "- Read `.cursor/rules/dogma-bioinformatics.mdc` before proposing code changes.",
    "- Prefer `.dogma/quration-edge-work-package.md` when it exists; it is the active graph-edge work unit.",
    "- Prefer `.dogma/ide-readiness.md`, `.dogma/methods-graph-preflight.md`, `.dogma/evidence-ledger.md`, and `.dogma/patch-proposals.md` as supporting local evidence.",
    "- Keep patches narrow and previewable. Do not bypass Dogma trust gates or quration graph review.",
    ""
  ].join("\n");
}

function renderCursorRules(record = {}) {
  const workspace = record.workspace || {};
  const quration = record.quration || {};
  const guardrails = record.guardrails || {};
  const methodsGraph = record.methods_graph_preflight || {};
  const policy = record.policy || {};
  const gapText = methodsGraph.coverage_gaps?.length ? methodsGraph.coverage_gaps.join(", ") : "none";
  return [
    "---",
    "description: Dogma bioinformatics IDE guardrails for this workspace",
    "globs: [\"**/*\"]",
    "alwaysApply: true",
    "---",
    "",
    "# Dogma Bioinformatics Guardrails",
    "",
    "You are working inside a Dogma-managed bioinformatics workspace. Follow these rules before proposing or applying code changes.",
    "",
    "## Current State",
    "",
    `- Workspace: ${cleanText(workspace.name)}`,
    `- Scan: ${cleanText(workspace.scan_source)}; ${Number(workspace.issue_count || 0)} finding(s), ${Number(workspace.errors || 0)} error(s), ${Number(workspace.warnings || 0)} warning(s)`,
    `- Trust: ${cleanText(workspace.trust_status)}; human data detected: ${workspace.human_data ? "yes" : "no"}`,
    `- quration graph: ${cleanText(quration.graph_id)}`,
    `- quration selected edge: ${compact(quration.selected_edge_claim || quration.selected_edge_id)}`,
    `- IDE readiness: ${cleanText(guardrails.ide_readiness)}; methods-graph: ${cleanText(guardrails.methods_graph)}; LLM: ${cleanText(guardrails.llm_provider)} (${cleanText(guardrails.llm_status)})`,
    `- methods-graph preflight: ${cleanText(methodsGraph.status)}; coverage gaps: ${gapText}`,
    "",
    "## Hard Rules",
    "",
    `- Treat ${policy.graph_surface || "quration"} as the canonical graph/evidence UI. Do not duplicate graph edits in local code without a Dogma handoff artifact.`,
    "- Do not assert biological support, refute, resolve, confidence, or causal truth from IDE context.",
    "- Do not invent sample metadata, clinical labels, genome build, annotation release, contrasts, containers, or method assumptions.",
    "- Treat missing methods-graph method, assumption, container, executor, or post-run coverage as an explicit guardrail gap.",
    "- Do not run real workflows or destructive commands. Use Dogma dry-run/stub-run previews and wait for explicit user confirmation.",
    "- Preserve privacy and Dogma redaction. For human data, do not expose raw sample identifiers unless the workspace trust artifact explicitly permits local operations.",
    "- Prefer narrow patches that can be previewed through Dogma. Keep patch rationale tied to a finding, guardrail, quration edge work package, or methods-graph gap.",
    "",
    "## Preferred Context Files",
    "",
    "- `.dogma/agent-handoff.md`",
    "- `.dogma/ide-readiness.md`",
    "- `.dogma/quration-edge-work-package.md`",
    "- `.dogma/methods-graph-preflight.md`",
    "- `.dogma/evidence-ledger.md`",
    "- `.dogma/patch-proposals.md`",
    "",
    "## Response Style",
    "",
    "- Lead with the next smallest safe edit or question.",
    "- Name the files that would change.",
    "- State which Dogma gate or artifact justifies the recommendation.",
    "- When evidence is missing, call it a coverage gap instead of filling it in.",
    ""
  ].join("\n");
}

module.exports = {
  buildAgentHandoffRecord,
  renderAgentHandoffMarkdown,
  renderCursorRules
};
