#!/usr/bin/env node
"use strict";

/**
 * Record where this repository lives, so the packaged app can find it.
 *
 * Run immediately before electron-builder. The file it writes is included in the
 * bundle and read by main.js when the derived path fails validation — which is
 * always the case once packaged, because the derivation lands inside
 * Contents/Resources/app.
 *
 * The output is NOT committed. Two reasons:
 *   - It is machine-specific; committing it would hand the next developer a path
 *     that does not exist on their disk.
 *   - tools/check-public-safety.js rejects any tracked text file containing a
 *     developer-local absolute path, and this file is nothing but one.
 * `.gitignore` covers it. If you are reading this because the check failed, the
 * fix is to remove the file from the index, not to relax the check.
 */

const fs = require("node:fs");
const path = require("node:path");

const { looksLikeRepo } = require("./lib/repoRoot");

/** frontend/electron -> frontend -> repository root */
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const OUTPUT = path.join(__dirname, "repo-root.generated.json");

const fileExists = (p) => fs.existsSync(p);

if (!looksLikeRepo(REPO_ROOT, fileExists)) {
  console.error(
    `bake-repo-root: ${REPO_ROOT} does not look like the Dogma repository.\n` +
      "Expected pyproject.toml and frontend/package.json there. Refusing to " +
      "bake a path the packaged app could not use.",
  );
  process.exit(1);
}

fs.writeFileSync(
  OUTPUT,
  `${JSON.stringify({ repoRoot: REPO_ROOT }, null, 2)}\n`,
  "utf8",
);

console.log(`baked repo root ${REPO_ROOT} -> ${path.basename(OUTPUT)}`);
