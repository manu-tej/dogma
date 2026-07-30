"use strict";

/**
 * `npm run electron:dev` — Vite dev server plus Electron pointed at it.
 * `npm run electron:dev -- --smoke` — the same, but run the boot assertions and
 * exit with their status instead of staying open.
 *
 * Written in Node rather than as a shell one-liner so the inline env vars and
 * process cleanup work the same on Windows.
 *
 * The `--smoke` mode exists because dev and production load the renderer by
 * different routes, so a production-only smoke run can pass while dev is
 * broken. That happened: the CSP was applied in dev too, which blocked Vite's
 * inline react-refresh preamble and left the window black.
 */

const { spawn } = require("node:child_process");
const path = require("node:path");

const { DEV_SERVER_URL } = require("./lib/config");
const { electronEnv } = require("./lib/env");

const FRONTEND_DIR = path.resolve(__dirname, "..");
const READY_TIMEOUT_MS = 60_000;
const POLL_INTERVAL_MS = 250;

const SMOKE = process.argv.includes("--smoke");

/** @type {import("node:child_process").ChildProcess[]} */
const children = [];
let shuttingDown = false;

function shutdown(code) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) {
    if (child.exitCode === null && child.signalCode === null) {
      child.kill("SIGTERM");
    }
  }
  process.exit(code);
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => shutdown(0));
}

async function waitForServer() {
  const deadline = Date.now() + READY_TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      await fetch(DEV_SERVER_URL, { signal: AbortSignal.timeout(1_000) });
      return true;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
    }
  }
  return false;
}

async function main() {
  console.log("[dogma] starting Vite…");
  const vite = spawn("npm", ["run", "dev"], {
    cwd: FRONTEND_DIR,
    // DOGMA_ELECTRON stops vite.config.ts from also opening a browser tab.
    env: { ...process.env, DOGMA_ELECTRON: "1" },
    stdio: "inherit",
    shell: process.platform === "win32",
  });
  children.push(vite);
  vite.on("exit", (code) => shutdown(code ?? 0));

  if (!(await waitForServer())) {
    console.error(`[dogma] ${DEV_SERVER_URL} never came up`);
    shutdown(1);
    return;
  }

  console.log(`[dogma] Vite ready, launching Electron…`);
  const electron = spawn(
    require("electron"),
    [path.join(FRONTEND_DIR, "electron", "main.js")],
    {
      cwd: FRONTEND_DIR,
      env: electronEnv(process.env, {
        DOGMA_ELECTRON: "1",
        DOGMA_ELECTRON_DEV: "1",
        ...(SMOKE ? { DOGMA_SMOKE: "1" } : {}),
      }),
      stdio: "inherit",
    },
  );
  children.push(electron);
  electron.on("exit", (code) => shutdown(code ?? 0));
}

void main();
