"use strict";

function yesNo(value) {
  return value ? "yes" : "no";
}

function renderQurationConnectionStatus(result = {}) {
  const backend = result.backend || {};
  const canvas = result.canvas || {};
  const graphApi = result.graph_api || {};
  const capabilities = Array.isArray(graphApi.capabilities) ? graphApi.capabilities : [];
  const requiredRows = capabilities
    .filter((capability) => capability.required)
    .map((capability) => `| ${capability.label || capability.id} | ${capability.method?.toUpperCase() || "GET"} ${capability.path || "unknown"} | ${capability.available ? "yes" : "no"} |`);
  const optionalRows = capabilities
    .filter((capability) => !capability.required)
    .map((capability) => `| ${capability.label || capability.id} | ${capability.method?.toUpperCase() || "GET"} ${capability.path || "unknown"} | ${capability.available ? "yes" : "no"} |`);
  const settings = result.settings || {};
  const lines = [
    "# Dogma quration Status",
    "",
    `- Status: ${result.status || "unknown"}`,
    `- Import ready: ${yesNo(result.import_ready)}`,
    `- Checked: ${result.checked_at || "unknown"}`,
    "",
    "## Backend API",
    "",
    `- URL: ${backend.url || settings.quration_api_url || "not configured"}`,
    `- Reachable: ${yesNo(backend.reachable)}`,
    `- Health: ${backend.healthy === null || backend.healthy === undefined ? "unknown" : yesNo(backend.healthy)}`,
    `- Status: ${backend.status || "unknown"}`,
    `- Message: ${backend.message || "none"}`,
    "",
    "## Canvas",
    "",
    `- URL: ${canvas.url || settings.quration_canvas_url || "not configured"}`,
    `- Reachable: ${yesNo(canvas.reachable)}`,
    `- HTTP status: ${canvas.status_code || "unknown"}`,
    `- Content type: ${canvas.content_type || "unknown"}`,
    `- Message: ${canvas.message || "none"}`,
    "",
    "## Graph API Contract",
    "",
    `- URL: ${graphApi.url || "not configured"}`,
    `- Reachable: ${yesNo(graphApi.reachable)}`,
    `- Ready: ${yesNo(graphApi.ready)}`,
    `- Status: ${graphApi.status || "unknown"}`,
    `- Message: ${graphApi.message || "none"}`,
    "",
    "| Required capability | Endpoint | Available |",
    "| --- | --- | --- |",
    ...(requiredRows.length ? requiredRows : ["| none | unknown | no |"]),
    "",
    "| Optional capability | Endpoint | Available |",
    "| --- | --- | --- |",
    ...(optionalRows.length ? optionalRows : ["| none | unknown | no |"]),
    "",
    "## Settings",
    "",
    `- dogma.qurationApiUrl: ${settings.quration_api_url || "not configured"}`,
    `- dogma.qurationUrl: ${settings.quration_canvas_url || "not configured"}`,
    `- dogma.qurationTimeoutMs: ${settings.timeout_ms || "not configured"}`,
    `- Graph contract: ${settings.graph_contract || "not configured"}`,
    "",
    "## Next Actions",
    ""
  ];

  if (result.import_ready) {
    lines.push("- Run `Dogma: Import Workspace To quration` to persist the current Dogma graph in quration.");
    lines.push("- Run `Dogma: Open Last quration Import` after a successful import to return to the saved graph.");
  } else {
    if (!backend.reachable) {
      lines.push("- Start quration's backend on `dogma.qurationApiUrl` before importing.");
    }
    if (!canvas.reachable) {
      lines.push("- Start quration's frontend on `dogma.qurationUrl` before opening imported graphs.");
    }
    if (!graphApi.ready) {
      lines.push("- Update quration or point `dogma.qurationApiUrl` at a backend exposing the required `/hypothesis` graph contract.");
    }
  }

  lines.push("");
  return lines.join("\n");
}

module.exports = {
  renderQurationConnectionStatus
};
