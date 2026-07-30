"use strict";

/**
 * Finding the repository the desktop app depends on.
 *
 * Unpackaged, this is trivial: main.js lives at frontend/electron, so the root
 * is two levels up. Packaged, that derivation lands inside
 * Contents/Resources/app and is simply wrong.
 *
 * The app is deliberately not redistributable — it runs the backend out of this
 * repo's `.venv`, so it needs the real checkout on disk, not a copy inside the
 * bundle. Rather than branch on `app.isPackaged`, every candidate is *validated*
 * and the first plausible one wins. One ordering then serves both cases: the
 * derived path is correct and validates when unpackaged, and fails validation
 * when packaged, falling through to the path baked in at build time.
 *
 * Everything here is pure; the filesystem probe is injected.
 */

const path = require("node:path");

/** Environment variable that overrides every other source. */
const REPO_ROOT_ENV_VAR = "DOGMA_REPO_ROOT";

/**
 * Files that together identify a Dogma checkout.
 *
 * `pyproject.toml` is the important one: it is what makes this a Python repo
 * with a `.venv` to find, and it is never bundled into the app, which is why
 * the packaged derived path reliably fails this check instead of being
 * mistaken for a real root.
 */
const REPO_MARKERS = [
  ["pyproject.toml"],
  ["frontend", "package.json"],
];

/**
 * @param {string | null | undefined} dir
 * @param {(p: string) => boolean} fileExists
 * @returns {boolean}
 */
function looksLikeRepo(dir, fileExists) {
  if (typeof dir !== "string" || dir === "") return false;
  if (!path.isAbsolute(dir)) return false;
  return REPO_MARKERS.every((segments) =>
    fileExists(path.join(dir, ...segments)),
  );
}

/**
 * Resolve the repository root from every place it might be recorded.
 *
 * Order, most authoritative first:
 *   1. DOGMA_REPO_ROOT — an explicit override, so it is tried before anything
 *      inferred. Still validated: a stale value should fall through rather than
 *      send the backend launcher at a directory that no longer exists.
 *   2. derived — `__dirname/../..`. Correct when running from the checkout.
 *   3. baked — written into the bundle at package time by bake-repo-root.js.
 *   4. stored — a directory the user picked previously, persisted in userData.
 *
 * @param {object} sources
 * @param {string} [sources.envValue] Raw value of DOGMA_REPO_ROOT.
 * @param {string} [sources.derived]
 * @param {string} [sources.baked]
 * @param {string} [sources.stored]
 * @param {(p: string) => boolean} sources.fileExists
 * @returns {{root: string|null, source: string|null, tried: Array<{source: string, path: string, valid: boolean}>}}
 */
function resolveRepoRoot({ envValue, derived, baked, stored, fileExists }) {
  const candidates = [
    ["env", envValue],
    ["derived", derived],
    ["baked", baked],
    ["stored", stored],
  ];

  const tried = [];
  for (const [source, value] of candidates) {
    if (typeof value !== "string" || value.trim() === "") continue;
    const candidate = path.resolve(value.trim());
    const valid = looksLikeRepo(candidate, fileExists);
    tried.push({ source, path: candidate, valid });
    if (valid) {
      return { root: candidate, source, tried };
    }
  }

  return { root: null, source: null, tried };
}

/**
 * Human-readable account of what was tried, for the failure dialog. Without
 * this the user sees "repository not found" with no way to tell whether their
 * override was ignored or simply pointed somewhere wrong.
 *
 * @param {Array<{source: string, path: string, valid: boolean}>} tried
 * @returns {string}
 */
function describeAttempts(tried) {
  if (tried.length === 0) {
    return "No candidate locations were available to check.";
  }
  const labels = {
    env: `${REPO_ROOT_ENV_VAR}`,
    derived: "relative to the app",
    baked: "recorded when the app was packaged",
    stored: "previously chosen",
  };
  return tried
    .map((t) => `  • ${labels[t.source] ?? t.source}: ${t.path}`)
    .join("\n");
}

module.exports = {
  REPO_MARKERS,
  REPO_ROOT_ENV_VAR,
  describeAttempts,
  looksLikeRepo,
  resolveRepoRoot,
};
