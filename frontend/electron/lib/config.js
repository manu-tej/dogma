"use strict";

/**
 * Values shared between the main process, the preload bridge and the tests.
 *
 * The renderer is served from `app://dogma` rather than `file://`. That single
 * choice is what keeps react-router's BrowserRouter and Vite's absolute asset
 * paths working unchanged, and it gives the backend one stable Origin string to
 * allow instead of the unmatchable `null` that file:// sends.
 */

const APP_SCHEME = "app";
const APP_HOST = "dogma";
const APP_ORIGIN = `${APP_SCHEME}://${APP_HOST}`;
const APP_URL = `${APP_ORIGIN}/`;

/** Must match `server.port` in vite.config.ts. */
const DEV_SERVER_URL = "http://localhost:3000";

/**
 * The renderer talks to 127.0.0.1 rather than "localhost" on purpose: uvicorn
 * binds the IPv4 loopback, while "localhost" can resolve to ::1 first and fail
 * to connect.
 */
const API_BASE_URL = "http://127.0.0.1:8000";

/**
 * Path prefix on the `app://` scheme that proxies to the backend.
 *
 * The packaged renderer calls `app://dogma/api/...` instead of the backend
 * directly, so from the page's point of view every request is same-origin and
 * CORS never enters the picture. That matters because the shell may *adopt* a
 * backend someone else started — one that has no `app://dogma` in its allowlist
 * and would reject every preflight. Proxying makes correctness independent of
 * how the backend was launched.
 */
const API_PROXY_PREFIX = "/api";

/** What the packaged renderer uses as its API base. */
const RENDERER_API_BASE_URL = `${APP_ORIGIN}${API_PROXY_PREFIX}`;

/** Argument prefix used to hand config to the sandboxed preload. */
const CONFIG_ARG_PREFIX = "--dogma-config=";

/**
 * Where the macOS traffic lights sit in the frameless window, as the top-left
 * of the three-button group.
 *
 * Electron exposes no way to *read* where the buttons land, so the shell pins
 * them instead. The reserved strip below is then a computed consequence of a
 * number we control, rather than a constant copied off a blog post that goes
 * quietly wrong the next time macOS restyles its chrome.
 *
 * The buttons are 12px across with 8px gaps: 3*12 + 2*8 = 52 wide, 12 tall.
 */
const TRAFFIC_LIGHT_POSITION = { x: 18, y: 14 };
const TRAFFIC_LIGHT_SIZE = { width: 52, height: 12 };

/**
 * Height of the strip the renderer must leave clear, with the buttons centred
 * in it: 14 above + 12 of button + 14 below.
 *
 * The renderer receives this as `--titlebar-inset` and defaults it to 0px, so
 * the same `frontend/build` output lays out correctly in a browser, where there
 * is no window chrome to avoid.
 */
const TITLEBAR_INSET = TRAFFIC_LIGHT_POSITION.y * 2 + TRAFFIC_LIGHT_SIZE.height;

/**
 * The reserved strip must actually clear the buttons. If someone retunes the
 * position without retuning the strip, fail loudly at require time rather than
 * shipping a window whose logo sits under a traffic light.
 */
if (TITLEBAR_INSET < TRAFFIC_LIGHT_POSITION.y + TRAFFIC_LIGHT_SIZE.height) {
  throw new Error(
    `TITLEBAR_INSET (${TITLEBAR_INSET}px) does not clear the traffic lights, ` +
      `which end at ${TRAFFIC_LIGHT_POSITION.y + TRAFFIC_LIGHT_SIZE.height}px.`,
  );
}

/**
 * Map an `app://dogma/api/...` request onto the backend.
 *
 * @param {string} upstreamBase e.g. "http://127.0.0.1:8000"
 * @param {string} requestUrl Full `app://` request URL.
 * @returns {string|null} Absolute upstream URL, or null if not a proxy path.
 */
function upstreamUrl(upstreamBase, requestUrl) {
  let url;
  try {
    url = new URL(requestUrl);
  } catch {
    return null;
  }
  if (!isProxyPath(url.pathname)) return null;

  // "/api/geo/search" -> "/geo/search"; "/api" -> "/"
  const rest = url.pathname.slice(API_PROXY_PREFIX.length) || "/";
  return `${upstreamBase.replace(/\/+$/, "")}${rest}${url.search}`;
}

/**
 * @param {string} pathname
 * @returns {boolean}
 */
function isProxyPath(pathname) {
  return (
    pathname === API_PROXY_PREFIX ||
    pathname.startsWith(`${API_PROXY_PREFIX}/`)
  );
}

/**
 * Read the config blob injected via `additionalArguments`.
 *
 * @param {string[]} argv
 * @returns {Record<string, unknown>} Empty when absent or unparseable.
 */
function parseConfigArg(argv) {
  const arg = argv.find((value) => value.startsWith(CONFIG_ARG_PREFIX));
  if (!arg) return {};
  try {
    const parsed = JSON.parse(arg.slice(CONFIG_ARG_PREFIX.length));
    return parsed !== null && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

module.exports = {
  API_BASE_URL,
  API_PROXY_PREFIX,
  APP_HOST,
  APP_ORIGIN,
  APP_SCHEME,
  APP_URL,
  CONFIG_ARG_PREFIX,
  DEV_SERVER_URL,
  RENDERER_API_BASE_URL,
  TITLEBAR_INSET,
  TRAFFIC_LIGHT_POSITION,
  TRAFFIC_LIGHT_SIZE,
  isProxyPath,
  parseConfigArg,
  upstreamUrl,
};
