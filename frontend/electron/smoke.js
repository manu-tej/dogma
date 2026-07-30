"use strict";

/**
 * `npm run electron:smoke`
 *
 * Launches the real packaged app with DOGMA_SMOKE=1. main.js then asserts the
 * renderer mounted, client-side routing works under `app://`, the preload
 * bridge is present and Node is not reachable from the renderer, and exits
 * non-zero if any of that fails.
 *
 * This is the gate that unit tests cannot provide: it proves the app boots.
 */

const { execFileSync, spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const { electronEnv } = require("./lib/env");

const FRONTEND_DIR = path.resolve(__dirname, "..");
const BUILD_INDEX = path.join(FRONTEND_DIR, "build", "index.html");
const TIMEOUT_MS = 180_000;

if (!fs.existsSync(BUILD_INDEX)) {
  console.error(
    `[dogma] no build at ${BUILD_INDEX}\n` +
      "        run `npm run build` in frontend/ first",
  );
  process.exit(1);
}

/**
 * Whether a backend was already running before we launched.
 *
 * This decides whether the no-orphan assertion applies at all. If one was
 * already up the app *adopts* it and correctly leaves it running on quit, so
 * asserting it disappeared would fail a working app.
 */
const preexistingBackend = orphanedBackend().length > 0;
if (preexistingBackend) {
  console.log(
    "[dogma] a backend is already running; the app will adopt it and the " +
      "no-orphan check will be skipped",
  );
}

const child = spawn(
  require("electron"),
  [path.join(FRONTEND_DIR, "electron", "main.js")],
  {
    cwd: FRONTEND_DIR,
    env: electronEnv(process.env, { DOGMA_SMOKE: "1" }),
    stdio: "inherit",
  },
);

const timer = setTimeout(() => {
  console.error(`[dogma] smoke run exceeded ${TIMEOUT_MS / 1000}s`);
  child.kill("SIGKILL");
  process.exit(1);
}, TIMEOUT_MS);

/**
 * Was a backend left behind?
 *
 * The success path exits through `app.quit()` so the `before-quit` teardown is
 * exercised; this is the assertion that it actually worked. An orphaned uvicorn
 * holds port 8000 and silently changes the next launch into an "adopt".
 */
function orphanedBackend() {
  try {
    const listing = execFileSync("ps", ["-eo", "pid,command"], {
      encoding: "utf8",
    });
    return listing
      .split("\n")
      .filter((line) => line.includes("uvicorn quration.api.server"))
      .filter((line) => !line.includes("ps -eo"));
  } catch {
    return [];
  }
}

child.on("exit", (code, signal) => {
  clearTimeout(timer);
  if (signal) {
    console.error(`[dogma] smoke run killed by ${signal}`);
    process.exit(1);
  }

  if (code === 0 && !preexistingBackend) {
    const orphans = orphanedBackend();
    if (orphans.length > 0) {
      console.error(
        "\nSMOKE FAILED\n  - the backend outlived the app; " +
          "before-quit did not reap it:\n    " +
          orphans.join("\n    "),
      );
      process.exit(1);
    }
    console.log("[dogma] backend reaped on quit");
  }

  process.exit(code ?? 1);
});
