"use strict";

const { deriveNextIdeAction } = require("./nextIdeAction");

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  })[character]);
}

function countBySeverity(issues = []) {
  return {
    errors: issues.filter((issue) => issue.severity === "error").length,
    warnings: issues.filter((issue) => issue.severity === "warning").length
  };
}

function statusFor(issues = [], scanSource = "not scanned", context = {}) {
  if (scanSource === "not scanned") return "waiting";
  if (context.trust?.trusted === false && context.trust?.human_data === true) return "blocked";
  const counts = countBySeverity(issues);
  if (counts.errors) return "blocked";
  if (counts.warnings) return "review";
  return "ready";
}

function renderMetric(label, value) {
  return `<div class="metric"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`;
}

function commandPayloadAttribute(payload) {
  return escapeHtml(JSON.stringify(payload || {}));
}

function renderAction(command, label, kind = "secondary", payload = null) {
  const payloadAttribute = payload ? ` data-payload="${commandPayloadAttribute(payload)}"` : "";
  return `<button class="${escapeHtml(kind)}" data-command="${escapeHtml(command)}"${payloadAttribute}>${escapeHtml(label)}</button>`;
}

function renderActionGroup(actions = []) {
  return `<section class="action-group" aria-label="Dogma actions">
    ${actions.map((action) => renderAction(action.command, action.label, action.kind)).join("")}
  </section>`;
}

function listValue(items = [], fallback = "not detected", limit = 3) {
  if (!Array.isArray(items) || !items.length) return fallback;
  const visible = items.slice(0, limit).join(", ");
  const more = items.length > limit ? ` +${items.length - limit}` : "";
  return `${visible}${more}`;
}

function formatCount(value) {
  const number = Number(value || 0);
  return Number.isFinite(number) ? number.toLocaleString("en-US") : "0";
}

function renderBioState(context = {}) {
  const samples = context.samples || {};
  const counts = context.counts || {};
  const reference = context.reference || {};
  const trust = context.trust || {};
  const workflow = context.workflowProcesses || context.workflow_processes || [];
  const trustStatus = trust.status || (context.privacy?.contains_human_data ? "human data" : "not declared");
  const cards = [
    ["Samples", formatCount(samples.count), listValue(samples.conditions, "conditions not declared")],
    ["FASTQ", `${formatCount(counts.fastqReads)} reads`, listValue(context.fastqFiles, "no FASTQ detected")],
    ["Workflow", workflow.length ? formatCount(workflow.length) : "0", listValue(workflow, "no workflow detected")],
    ["Reference", reference.genome_build || reference.genomeBuild || "not declared", reference.annotation || "annotation missing"],
    ["Trust", trustStatus, trust.trusted === true ? "local operations allowed" : trust.human_data ? "local operations gated" : "trust policy not required"]
  ];

  return `<div class="bio-state">
    ${cards.map(([label, value, detail]) => (
      `<article class="bio-card">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
        <p>${escapeHtml(detail)}</p>
      </article>`
    )).join("")}
  </div>`;
}

function renderFindings(issues = []) {
  if (!issues.length) {
    return `<div class="empty-state">No Dogma findings yet. Run a workspace scan to populate diagnostics, graph state, and guardrails.</div>`;
  }

  return issues.slice(0, 12).map(renderFindingArticle).join("");
}

function renderFindingArticle(issue) {
  const payload = {
    file: issue.file || "",
    line: Number(issue.line || 1)
  };
  return (
    `<article class="finding ${escapeHtml(issue.severity || "warning")}">
      <div>
        <strong>${escapeHtml(issue.severity || "warning")}</strong>
        <span>${escapeHtml(issue.file || "workspace")}:${escapeHtml(issue.line || 1)}</span>
      </div>
      <p>${escapeHtml(issue.message || issue.code || "Dogma finding")}</p>
      <div class="finding-actions">
        ${renderAction("dogma.openFinding", "Open", "inline", payload)}
      </div>
    </article>`
  );
}

function renderContextRows(context = {}) {
  const rows = [
    ["Assay", context.assay || context.metadata?.assay || "not declared"],
    ["Organism", context.organism || context.metadata?.organism || "not declared"],
    ["Reference", context.reference?.genome_build || context.reference?.genomeBuild || "not declared"],
    ["Annotation", context.reference?.annotation || "not declared"],
    ["Workflow", (context.workflowProcesses || context.workflow_processes || []).join(", ") || "not detected"],
    ["Samples", context.samples?.count ?? context.sampleCount ?? "not detected"]
  ];

  return rows.map(([label, value]) => (
    `<div class="context-row"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`
  )).join("");
}

function truncateLine(value, maxLength = 140) {
  const text = String(value || "").trim();
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 1)}...`;
}

function issueCountForFile(issues = [], filePath = "") {
  if (!filePath) return 0;
  return issues.filter((issue) => issue.file === filePath).length;
}

function issuesForFile(issues = [], filePath = "") {
  if (!filePath) return [];
  return issues.filter((issue) => issue.file === filePath);
}

function renderActiveFileFindings(activeIssues = []) {
  if (!activeIssues.length) {
    return `<div class="empty-state active-file-findings">No Dogma findings are currently attached to this file.</div>`;
  }

  return `<div class="active-file-findings">
    <h3>Active File Findings</h3>
    ${activeIssues.slice(0, 5).map(renderFindingArticle).join("")}
  </div>`;
}

function renderActiveEditor(activeEditor, issues = []) {
  if (!activeEditor) {
    return `<div class="empty-state">No file-backed active editor. Open a workspace file to review it with Dogma.</div>`;
  }

  const hasSelection = activeEditor.selection?.is_empty === false;
  const activeIssues = issuesForFile(issues, activeEditor.path);
  const fileIssues = activeIssues.length;
  const rows = [
    ["File", activeEditor.path || "unknown"],
    ["Language", activeEditor.language_id || "unknown"],
    ["Selection", hasSelection ? "selected text included" : "current line only"],
    ["Findings", fileIssues ? `${fileIssues} in this file` : "none in this file"],
    ["Line", truncateLine(activeEditor.current_line)]
  ];

  return `<div class="context">
    ${rows.map(([label, value]) => `<div class="context-row"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}
    <div class="active-actions">
      ${renderAction("dogma.previewActiveBioFile", "Preview Active Bio File")}
      ${renderAction("dogma.askDogmaAboutSelection", "Ask Dogma About Selection")}
      ${renderAction("dogma.previewActiveFilePatch", "Preview Active File Patch")}
      ${renderAction("dogma.applyActiveFilePatch", "Apply Active File Patch")}
      ${renderAction("dogma.reviewActiveFinding", "Review Active Finding")}
      ${renderAction("dogma.reviewActiveFile", "Review Active File", "primary")}
    </div>
  </div>
  ${renderActiveFileFindings(activeIssues)}`;
}

function compactText(value, fallback = "not available", maxLength = 120) {
  const text = String(value || "").trim();
  if (!text) return fallback;
  return truncateLine(text, maxLength);
}

function artifactPresent(artifacts = {}) {
  return Boolean(
    artifacts.qurationGraph ||
    artifacts.qurationEdgeSelection ||
    artifacts.qurationStatus ||
    artifacts.ideReadiness ||
    artifacts.methodsGraphPreflight ||
    artifacts.qurationEdgeWorkPackage ||
    artifacts.agentHandoff
  );
}

function edgeFromArtifacts(artifacts = {}) {
  return artifacts.qurationEdgeSelection?.selected_edge || artifacts.qurationEdgeWorkPackage?.selected_edge || null;
}

function graphFromArtifacts(artifacts = {}) {
  return artifacts.qurationGraph || artifacts.qurationEdgeSelection?.quration_graph || artifacts.qurationEdgeWorkPackage?.quration_graph || {};
}

function edgeStatus(edge = {}) {
  const state = edge.state || edge.status || "unknown";
  const validation = edge.validation_status || "";
  return validation && !String(state).includes(validation) ? `${state}/${validation}` : state;
}

function graphShape(graph = {}) {
  const summary = graph.summary || {};
  const nodes = summary.nodes ?? graph.graph?.nodes?.length;
  const edges = summary.edges ?? graph.graph?.edges?.length;
  if (nodes === undefined && edges === undefined) return "not pulled";
  const edgeStates = summary.edge_states ? Object.keys(summary.edge_states).join(", ") : "";
  const suffix = edgeStates ? `; ${edgeStates}` : "";
  return `${formatCount(nodes)} node(s), ${formatCount(edges)} edge(s)${suffix}`;
}

function qurationBridgeStatus(status = {}) {
  if (!status.contract_version) return "not checked";
  const backend = status.backend?.status || (status.backend?.reachable ? "reachable" : "offline");
  const canvas = status.canvas?.reachable ? "canvas reachable" : "canvas offline";
  return `${status.status || "unknown"}; ${backend}; ${canvas}`;
}

function readinessSummary(readiness = {}) {
  if (!readiness.contract_version) return "not checked";
  const blocked = (readiness.gates || []).filter((gate) => gate.state === "blocked").length;
  const warnings = (readiness.gates || []).filter((gate) => gate.state === "warning").length;
  const suffix = blocked || warnings ? `; ${blocked} blocked, ${warnings} warning` : "";
  return `${readiness.status || "unknown"}${suffix}`;
}

function agentSuggestionSummary(record = {}) {
  if (!record.contract_version) return "not generated";
  const status = record.suggestion?.status || "unknown";
  const patchCount = Number(record.suggestion?.patch_preview_count || 0);
  const llm = record.suggestion?.llm_executed ? "Claude" : "prompt-ready";
  return `${status}; ${patchCount} patch proposal(s); ${llm}`;
}

function llmProviderSummary(record = {}) {
  if (!record.service && !record.status && !record.provider) return "not checked";
  const provider = record.provider || "none";
  const status = record.status || "unknown";
  const resolved = record.claude_subscription?.resolved_cli_path ? "CLI found" : "CLI missing";
  return `${provider}: ${status}; ${resolved}`;
}

function methodsGraphPreflightSummary(record = {}) {
  if (!record.service && !record.status) return "not generated";
  const gaps = Array.isArray(record.coverage_gaps) ? record.coverage_gaps.length : 0;
  const substrate = record.substrate_status || "unknown substrate";
  return `${record.status || "unknown"}; ${substrate}; ${gaps} coverage gap(s)`;
}

function agentHandoffSummary(record = {}) {
  if (!record.contract_version) return "not generated";
  const workspace = record.workspace?.name || "workspace";
  const methodsGraph = record.guardrails?.methods_graph || "not checked";
  const path = record.output_paths?.cursor_rules || ".cursor/rules/dogma-bioinformatics.mdc";
  return `${workspace}; methods-graph ${methodsGraph}; ${path}`;
}

function activeNextAction(artifacts = {}) {
  const routed = deriveNextIdeAction(artifacts);
  if (routed?.label) return `${routed.label}: ${routed.reason}`;
  const readinessAction = artifacts.ideReadiness?.next_actions?.[0];
  if (readinessAction) return readinessAction.replace(/`/g, "");
  const selectionAction = artifacts.qurationEdgeSelection?.next_actions?.[0];
  if (selectionAction) return selectionAction;
  const workPackageAction = artifacts.qurationEdgeWorkPackage?.selected_edge?.next_actions?.[0];
  if (workPackageAction) return workPackageAction;
  return "Prepare IDE Session";
}

function renderActiveInvestigation(artifacts = {}) {
  if (!artifactPresent(artifacts)) {
    return `<div class="empty-state">No active Dogma investigation artifacts yet. Run Prepare IDE Session or pull quration graph context.</div>`;
  }

  const graph = graphFromArtifacts(artifacts);
  const edge = edgeFromArtifacts(artifacts) || {};
  const rows = [
    ["Graph", compactText(graph.graph_id || graph.id, "no graph id")],
    ["Question", compactText(graph.query, "no quration question", 150)],
    ["Shape", graphShape(graph)],
    ["Selected edge", compactText(edge.claim || edge.title || edge.id, "none selected", 150)],
    ["Edge state", edge.id ? compactText(edgeStatus(edge)) : "none selected"],
    ["quration", qurationBridgeStatus(artifacts.qurationStatus || {})],
    ["IDE gates", readinessSummary(artifacts.ideReadiness || {})],
    ["methods-graph", methodsGraphPreflightSummary(artifacts.methodsGraphPreflight || {})],
    ["Claude", llmProviderSummary(artifacts.llmProviderStatus || {})],
    ["Agent handoff", agentHandoffSummary(artifacts.agentHandoff || {})],
    ["Agent", agentSuggestionSummary(artifacts.qurationEdgeAgentSuggestion || {})],
    ["Next", compactText(activeNextAction(artifacts), "Prepare IDE Session", 170)]
  ];

  return `<div class="investigation">
    <dl class="context">${rows.map(([label, value]) => `<div class="context-row"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>
    ${renderActionGroup([
      { command: "dogma.runNextIdeAction", label: `Run Next: ${deriveNextIdeAction(artifacts).label}`, kind: "primary" },
      { command: "dogma.openCurrentQurationGraph", label: "Open Current Graph", kind: "primary" },
      { command: "dogma.generateQurationEdgeWorkPackage", label: "Edge Work Package" },
      { command: "dogma.checkIdeReadiness", label: "Check IDE Readiness" }
    ])}
  </div>`;
}

function renderSidecarHtml(state = {}) {
  const issues = state.issues || [];
  const context = state.context || {};
  const activeEditor = state.activeEditor || null;
  const artifacts = state.artifacts || {};
  const scanSource = state.scanSource || context.scanSource || "not scanned";
  const counts = countBySeverity(issues);
  const status = statusFor(issues, scanSource, context);

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {
      margin: 0;
      padding: 0;
      color: var(--vscode-foreground);
      background: var(--vscode-sideBar-background);
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
    }
    .shell { padding: 12px; }
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 12px;
    }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: 15px; line-height: 1.2; }
    h2 {
      margin: 16px 0 8px;
      color: var(--vscode-descriptionForeground);
      font-size: 11px;
      letter-spacing: 0;
      text-transform: uppercase;
    }
    h3 {
      margin: 12px 0 8px;
      color: var(--vscode-descriptionForeground);
      font-size: 11px;
      letter-spacing: 0;
      text-transform: uppercase;
    }
    .pill {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 999px;
      padding: 3px 8px;
      font-size: 11px;
      white-space: nowrap;
    }
    .pill.ready { color: var(--vscode-testing-iconPassed); }
    .pill.review { color: var(--vscode-testing-iconQueued); }
    .pill.blocked { color: var(--vscode-testing-iconFailed); }
    .pill.waiting { color: var(--vscode-descriptionForeground); }
    .metrics {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin-bottom: 10px;
    }
    .metric, .empty-state, .finding, .context, .action-group, .bio-card {
      border: 1px solid var(--vscode-panel-border);
      border-radius: 6px;
      background: var(--vscode-editor-background);
    }
    .metric { padding: 8px; min-width: 0; }
    .metric strong { display: block; font-size: 15px; }
    .metric span, .muted {
      color: var(--vscode-descriptionForeground);
      font-size: 11px;
    }
    .action-group {
      display: grid;
      grid-template-columns: 1fr;
      gap: 6px;
      padding: 8px;
    }
    .bio-state {
      display: grid;
      grid-template-columns: 1fr;
      gap: 7px;
    }
    .bio-card {
      padding: 8px;
      min-width: 0;
    }
    .bio-card span {
      display: block;
      color: var(--vscode-descriptionForeground);
      font-size: 11px;
      margin-bottom: 3px;
    }
    .bio-card strong {
      display: block;
      font-size: 13px;
      margin-bottom: 3px;
      overflow-wrap: anywhere;
    }
    .bio-card p {
      color: var(--vscode-descriptionForeground);
      font-size: 11px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }
    button {
      width: 100%;
      min-height: 30px;
      border: 0;
      border-radius: 5px;
      padding: 6px 8px;
      color: var(--vscode-button-secondaryForeground);
      background: var(--vscode-button-secondaryBackground);
      cursor: pointer;
      text-align: left;
    }
    button.primary {
      color: var(--vscode-button-foreground);
      background: var(--vscode-button-background);
      text-align: center;
      font-weight: 600;
    }
    button.inline {
      width: auto;
      min-height: 24px;
      padding: 4px 8px;
      text-align: center;
      font-size: 11px;
    }
    button:hover { background: var(--vscode-button-hoverBackground); color: var(--vscode-button-foreground); }
    .context { padding: 8px 10px; }
    .context-row {
      display: grid;
      grid-template-columns: 82px minmax(0, 1fr);
      gap: 8px;
      padding: 5px 0;
      border-bottom: 1px solid var(--vscode-panel-border);
    }
    .context-row:last-child { border-bottom: 0; }
    dt { color: var(--vscode-descriptionForeground); }
    dd { margin: 0; overflow-wrap: anywhere; }
    .active-actions {
      display: grid;
      grid-template-columns: 1fr;
      gap: 6px;
      margin-top: 8px;
    }
    .finding {
      padding: 9px;
      margin-bottom: 8px;
    }
    .finding div {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 4px;
      color: var(--vscode-descriptionForeground);
      font-size: 11px;
    }
    .finding .finding-actions {
      justify-content: flex-start;
      margin: 7px 0 0;
    }
    .finding p { line-height: 1.35; }
    .finding.error { border-left: 3px solid var(--vscode-testing-iconFailed); }
    .finding.warning { border-left: 3px solid var(--vscode-testing-iconQueued); }
    .active-file-findings { margin-top: 8px; }
    .empty-state {
      padding: 10px;
      color: var(--vscode-descriptionForeground);
      line-height: 1.35;
    }
    .footer {
      margin-top: 12px;
      color: var(--vscode-descriptionForeground);
      font-size: 11px;
      line-height: 1.35;
    }
  </style>
</head>
<body>
  <main class="shell">
    <div class="header">
      <div>
        <h1>Dogma</h1>
        <p class="muted">${escapeHtml(scanSource)}</p>
      </div>
      <span class="pill ${escapeHtml(status)}">${escapeHtml(status)}</span>
    </div>

    <section class="metrics" aria-label="Scan summary">
      ${renderMetric("issues", issues.length)}
      ${renderMetric("errors", counts.errors)}
      ${renderMetric("warnings", counts.warnings)}
    </section>

    ${renderActionGroup([
      { command: "dogma.prepareIdeSession", label: "Prepare IDE Session", kind: "primary" },
      { command: "dogma.checkIdeReadiness", label: "Check IDE Readiness" },
      { command: "dogma.scanWithLocalService", label: "Scan With Local Service" },
      { command: "dogma.reviewActiveFile", label: "Review Active File" },
      { command: "dogma.openAgentWorkbench", label: "Open Agent Workbench" },
      { command: "dogma.generateAgentHandoff", label: "Agent Handoff" },
      { command: "dogma.openBiologicalGraphWorkbench", label: "Local Biological Guardrails" },
      { command: "dogma.openAssistant", label: "Open Assistant" }
    ])}

    <h2>Active Investigation</h2>
    <section>${renderActiveInvestigation(artifacts)}</section>

    <h2>quration</h2>
    ${renderActionGroup([
      { command: "dogma.checkQurationStatus", label: "Check quration Status" },
      { command: "dogma.refreshQurationGraphHistory", label: "Refresh Graph History" },
      { command: "dogma.pullQurationGraphContext", label: "Pull Graph Context" },
      { command: "dogma.openCurrentQurationGraph", label: "Open Current Graph", kind: "primary" },
      { command: "dogma.pullQurationGraphEvents", label: "Pull Graph Events" },
      { command: "dogma.pullQurationFailedEvents", label: "Pull Failed Events" },
      { command: "dogma.selectQurationEdge", label: "Select quration Edge" },
      { command: "dogma.fetchQurationEdgePlan", label: "Fetch quration Edge Plan" },
      { command: "dogma.generateQurationEdgeEvaluationPlan", label: "quration Edge Plan" },
      { command: "dogma.generateQurationEdgeWorkPackage", label: "Edge Work Package", kind: "primary" },
      { command: "dogma.suggestFromQurationEdgeWorkPackage", label: "Suggest From Edge Package" },
      { command: "dogma.previewQurationEdgeSuggestedPatch", label: "Preview Edge Patch" },
      { command: "dogma.generateQurationEdgePatchHandoff", label: "Edge Patch Handoff" },
      { command: "dogma.resolveQurationSelectedEdgeReadout", label: "Resolve Edge Readout" },
      { command: "dogma.applyQurationEdgeSuggestedPatch", label: "Apply Edge Patch" },
      { command: "dogma.importWorkspaceToQuration", label: "Import To quration", kind: "primary" },
      { command: "dogma.openLastQurationImport", label: "Open Last Import" },
      { command: "dogma.openQurationCanvasFromWorkspace", label: "Open Canvas From Workspace" },
      { command: "dogma.generateQurationHandoff", label: "Generate Handoff" },
      { command: "dogma.openQurationGraphUi", label: "Open Graph UI" }
    ])}

    <h2>Guardrails</h2>
    ${renderActionGroup([
      { command: "dogma.generateMethodsGraphPreflight", label: "Methods-Graph Preflight", kind: "primary" },
      { command: "dogma.generateMethodGuardrails", label: "Method Guardrails" },
      { command: "dogma.generateMethodsGraphSubstrate", label: "Methods-Graph Substrate" },
      { command: "dogma.generateEvidenceLedger", label: "Evidence Ledger" },
      { command: "dogma.generateEdgeEvaluationPlan", label: "Edge Evaluation Plan" },
      { command: "dogma.checkLlmProvider", label: "Check LLM Provider" }
    ])}

    <h2>Local Service</h2>
    ${renderActionGroup([
      { command: "dogma.checkLocalService", label: "Check Local Service" },
      { command: "dogma.startLocalService", label: "Start Local Service" },
      { command: "dogma.checkWorkspaceTrust", label: "Check Workspace Trust" },
      { command: "dogma.trustWorkspaceForLocalOperations", label: "Trust Workspace For Local Operations" }
    ])}

    <h2>Bioinformatics State</h2>
    <section>${renderBioState(context)}</section>

    <h2>Active File</h2>
    <section>${renderActiveEditor(activeEditor, issues)}</section>

    <h2>Workspace Context</h2>
    <dl class="context">${renderContextRows(context)}</dl>

    <h2>Findings</h2>
    <section>${renderFindings(issues)}</section>

    <p class="footer">Sidecar state updates after scans. Graph and assistant commands open richer editor-side webviews.</p>
  </main>
  <script>
    const vscode = acquireVsCodeApi();
    function payloadFor(button) {
      if (!button.dataset.payload) return undefined;
      try {
        return JSON.parse(button.dataset.payload);
      } catch (error) {
        return undefined;
      }
    }
    document.querySelectorAll("button[data-command]").forEach((button) => {
      button.addEventListener("click", () => {
        const message = { command: button.dataset.command };
        const payload = payloadFor(button);
        if (payload !== undefined) {
          message.payload = payload;
        }
        vscode.postMessage(message);
      });
    });
  </script>
</body>
</html>`;
}

module.exports = {
  renderSidecarHtml
};
