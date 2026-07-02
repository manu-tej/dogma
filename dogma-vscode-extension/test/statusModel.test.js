"use strict";

const assert = require("assert");
const {
  countIssues,
  idleStatus,
  scanningStatus,
  serviceOfflineStatus,
  statusColorRole,
  statusFromScanResult,
  renderStatusText,
  renderStatusTooltip
} = require("../src/statusModel");

assert.deepStrictEqual(
  countIssues([
    { severity: "error" },
    { severity: "warning" },
    { severity: "warning" }
  ]),
  { total: 3, errors: 1, warnings: 2 }
);

const idle = idleStatus();
assert.strictEqual(renderStatusText(idle), "$(beaker) Dogma: idle");
assert.strictEqual(statusColorRole(idle), undefined);

const scanning = scanningStatus("background scan");
assert.strictEqual(renderStatusText(scanning), "$(sync~spin) Dogma: scanning");
assert(renderStatusTooltip(scanning).includes("Source: background scan"));

const ready = statusFromScanResult({ issues: [], source: "extension" });
assert.strictEqual(ready.kind, "ready");
assert.strictEqual(renderStatusText(ready), "$(check) Dogma: ready");
assert(renderStatusTooltip(ready).includes("0 total, 0 errors, 0 warnings"));

const review = statusFromScanResult({ issues: [{ severity: "warning" }, { severity: "warning" }], source: "local service" });
assert.strictEqual(review.kind, "review");
assert.strictEqual(renderStatusText(review), "$(warning) Dogma: review W2");
assert.strictEqual(statusColorRole(review), "warning");

const blocked = statusFromScanResult({ issues: [{ severity: "error" }, { severity: "warning" }], source: "local service" });
assert.strictEqual(blocked.kind, "blocked");
assert.strictEqual(renderStatusText(blocked), "$(error) Dogma: blocked E1 W1");
assert.strictEqual(statusColorRole(blocked), "error");

const offline = serviceOfflineStatus("Connection refused.");
assert.strictEqual(renderStatusText(offline), "$(debug-disconnect) Dogma: service offline");
assert.strictEqual(statusColorRole(offline), "error");
assert(renderStatusTooltip(offline).includes("Connection refused."));

console.log("Status model tests passed");
