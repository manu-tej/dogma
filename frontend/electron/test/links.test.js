"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");

const { classifyUrl, originOf } = require("../lib/links");
const { APP_ORIGIN, DEV_SERVER_URL } = require("../lib/config");

const INTERNAL = [APP_ORIGIN, DEV_SERVER_URL];

describe("originOf", () => {
  it("derives a tuple origin for a custom scheme", () => {
    // Regression guard: URL.prototype.origin is the string "null" here on Node,
    // which previously made every in-app navigation look external and get
    // blocked in the packaged app.
    assert.equal(new URL(`${APP_ORIGIN}/datasets`).origin, "null");
    assert.equal(originOf(new URL(`${APP_ORIGIN}/datasets`)), APP_ORIGIN);
  });

  it("matches the standard origin for http URLs", () => {
    const url = new URL(`${DEV_SERVER_URL}/canvas`);
    assert.equal(originOf(url), url.origin);
  });
});

describe("classifyUrl", () => {
  it("treats in-app origins as internal", () => {
    assert.equal(classifyUrl(`${APP_ORIGIN}/datasets`, INTERNAL), "internal");
    assert.equal(classifyUrl(`${DEV_SERVER_URL}/canvas`, INTERNAL), "internal");
  });

  it("treats other web origins as external", () => {
    assert.equal(classifyUrl("https://www.ncbi.nlm.nih.gov/geo/", INTERNAL), "external");
    assert.equal(classifyUrl("http://example.test/docs", INTERNAL), "external");
  });

  it("does not confuse a lookalike origin for an internal one", () => {
    assert.equal(classifyUrl("http://localhost:3001/", INTERNAL), "external");
    assert.equal(classifyUrl("app://evil/index.html", INTERNAL), "blocked");
  });

  it("blocks non-web schemes", () => {
    for (const blocked of [
      "file:///etc/passwd",
      "javascript:alert(1)",
      "data:text/html,<h1>x</h1>",
      "vscode://open",
      "chrome://settings",
    ]) {
      assert.equal(classifyUrl(blocked, INTERNAL), "blocked", `expected blocked for ${blocked}`);
    }
  });

  it("blocks anything unparseable", () => {
    assert.equal(classifyUrl("", INTERNAL), "blocked");
    assert.equal(classifyUrl("://nope", INTERNAL), "blocked");
  });
});
