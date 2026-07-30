"use strict";

/**
 * Pure path resolution for the `app://` protocol handler and the Python
 * interpreter lookup. Everything here is side-effect free: filesystem probes
 * are injected so the logic can be unit tested without touching disk.
 */

const path = require("node:path");

/** Extensions that must never fall back to index.html. */
const ASSET_EXTENSIONS = new Set([
  ".js",
  ".mjs",
  ".cjs",
  ".css",
  ".map",
  ".json",
  ".png",
  ".jpg",
  ".jpeg",
  ".gif",
  ".svg",
  ".webp",
  ".avif",
  ".ico",
  ".woff",
  ".woff2",
  ".ttf",
  ".otf",
  ".eot",
  ".wasm",
  ".txt",
  ".webmanifest",
]);

/**
 * Decide what to serve for one `app://` request.
 *
 * A missing *asset* is a 404 rather than an index.html fallback: handing HTML
 * back for a `.js` request produces a MIME error that hides the real cause.
 * A missing *route* (no asset extension) is the SPA fallback, which is what
 * lets react-router's BrowserRouter work under a custom scheme.
 *
 * @param {string} buildDir Absolute path to the Vite build output.
 * @param {string} requestUrl Full request URL, e.g. "app://dogma/datasets".
 * @param {(p: string) => boolean} fileExists Injected filesystem probe.
 * @returns {{kind: "file"|"fallback"|"denied"|"notFound"|"badRequest", filePath?: string}}
 */
function resolveRequest(buildDir, requestUrl, fileExists) {
  let pathname;
  try {
    pathname = new URL(requestUrl).pathname;
  } catch {
    return { kind: "badRequest" };
  }

  let decoded;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    // Malformed percent-encoding, e.g. "%zz".
    return { kind: "badRequest" };
  }

  // A NUL byte can truncate the path inside native filesystem calls.
  if (decoded.includes("\0")) {
    return { kind: "denied" };
  }

  const indexHtml = path.join(buildDir, "index.html");

  if (decoded === "/" || decoded === "") {
    return { kind: "fallback", filePath: indexHtml };
  }

  const candidate = path.resolve(buildDir, "." + decoded);
  const relative = path.relative(buildDir, candidate);
  const escapes =
    relative === "" ||
    relative.startsWith("..") ||
    path.isAbsolute(relative);
  if (escapes) {
    return { kind: "denied" };
  }

  if (fileExists(candidate)) {
    return { kind: "file", filePath: candidate };
  }

  const ext = path.extname(candidate).toLowerCase();
  if (ASSET_EXTENSIONS.has(ext)) {
    return { kind: "notFound" };
  }

  return { kind: "fallback", filePath: indexHtml };
}

/**
 * Path to the Python interpreter inside the repo's virtualenv.
 *
 * @param {string} repoRoot Absolute path to the monorepo root.
 * @param {string} [platform] process.platform value; injectable for tests.
 * @returns {string}
 */
function resolvePythonPath(repoRoot, platform = process.platform) {
  if (platform === "win32") {
    return path.join(repoRoot, ".venv", "Scripts", "python.exe");
  }
  return path.join(repoRoot, ".venv", "bin", "python");
}

module.exports = { ASSET_EXTENSIONS, resolveRequest, resolvePythonPath };
