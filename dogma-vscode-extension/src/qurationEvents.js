"use strict";

function cleanText(value, fallback = "") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function safeCell(value, fallback = "") {
  return cleanText(value, fallback).replace(/\|/g, "\\|").replace(/\s+/g, " ");
}

function compactJson(value) {
  if (!value || typeof value !== "object") return "";
  try {
    return JSON.stringify(value);
  } catch {
    return "";
  }
}

function eventRows(events = []) {
  if (!Array.isArray(events) || !events.length) {
    return ["| none | unknown | unknown | unknown | not available | none |"];
  }
  return events.map((event) => [
    `| ${safeCell(event.ts || event.rank, "unknown")}`,
    safeCell(event.op, "unknown"),
    safeCell(event.status, "unknown"),
    event.latency_ms === null || event.latency_ms === undefined ? "unknown" : safeCell(event.latency_ms),
    safeCell(compactJson(event.detail), "not available"),
    safeCell(event.error, "none")
  ].join(" | ") + " |");
}

function summaryLines(summary = {}) {
  const statuses = summary.statuses || {};
  const operations = summary.operations || {};
  return [
    `- Events: ${summary.total ?? 0}`,
    `- Failed: ${summary.failed ?? 0}`,
    `- Events with raw IO: ${summary.with_raw_io ?? 0}`,
    `- Statuses: ${Object.keys(statuses).length ? Object.entries(statuses).map(([key, value]) => `${key}: ${value}`).join(", ") : "none"}`,
    `- Operations: ${Object.keys(operations).length ? Object.entries(operations).map(([key, value]) => `${key}: ${value}`).join(", ") : "none"}`
  ];
}

function renderQurationEvents(record = {}) {
  const isFailedFeed = record.scope === "failed" || record.contract_version === "dogma-quration-failed-events.v1";
  const title = isFailedFeed ? "# Dogma quration Failed Events" : "# Dogma quration Graph Events";
  const settings = record.settings || {};

  const target = isFailedFeed
    ? [
        "## Failed Event Feed",
        "",
        `- Limit: ${record.limit ?? "unknown"}`,
        `- Endpoint: ${record.endpoints?.failed_events || "not recorded"}`
      ]
    : [
        "## quration Graph",
        "",
        `- Graph ID: ${cleanText(record.graph_id, "unknown")}`,
        `- Graph URL: ${cleanText(record.graph_url, "not available")}`,
        `- Query: ${cleanText(record.query, "not recorded")}`,
        `- Endpoint: ${record.endpoints?.graph_events || "not recorded"}`
      ];

  return [
    title,
    "",
    "Dogma pulled this quration event trail for IDE context only. quration remains the canonical graph, evidence, and event-history surface; this artifact is read-only and does not mutate quration.",
    "",
    ...target,
    "",
    "## Summary",
    "",
    `- Status: ${cleanText(record.status, "unknown")}`,
    `- Fetched: ${cleanText(record.fetched_at, "unknown")}`,
    ...summaryLines(record.summary || {}),
    "",
    "## Events",
    "",
    "| Time | Operation | Status | Latency ms | Detail | Error |",
    "| --- | --- | --- | --- | --- | --- |",
    ...eventRows(record.events),
    "",
    "## Boundary",
    "",
    "- Use quration to inspect full event history, graph edits, evidence records, and raw event trails.",
    "- Use Dogma to connect event context to local files, guardrails, patches, and IDE work packages.",
    "- Do not treat an event trail as biological support/refute evidence.",
    "",
    "## Settings",
    "",
    `- quration API: ${settings.quration_api_url || "not configured"}`,
    `- quration canvas: ${settings.quration_canvas_url || "not configured"}`,
    `- Contract: ${settings.graph_contract || "unknown"}`,
    ""
  ].join("\n");
}

module.exports = {
  renderQurationEvents
};
