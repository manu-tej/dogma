"use strict";

function stepResult(step = {}) {
  return step.ok ? (step.result || {}) : {};
}

function messageFor(step = {}, fallback = "not reported") {
  if (!step.ok) return step.error || "request failed";
  const result = step.result || {};
  return result.message || result.status || result.root || fallback;
}

function localServiceGate(step = {}) {
  const result = stepResult(step);
  return {
    id: "local_service",
    label: "Local service",
    state: step.ok ? "ready" : "blocked",
    detail: step.ok ? `${result.status || "reachable"} at ${result.url || "configured service URL"}` : messageFor(step)
  };
}

function trustGate(step = {}) {
  const trust = stepResult(step).trust || {};
  if (!step.ok) {
    return { id: "workspace_trust", label: "Workspace trust", state: "unknown", detail: messageFor(step) };
  }
  const blocked = trust.trusted === false;
  return {
    id: "workspace_trust",
    label: "Workspace trust",
    state: blocked ? "blocked" : "ready",
    detail: `${trust.status || "unknown"}${trust.human_data ? "; human data detected" : ""}`
  };
}

function llmGate(step = {}) {
  const result = stepResult(step);
  if (!step.ok) {
    return { id: "llm_provider", label: "Claude provider", state: "unknown", detail: messageFor(step) };
  }
  const status = String(result.status || "unknown");
  const provider = result.provider || "none";
  const readyStatuses = new Set(["ready", "configured", "available", "ok", "llm_ready", "claude_ready"]);
  const disabled = provider === "none" || status === "not_configured";
  return {
    id: "llm_provider",
    label: "Claude provider",
    state: disabled ? "warning" : readyStatuses.has(status) ? "ready" : "warning",
    detail: disabled ? "agent LLM disabled or not configured" : `${provider}: ${status}`
  };
}

function methodsGraphGate(step = {}) {
  const result = stepResult(step);
  if (!step.ok) {
    return { id: "methods_graph", label: "methods-graph", state: "unknown", detail: messageFor(step) };
  }
  const status = String(result.status || "unknown");
  const readyStatuses = new Set(["evaluable", "ready", "pass"]);
  const blockedStatuses = new Set(["blocked", "not_evaluable"]);
  return {
    id: "methods_graph",
    label: "methods-graph",
    state: readyStatuses.has(status) ? "ready" : blockedStatuses.has(status) ? "blocked" : "warning",
    detail: `${status}; substrate ${result.substrate_status || result.methods_graph_status || "unknown"}`
  };
}

function qurationGate(step = {}) {
  const result = stepResult(step);
  if (!step.ok) {
    return { id: "quration", label: "quration bridge", state: "unknown", detail: messageFor(step) };
  }
  const graphReady = result.graph_api?.ready;
  const graphDetail = graphReady === undefined ? "" : `; graph API ready: ${graphReady ? "yes" : "no"}`;
  return {
    id: "quration",
    label: "quration bridge",
    state: result.import_ready ? "ready" : "warning",
    detail: `${result.status || "unknown"}; import ready: ${result.import_ready ? "yes" : "no"}${graphDetail}`
  };
}

function overallStatus(gates) {
  if (gates.some((gate) => gate.state === "blocked")) return "blocked";
  if (gates.some((gate) => gate.state === "warning" || gate.state === "unknown")) return "degraded";
  return "ready";
}

function nextActions(gates) {
  const byId = Object.fromEntries(gates.map((gate) => [gate.id, gate]));
  const actions = [];
  if (byId.local_service?.state === "blocked") actions.push("Start the Dogma local service before running IDE agent, trust, patch, or methods-graph checks.");
  if (byId.workspace_trust?.state === "blocked") actions.push("Run `Dogma: Check Workspace Trust` and explicitly trust the workspace before local operations on human data.");
  if (byId.llm_provider?.state === "warning") actions.push("Run `Dogma: Check LLM Provider`; log in to Claude Code or set `dogma.agentProvider` to `none` for prompt-only mode.");
  if (byId.methods_graph?.state === "warning" || byId.methods_graph?.state === "unknown") actions.push("Run `Dogma: Generate Methods-Graph Preflight` and resolve reported substrate or coverage gaps before treating methods as grounded.");
  if (byId.quration?.state === "warning" || byId.quration?.state === "unknown") actions.push("Run `Dogma: Check quration Status`; start quration backend/frontend before importing the workspace graph.");
  if (!actions.length) actions.push("Use `Dogma: Open Agent Workbench`, `Dogma: Generate quration Handoff`, or `Dogma: Import Workspace To quration` for the next IDE step.");
  return actions;
}

function buildIdeReadinessReport(input = {}) {
  const gates = [
    localServiceGate(input.localService),
    trustGate(input.trust),
    llmGate(input.llmProvider),
    methodsGraphGate(input.methodsGraph),
    qurationGate(input.quration)
  ];
  return {
    contract_version: "dogma-ide-readiness.v1",
    checked_at: input.checkedAt || new Date().toISOString(),
    status: overallStatus(gates),
    gates,
    settings: input.settings || {},
    next_actions: nextActions(gates)
  };
}

function renderIdeReadiness(report = {}) {
  const gates = report.gates || [];
  const rows = gates.length
    ? gates.map((gate) => `| ${gate.label || gate.id} | ${gate.state || "unknown"} | ${gate.detail || "not reported"} |`)
    : ["| none | unknown | no gates reported |"];
  const actions = report.next_actions?.length ? report.next_actions.map((item) => `- ${item}`) : ["- Run `Dogma: Scan With Local Service`."];
  const settings = report.settings || {};
  return [
    "# Dogma IDE Readiness",
    "",
    "This report checks whether the VS Code/Cursor IDE layer is ready to act locally while keeping quration as the canonical graph web UI.",
    "",
    `- Status: ${report.status || "unknown"}`,
    `- Checked: ${report.checked_at || "unknown"}`,
    "",
    "## Gates",
    "",
    "| Gate | State | Detail |",
    "| --- | --- | --- |",
    ...rows,
    "",
    "## Settings",
    "",
    `- Local service: ${settings.service_url || "not configured"}`,
    `- quration canvas: ${settings.quration_canvas_url || "not configured"}`,
    `- quration API: ${settings.quration_api_url || "not configured"}`,
    `- Agent provider: ${settings.agent_provider || "not configured"}`,
    "",
    "## Next Actions",
    "",
    ...actions,
    ""
  ].join("\n");
}

module.exports = {
  buildIdeReadinessReport,
  renderIdeReadiness
};
