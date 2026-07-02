"use strict";

function countIssues(issues = []) {
  return issues.reduce(
    (counts, issue) => {
      if (issue?.severity === "error") {
        counts.errors += 1;
      } else if (issue?.severity === "warning") {
        counts.warnings += 1;
      }
      counts.total += 1;
      return counts;
    },
    { total: 0, errors: 0, warnings: 0 }
  );
}

function idleStatus(message = "No workspace scan has run yet.") {
  return { kind: "idle", source: "not scanned", total: 0, errors: 0, warnings: 0, message };
}

function scanningStatus(source = "workspace") {
  return { kind: "scanning", source, total: 0, errors: 0, warnings: 0, message: "Scanning workspace." };
}

function serviceOfflineStatus(message, source = "local service") {
  return {
    kind: "service_offline",
    source,
    total: 0,
    errors: 0,
    warnings: 0,
    message: message || "Dogma local service is not reachable."
  };
}

function statusFromScanResult(result = {}) {
  const counts = countIssues(result.issues || []);
  const source = result.source || result.context?.scanSource || "workspace";
  let kind = "ready";
  if (counts.errors > 0) {
    kind = "blocked";
  } else if (counts.warnings > 0) {
    kind = "review";
  }

  return {
    kind,
    source,
    total: counts.total,
    errors: counts.errors,
    warnings: counts.warnings,
    message: result.message || ""
  };
}

function renderStatusText(status = idleStatus()) {
  if (status.kind === "scanning") {
    return "$(sync~spin) Dogma: scanning";
  }
  if (status.kind === "service_offline") {
    return "$(debug-disconnect) Dogma: service offline";
  }
  if (status.kind === "blocked") {
    return `$(error) Dogma: blocked E${status.errors} W${status.warnings}`;
  }
  if (status.kind === "review") {
    return `$(warning) Dogma: review W${status.warnings}`;
  }
  if (status.kind === "ready") {
    return "$(check) Dogma: ready";
  }
  return "$(beaker) Dogma: idle";
}

function renderStatusTooltip(status = idleStatus()) {
  const lines = ["Dogma workspace state"];
  if (status.source) {
    lines.push(`Source: ${status.source}`);
  }
  if (status.kind === "blocked" || status.kind === "review" || status.kind === "ready") {
    lines.push(`Issues: ${status.total} total, ${status.errors} errors, ${status.warnings} warnings`);
  }
  if (status.message) {
    lines.push(status.message);
  }
  lines.push("Click to scan the workspace.");
  return lines.join("\n");
}

function statusColorRole(status = idleStatus()) {
  if (status.kind === "blocked" || status.kind === "service_offline") {
    return "error";
  }
  if (status.kind === "review") {
    return "warning";
  }
  return undefined;
}

module.exports = {
  countIssues,
  idleStatus,
  scanningStatus,
  serviceOfflineStatus,
  statusColorRole,
  statusFromScanResult,
  renderStatusText,
  renderStatusTooltip
};
