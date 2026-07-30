"use strict";

/**
 * Environment sanitising for spawning the Electron binary.
 *
 * VS Code and Cursor set `ELECTRON_RUN_AS_NODE=1` for the processes they host,
 * including their integrated terminals and extension hosts. Inherited, it makes
 * the Electron binary run as a plain Node interpreter, so `require("electron")`
 * yields the path string to the executable instead of the API object and the
 * app dies on the first `protocol.…` access.
 *
 * Since this repo also ships a VS Code extension, launching from an integrated
 * terminal is a likely path, so the launchers scrub the variable rather than
 * relying on a clean shell.
 */

/** Variables that make the Electron binary refuse to be Electron. */
const STRIPPED_VARS = ["ELECTRON_RUN_AS_NODE"];

/**
 * @param {Record<string, string | undefined>} [base] Environment to derive from.
 * @param {Record<string, string>} [overrides] Values to set.
 * @returns {Record<string, string | undefined>}
 */
function electronEnv(base = process.env, overrides = {}) {
  const env = { ...base, ...overrides };
  for (const name of STRIPPED_VARS) {
    delete env[name];
  }
  return env;
}

module.exports = { STRIPPED_VARS, electronEnv };
