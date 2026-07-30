"use strict";

/**
 * Minimal, read-only bridge. Runs sandboxed with context isolation, so the
 * renderer sees exactly the four values below and no Node capability.
 *
 * The renderer needs `apiBaseUrl` at runtime rather than from a build-time
 * `import.meta.env`, because the same `frontend/build` output serves both the
 * web app and the desktop app, and because the desktop backend must be reached
 * over the IPv4 loopback.
 *
 * IMPORTANT: this file must stay self-contained. A sandboxed preload cannot
 * `require` relative modules — it only gets `electron` plus a small polyfilled
 * subset of Node built-ins — so sharing `lib/config.js` here would fail at
 * runtime with "module not found". The prefix below is therefore duplicated
 * from that module on purpose; `test/preload.test.js` asserts the two stay in
 * sync and that no relative require creeps back in.
 */

const { contextBridge } = require("electron");

const CONFIG_ARG_PREFIX = "--dogma-config=";

function readConfig(argv) {
  const arg = argv.find((value) => value.startsWith(CONFIG_ARG_PREFIX));
  if (!arg) return {};
  try {
    const parsed = JSON.parse(arg.slice(CONFIG_ARG_PREFIX.length));
    return parsed !== null && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

const config = readConfig(process.argv);

contextBridge.exposeInMainWorld("dogma", {
  isDesktop: true,
  apiBaseUrl: typeof config.apiBaseUrl === "string" ? config.apiBaseUrl : null,
  platform: process.platform,
  // Height of the strip kept clear for the macOS traffic lights. 0 when the
  // window has ordinary chrome, which is what every non-macOS platform gets.
  titlebarInset:
    typeof config.titlebarInset === "number" && config.titlebarInset >= 0
      ? config.titlebarInset
      : 0,
});
