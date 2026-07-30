"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");
const { describe, it } = require("node:test");

const { resolveRequest, resolvePythonPath } = require("../lib/paths");

const BUILD = "/repo/frontend/build";
const url = (p) => `app://dogma${p}`;

/** Pretend only the files a real Vite build emits exist. */
const existing = new Set([
  path.join(BUILD, "index.html"),
  path.join(BUILD, "assets", "index-abc123.js"),
  path.join(BUILD, "assets", "index-abc123.css"),
]);
const fileExists = (p) => existing.has(p);

describe("resolveRequest", () => {
  it("serves index.html for the root", () => {
    const result = resolveRequest(BUILD, url("/"), fileExists);
    assert.equal(result.kind, "fallback");
    assert.equal(result.filePath, path.join(BUILD, "index.html"));
  });

  it("serves a real asset directly", () => {
    const result = resolveRequest(BUILD, url("/assets/index-abc123.js"), fileExists);
    assert.equal(result.kind, "file");
    assert.equal(result.filePath, path.join(BUILD, "assets", "index-abc123.js"));
  });

  it("falls back to index.html for client-side routes", () => {
    // This is the behaviour that lets BrowserRouter work under app://.
    for (const route of ["/datasets", "/pipelines", "/canvas/nested/deep"]) {
      const result = resolveRequest(BUILD, url(route), fileExists);
      assert.equal(result.kind, "fallback", `expected fallback for ${route}`);
      assert.equal(result.filePath, path.join(BUILD, "index.html"));
    }
  });

  it("404s a missing asset instead of returning HTML", () => {
    // Returning index.html here would surface as an opaque MIME type error
    // rather than the actual missing-file problem.
    for (const missing of [
      "/assets/gone.js",
      "/assets/gone.css",
      "/favicon.ico",
      "/chunk.mjs",
      "/sourcemap.map",
    ]) {
      const result = resolveRequest(BUILD, url(missing), fileExists);
      assert.equal(result.kind, "notFound", `expected notFound for ${missing}`);
    }
  });

  it("never resolves a path outside the build directory", () => {
    // Two mechanisms combine here, so this asserts the property rather than one
    // outcome. The WHATWG URL parser already collapses literal ".." and bare
    // "%2e%2e" segments before the handler sees them; an encoded slash
    // ("%2e%2e%2f") survives that normalisation as one opaque segment and is
    // what the explicit path.relative guard exists to catch. Either way, no
    // request may ever name a file outside the build output.
    const attacks = [
      "/../../secrets.txt",
      "/../package.json",
      "/../../../../../../etc/passwd",
      "/assets/../../../etc/passwd",
      "/%2e%2e%2f%2e%2e%2fsecrets.txt",
      "/%2e%2e/%2e%2e/x.txt",
      "/assets/%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
      "/..%2f..%2fsecrets.txt",
    ];

    // Claim every file exists, so a traversal that got through would be
    // reported as a servable "file" rather than hidden behind a 404.
    const allExist = () => true;

    for (const attack of attacks) {
      const result = resolveRequest(BUILD, url(attack), allExist);
      assert.notEqual(result.kind, "badRequest", `unexpected parse failure for ${attack}`);
      if (result.filePath !== undefined) {
        const relative = path.relative(BUILD, result.filePath);
        assert.ok(
          relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative)),
          `${attack} escaped the build dir as ${result.filePath}`,
        );
      }
    }
  });

  it("denies an encoded-slash traversal explicitly", () => {
    // This input bypasses URL dot-segment normalisation, so it is the case that
    // actually exercises the guard rather than the parser.
    const result = resolveRequest(BUILD, url("/%2e%2e%2f%2e%2e%2fsecrets.txt"), () => true);
    assert.equal(result.kind, "denied");
  });

  it("denies a path containing a NUL byte", () => {
    const result = resolveRequest(BUILD, url("/assets/x%00.js"), fileExists);
    assert.equal(result.kind, "denied");
  });

  it("rejects malformed percent-encoding", () => {
    const result = resolveRequest(BUILD, url("/%zz"), fileExists);
    assert.equal(result.kind, "badRequest");
  });

  it("rejects an unparseable URL", () => {
    assert.equal(resolveRequest(BUILD, "not a url", fileExists).kind, "badRequest");
  });

  it("decodes percent-encoded filenames", () => {
    const spaced = path.join(BUILD, "assets", "my file.js");
    const result = resolveRequest(BUILD, url("/assets/my%20file.js"), (p) => p === spaced);
    assert.equal(result.kind, "file");
    assert.equal(result.filePath, spaced);
  });
});

describe("resolvePythonPath", () => {
  it("uses the posix venv layout", () => {
    assert.equal(
      resolvePythonPath("/repo", "darwin"),
      path.join("/repo", ".venv", "bin", "python"),
    );
    assert.equal(
      resolvePythonPath("/repo", "linux"),
      path.join("/repo", ".venv", "bin", "python"),
    );
  });

  it("uses the Scripts layout on Windows", () => {
    assert.equal(
      resolvePythonPath("/repo", "win32"),
      path.join("/repo", ".venv", "Scripts", "python.exe"),
    );
  });
});
