"use strict";

/**
 * `npm run electron`
 *
 * Launches the production app against `frontend/build`.
 *
 * This wrapper exists instead of a bare `electron .` so the child environment
 * can be scrubbed — see lib/env.js for why an inherited ELECTRON_RUN_AS_NODE
 * would otherwise break the launch outright.
 */

const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const { electronEnv } = require("./lib/env");

const FRONTEND_DIR = path.resolve(__dirname, "..");
const BUILD_INDEX = path.join(FRONTEND_DIR, "build", "index.html");

if (!fs.existsSync(BUILD_INDEX)) {
  console.error(
    `[dogma] no build at ${BUILD_INDEX}\n` +
      "        run `npm run build` in frontend/ first",
  );
  process.exit(1);
}

const child = spawn(
  require("electron"),
  [path.join(__dirname, "main.js"), ...process.argv.slice(2)],
  {
    cwd: FRONTEND_DIR,
    env: electronEnv(),
    stdio: "inherit",
  },
);

child.on("exit", (code, signal) => {
  process.exit(signal ? 1 : (code ?? 0));
});
