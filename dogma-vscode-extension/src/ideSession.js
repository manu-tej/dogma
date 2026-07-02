"use strict";

function issueCounts(issues = []) {
  const list = Array.isArray(issues) ? issues : [];
  return {
    total: list.length,
    errors: list.filter((item) => item.severity === "error").length,
    warnings: list.filter((item) => item.severity === "warning").length
  };
}

function statusFrom({ service = {}, scan = {}, readiness = {} } = {}) {
  if (service.ready === false || scan.completed === false) return "blocked";
  if (readiness.status) return readiness.status;
  return "degraded";
}

function sessionActions(report = {}) {
  const actions = [];
  const counts = report.scan?.issue_counts || {};

  if (report.service?.ready === false) {
    actions.push("Start the Dogma local service before using local scan, trust, patch, or agent commands.");
  }
  if (counts.errors > 0) {
    actions.push("Resolve error-level Dogma scan findings before generating or applying workflow edits.");
  }
  if (report.readiness?.status === "blocked") {
    actions.push("Open `.dogma/ide-readiness.md` and clear blocked gates before treating the IDE session as actionable.");
  } else if (report.readiness?.status === "degraded") {
    actions.push("Review `.dogma/ide-readiness.md` warnings before handing the workspace graph to quration.");
  }

  actions.push("Use quration as the graph web UI; Dogma should import, open, or deep-link workspace graphs rather than duplicate the canvas.");
  return actions;
}

function buildIdeSessionReport(input = {}) {
  const scan = input.scan || {};
  const readiness = input.readiness || {};
  const service = input.service || {};
  const report = {
    contract_version: "dogma-ide-session.v1",
    prepared_at: input.preparedAt || new Date().toISOString(),
    status: statusFrom({ service, scan, readiness }),
    architecture: {
      ide_surface: "VS Code/Cursor extension",
      graph_surface: "quration web UI",
      guardrail_surface: "methods-graph-backed Dogma local service"
    },
    service: {
      ready: service.ready !== false,
      url: service.url || null,
      status: service.status || "unknown",
      already_reachable: Boolean(service.already_reachable),
      started_by_extension: Boolean(service.started_by_extension),
      already_running: Boolean(service.already_running)
    },
    scan: {
      completed: scan.completed !== false,
      source: scan.source || "local service",
      issue_counts: issueCounts(scan.issues)
    },
    readiness: {
      status: readiness.status || "unknown",
      artifact: ".dogma/ide-readiness.md",
      gates: Array.isArray(readiness.gates) ? readiness.gates : []
    },
    artifacts: {
      session_json: ".dogma/ide-session.json",
      session_markdown: ".dogma/ide-session.md",
      readiness_json: ".dogma/ide-readiness.json",
      readiness_markdown: ".dogma/ide-readiness.md"
    }
  };
  report.next_actions = sessionActions(report);
  return report;
}

function renderIdeSession(report = {}) {
  const service = report.service || {};
  const scan = report.scan || {};
  const counts = scan.issue_counts || {};
  const readiness = report.readiness || {};
  const gates = readiness.gates || [];
  const gateRows = gates.length
    ? gates.map((gate) => `| ${gate.label || gate.id} | ${gate.state || "unknown"} | ${gate.detail || "not reported"} |`)
    : ["| none | unknown | no readiness gates reported |"];
  const actions = report.next_actions?.length ? report.next_actions.map((item) => `- ${item}`) : ["- Run `Dogma: Check IDE Readiness`."];

  return [
    "# Dogma IDE Session",
    "",
    "Dogma prepares the VS Code/Cursor extension session. quration remains the graph-native web UI, and methods-graph remains the guardrail substrate.",
    "",
    `- Status: ${report.status || "unknown"}`,
    `- Prepared: ${report.prepared_at || "unknown"}`,
    "",
    "## Boundaries",
    "",
    `- IDE surface: ${report.architecture?.ide_surface || "VS Code/Cursor extension"}`,
    `- Graph surface: ${report.architecture?.graph_surface || "quration web UI"}`,
    `- Guardrails: ${report.architecture?.guardrail_surface || "methods-graph-backed Dogma local service"}`,
    "",
    "## Local Service",
    "",
    `- URL: ${service.url || "not configured"}`,
    `- Status: ${service.status || "unknown"}`,
    `- Already reachable: ${service.already_reachable ? "yes" : "no"}`,
    `- Started by extension: ${service.started_by_extension ? "yes" : "no"}`,
    "",
    "## Scan",
    "",
    `- Completed: ${scan.completed === false ? "no" : "yes"}`,
    `- Source: ${scan.source || "unknown"}`,
    `- Issues: ${counts.total || 0} total, ${counts.errors || 0} errors, ${counts.warnings || 0} warnings`,
    "",
    "## Readiness Gates",
    "",
    `- Readiness status: ${readiness.status || "unknown"}`,
    `- Artifact: ${readiness.artifact || ".dogma/ide-readiness.md"}`,
    "",
    "| Gate | State | Detail |",
    "| --- | --- | --- |",
    ...gateRows,
    "",
    "## Next Actions",
    "",
    ...actions,
    ""
  ].join("\n");
}

module.exports = {
  buildIdeSessionReport,
  renderIdeSession
};
