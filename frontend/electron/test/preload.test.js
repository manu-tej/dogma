"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { describe, it } = require("node:test");

const { CONFIG_ARG_PREFIX } = require("../lib/config");

const PRELOAD_PATH = path.join(__dirname, "..", "preload.js");
const source = fs.readFileSync(PRELOAD_PATH, "utf8");

describe("preload.js", () => {
  it("requires no relative modules", () => {
    // A sandboxed preload gets `electron` plus a polyfilled subset of Node
    // built-ins and nothing else. Requiring a sibling file fails at runtime
    // with "module not found", which silently costs the renderer its bridge.
    const relativeRequires = source.match(/require\(\s*['"]\.[^'"]*['"]\s*\)/g);
    assert.equal(
      relativeRequires,
      null,
      `preload must be self-contained, found: ${relativeRequires?.join(", ")}`,
    );
  });

  it("only requires electron", () => {
    const specifiers = [...source.matchAll(/require\(\s*['"]([^'"]+)['"]\s*\)/g)].map(
      (match) => match[1],
    );
    assert.deepEqual(specifiers, ["electron"]);
  });

  it("keeps its duplicated config prefix in sync with lib/config", () => {
    // The duplication is deliberate (see the note in preload.js); this is the
    // check that keeps it honest.
    assert.ok(
      source.includes(`"${CONFIG_ARG_PREFIX}"`),
      `preload.js must contain the literal ${CONFIG_ARG_PREFIX}`,
    );
  });

  it("exposes the bridge through contextBridge rather than assigning a global", () => {
    assert.match(source, /contextBridge\.exposeInMainWorld\(\s*"dogma"/);
    assert.doesNotMatch(source, /window\.dogma\s*=/);
  });
});
