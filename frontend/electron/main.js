"use strict";

/**
 * Electron main process for the Dogma desktop app.
 *
 * Boot sequence:
 *   1. Register the privileged `app://` scheme (must happen before ready).
 *   2. Open the window on a self-contained splash so there is never a blank
 *      frame while the Python backend warms up.
 *   3. Adopt or spawn the backend, reporting progress into the splash.
 *   4. Swap the window over to the real renderer once /health answers.
 *
 * A backend failure ends in a dialog quoting the interpreter's own output,
 * because "could not start" on its own is never enough to act on.
 */

// Refuse to run as plain Node, loudly.
//
// With ELECTRON_RUN_AS_NODE=1 in the environment, the Electron binary is a Node
// interpreter: require("electron") returns the path to the executable instead of
// the API object, and the first property access on it throws. VS Code and Cursor
// set that variable for their integrated terminals, and this repo also ships a
// VS Code extension, so launching from one is a normal thing to do.
//
// run.js, dev.js and smoke.js all scrub it (see lib/env.js), but a packaged .app
// executed directly inherits whatever the shell had. The resulting failure is
// invisible: status 0, no window, nothing on stderr, and no amount of logging
// further down this file is ever reached. Diagnosing it from the symptoms costs
// far more than this check.
if (typeof require("electron") === "string") {
  process.stderr.write(
    "dogma: refusing to start, because ELECTRON_RUN_AS_NODE is set in the\n" +
      "environment. That makes this binary behave as a Node interpreter rather\n" +
      "than as Electron, and the app cannot open a window.\n\n" +
      "VS Code and Cursor set it for their integrated terminals. Relaunch with\n" +
      "it removed:\n\n" +
      `  env -u ELECTRON_RUN_AS_NODE ${process.execPath}\n\n` +
      "Launching from Finder, Spotlight or the Dock is unaffected. The npm\n" +
      "scripts (npm run desktop, dev:desktop, test:desktop-smoke) scrub it for\n" +
      "you.\n",
  );
  process.exit(1);
}

const {
  BrowserWindow,
  Menu,
  app,
  dialog,
  net,
  protocol,
  screen,
  shell,
} = require("electron");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const {
  API_BASE_URL,
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
  upstreamUrl,
} = require("./lib/config");
const {
  BackendStartError,
  probeDependencies,
  startBackend,
} = require("./lib/backend");
const { classifyUrl } = require("./lib/links");
const { resolveRequest } = require("./lib/paths");
const {
  REPO_ROOT_ENV_VAR,
  describeAttempts,
  looksLikeRepo,
  resolveRepoRoot,
} = require("./lib/repoRoot");
const { readJson, writeJson } = require("./lib/store");
const { sanitizeBounds } = require("./lib/windowState");

// Set before any getPath("userData") call, which derives its directory from the
// app name. Also what the macOS application menu and the About item read.
app.setName("dogma");

const IS_DEV = process.env.DOGMA_ELECTRON_DEV === "1";
const IS_SMOKE = process.env.DOGMA_SMOKE === "1";
/**
 * `hiddenInset` and `trafficLightPosition` are macOS-only. Everywhere else the
 * window keeps ordinary chrome and the renderer reserves no strip at all.
 */
const IS_MAC = process.platform === "darwin";
const titlebarInset = IS_MAC ? TITLEBAR_INSET : 0;

/** frontend/electron -> frontend */
const FRONTEND_DIR = path.resolve(__dirname, "..");
const BUILD_DIR = path.join(FRONTEND_DIR, "build");
const SPLASH_FILE = path.join(__dirname, "splash.html");

/**
 * Where the repository lives, which is where the backend's `.venv` is.
 *
 * Not simply `__dirname/../..`: once packaged, that resolves inside
 * Contents/Resources/app. Each possible source is validated instead, so the same
 * ordering works packaged and unpackaged. See lib/repoRoot.js.
 *
 * Resolved lazily on first use so a failure can raise a dialog rather than throw
 * during module evaluation, when there is no window to show it against.
 */
let repoRootResolution = null;

function resolveRepoRootOnce() {
  if (repoRootResolution) return repoRootResolution;

  const bakedFile = path.join(__dirname, "repo-root.generated.json");
  const baked = readJson(bakedFile);
  const stored = readJson(repoRootStateFile());

  repoRootResolution = resolveRepoRoot({
    envValue: process.env[REPO_ROOT_ENV_VAR],
    derived: path.resolve(FRONTEND_DIR, ".."),
    baked:
      baked && typeof baked.repoRoot === "string" ? baked.repoRoot : undefined,
    stored:
      stored && typeof stored.repoRoot === "string"
        ? stored.repoRoot
        : undefined,
    fileExists: (p) => fs.existsSync(p),
  });

  return repoRootResolution;
}

function repoRootStateFile() {
  return path.join(app.getPath("userData"), "repo-root.json");
}

/**
 * Ask the user where the repository is, once, and remember the answer.
 *
 * Only reachable from a packaged app whose baked path has gone stale — the repo
 * was moved or renamed after the build. Quitting with an unexplained error would
 * be the alternative.
 *
 * @returns {Promise<string|null>}
 */
async function promptForRepoRoot(attempts) {
  const { response } = await dialog.showMessageBox({
    type: "error",
    buttons: ["Choose Repository…", "Quit"],
    defaultId: 0,
    cancelId: 1,
    message: "Cannot find the Dogma repository",
    detail:
      "The desktop app runs the backend from the repository's .venv, so it " +
      "needs the checkout on disk.\n\nChecked:\n" +
      `${describeAttempts(attempts)}\n\n` +
      `You can also set ${REPO_ROOT_ENV_VAR} instead of choosing here.`,
  });

  if (response !== 0) return null;

  const picked = await dialog.showOpenDialog({
    properties: ["openDirectory"],
    message: "Select the Dogma repository (the folder containing pyproject.toml)",
  });
  const chosen = picked.filePaths?.[0];
  if (!chosen) return null;

  if (!looksLikeRepo(chosen, (p) => fs.existsSync(p))) {
    await dialog.showMessageBox({
      type: "error",
      buttons: ["OK"],
      message: "That folder is not a Dogma repository",
      detail: `${chosen}\n\nExpected to find pyproject.toml and frontend/package.json.`,
    });
    return null;
  }

  writeJson(repoRootStateFile(), { repoRoot: chosen });
  repoRootResolution = { root: chosen, source: "stored", tried: [] };
  return chosen;
}

const RENDERER_URL = IS_DEV ? DEV_SERVER_URL : APP_URL;
const INTERNAL_ORIGINS = [APP_ORIGIN, DEV_SERVER_URL];

/** Where the backend actually listens. */
const apiUpstream = process.env.DOGMA_API_BASE_URL || API_BASE_URL;

/**
 * What the renderer uses as its API base.
 *
 * In production it is the same-origin `app://dogma/api` proxy, so CORS never
 * applies. In dev the page is served by Vite from http://localhost:3000, which
 * the backend's allowlist already covers, and reaching the proxy from there
 * would itself be cross-origin — so dev talks to the backend directly.
 */
const rendererApiBaseUrl = IS_DEV ? apiUpstream : RENDERER_API_BASE_URL;

/** @type {BrowserWindow | null} */
let mainWindow = null;
/** @type {(() => Promise<void>) | null} */
let stopBackend = null;
/** Console errors seen in the renderer; the smoke run asserts on these. */
const rendererErrors = [];

let shuttingDown = false;

/**
 * The single exit path.
 *
 * `app.exit()` terminates immediately and does *not* emit `before-quit`, so
 * calling it directly skips backend teardown and orphans the uvicorn process we
 * spawned. Every exit therefore goes through here.
 *
 * @param {number} code
 */
async function shutdown(code) {
  if (shuttingDown) return;
  shuttingDown = true;
  if (stopBackend) {
    try {
      await stopBackend();
    } catch {
      // Nothing useful to do; we are exiting regardless.
    }
    stopBackend = null;
  }
  app.exit(code);
}

// ---------------------------------------------------------------------------
// Protocol
// ---------------------------------------------------------------------------

// Must be called before the app is ready. `standard` gives the scheme real URL
// semantics (so relative paths and history work); `secure` keeps it a trusted
// context so fetch and the Web Crypto API behave as they do over https.
protocol.registerSchemesAsPrivileged([
  {
    scheme: APP_SCHEME,
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      corsEnabled: true,
    },
  },
]);

/**
 * Forward an `app://dogma/api/...` request to the backend.
 *
 * The request body is buffered rather than streamed because a streaming request
 * body would require `duplex: "half"` and the app only ever POSTs JSON. The
 * *response* is passed through untouched so server-sent events still stream.
 *
 * @param {Request} request
 * @returns {Promise<Response>}
 */
async function proxyToBackend(request) {
  const target = upstreamUrl(apiUpstream, request.url);
  if (!target) {
    return new Response("Bad request", { status: 400 });
  }

  const headers = new Headers(request.headers);
  // Dropped so the backend sees an ordinary same-origin request rather than a
  // cross-origin one it would have to have been configured to allow.
  headers.delete("origin");
  headers.delete("host");
  headers.delete("referer");

  /** @type {RequestInit} */
  const init = { method: request.method, headers };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  try {
    return await net.fetch(target, init);
  } catch (error) {
    // Report this as a gateway failure rather than letting the renderer see an
    // opaque network error it cannot distinguish from a bug in itself.
    return new Response(
      JSON.stringify({ detail: `Backend unreachable: ${error.message}` }),
      { status: 502, headers: { "content-type": "application/json" } },
    );
  }
}

function registerAppProtocol() {
  protocol.handle(APP_SCHEME, async (request) => {
    const { host, pathname } = new URL(request.url);
    if (host !== APP_HOST) {
      return new Response("Not found", { status: 404 });
    }

    // Checked before static resolution: /api/* belongs to the backend, and the
    // SPA has no route by that name.
    if (isProxyPath(pathname)) {
      return proxyToBackend(request);
    }

    const resolved = resolveRequest(BUILD_DIR, request.url, (p) => {
      try {
        return fs.statSync(p).isFile();
      } catch {
        return false;
      }
    });

    switch (resolved.kind) {
      case "file":
      case "fallback":
        return net.fetch(pathToFileURL(resolved.filePath).toString());
      case "denied":
        return new Response("Forbidden", { status: 403 });
      case "badRequest":
        return new Response("Bad request", { status: 400 });
      default:
        return new Response("Not found", { status: 404 });
    }
  });
}

/**
 * Content Security Policy for the packaged renderer.
 *
 * Applied in production only: the Vite dev server needs eval for react-refresh
 * and a websocket for HMR, and locking those down would break `electron:dev`
 * without protecting anything a developer does not already control.
 */
function applyContentSecurityPolicy() {
  if (IS_DEV) {
    // The guard lives here rather than at the call site so it cannot drift from
    // the rule documented above. Vite serves an inline react-refresh preamble,
    // which `script-src 'self'` blocks outright — the renderer then mounts
    // nothing and the window stays black.
    return;
  }

  const csp = [
    `default-src 'self' ${APP_ORIGIN}`,
    // Radix and Tailwind v4 both inject inline style attributes.
    `style-src 'self' ${APP_ORIGIN} 'unsafe-inline'`,
    `script-src 'self' ${APP_ORIGIN}`,
    `font-src 'self' ${APP_ORIGIN} data:`,
    `img-src 'self' ${APP_ORIGIN} data: blob: https:`,
    // Same-origin suffices: API traffic goes through the app:// proxy.
    `connect-src 'self' ${APP_ORIGIN}`,
    "object-src 'none'",
    "frame-src 'none'",
    "base-uri 'none'",
    "form-action 'none'",
  ].join("; ");

  const session = mainWindow?.webContents.session;
  session?.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        "Content-Security-Policy": [csp],
      },
    });
  });
}

// ---------------------------------------------------------------------------
// Window
// ---------------------------------------------------------------------------

function windowStateFile() {
  return path.join(app.getPath("userData"), "window-state.json");
}

function persistWindowState() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  // Saving a maximized or minimized frame would restore a tiny window.
  if (mainWindow.isMinimized() || mainWindow.isMaximized()) return;
  writeJson(windowStateFile(), mainWindow.getNormalBounds());
}

function createWindow() {
  const displays = screen.getAllDisplays().map((d) => d.workArea);
  const bounds = sanitizeBounds(readJson(windowStateFile()), displays);

  mainWindow = new BrowserWindow({
    ...bounds,
    minWidth: 900,
    minHeight: 600,
    show: true,
    // The `background` token, oklch(0.155 0.006 264), converted to sRGB. Painted
    // before any renderer content exists, so a near-miss shows as a flash on
    // launch and again on every reload.
    backgroundColor: "#0b0c0f",
    title: "dogma",
    // On macOS the renderer draws under the window chrome and the app supplies
    // its own header. The traffic lights would otherwise land on the NavRail's
    // brand mark, so the shell pins them to a known spot and tells the renderer
    // how much room to leave via `--titlebar-inset`. See lib/config.js for how
    // the strip height is derived from the button placement.
    titleBarStyle: IS_MAC ? "hiddenInset" : "default",
    ...(IS_MAC ? { trafficLightPosition: TRAFFIC_LIGHT_POSITION } : {}),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      additionalArguments: [
        CONFIG_ARG_PREFIX +
          JSON.stringify({
            apiBaseUrl: rendererApiBaseUrl,
            titlebarInset,
          }),
      ],
    },
  });

  // macOS hides the traffic lights in native fullscreen, so the reserved strip
  // becomes dead space. Overriding the custom property from the main process
  // keeps this out of the renderer entirely — no IPC channel, and nothing for
  // the sandboxed preload to forward. `insertCSS` survives in-app navigation
  // but not a reload, so it is re-applied on `did-finish-load` below.
  if (IS_MAC) {
    /** @type {string | null} */
    let fullScreenCssKey = null;

    const clearInset = async () => {
      if (!mainWindow || mainWindow.isDestroyed() || fullScreenCssKey) return;
      try {
        // `!important` is load-bearing: the renderer sets `--titlebar-inset` as
        // an *inline* style on <html>, and an inline declaration outranks an
        // ordinary stylesheet rule. Only an important author declaration wins.
        fullScreenCssKey = await mainWindow.webContents.insertCSS(
          ":root { --titlebar-inset: 0px !important; }",
        );
      } catch {
        // The window can go away mid-transition; the strip is cosmetic.
      }
    };

    const restoreInset = async () => {
      if (!mainWindow || mainWindow.isDestroyed() || !fullScreenCssKey) return;
      const key = fullScreenCssKey;
      fullScreenCssKey = null;
      try {
        await mainWindow.webContents.removeInsertedCSS(key);
      } catch {
        // Same as above.
      }
    };

    mainWindow.on("enter-full-screen", () => void clearInset());
    mainWindow.on("leave-full-screen", () => void restoreInset());
    mainWindow.webContents.on("did-finish-load", () => {
      // A reload drops inserted CSS, so the key is stale even though the window
      // is still fullscreen. Forget it, then re-insert if still needed.
      fullScreenCssKey = null;
      if (mainWindow && !mainWindow.isDestroyed() && mainWindow.isFullScreen()) {
        void clearInset();
      }
    });
  }

  applyContentSecurityPolicy();

  // Send web links to the system browser; refuse everything else outright so
  // the app window cannot be navigated away from Dogma.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (classifyUrl(url, INTERNAL_ORIGINS) === "external") {
      shell.openExternal(url);
    }
    return { action: "deny" };
  });

  mainWindow.webContents.on("will-navigate", (event, url) => {
    const kind = classifyUrl(url, INTERNAL_ORIGINS);
    if (kind === "internal") return;
    event.preventDefault();
    if (kind === "external") {
      shell.openExternal(url);
    }
  });

  mainWindow.webContents.on("console-message", (...args) => {
    // Electron 35 replaced the positional signature with a details object.
    const details = typeof args[1] === "object" ? args[1] : null;
    const level = details ? details.level : args[1];
    const message = details ? details.message : args[2];
    if (level === "error" || level === 3) {
      rendererErrors.push(String(message));
    }
  });

  mainWindow.webContents.on(
    "did-fail-load",
    (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
      if (!isMainFrame) return;
      // -3 is ERR_ABORTED, which fires for ordinary in-app navigation.
      if (errorCode === -3) return;
      rendererErrors.push(
        `did-fail-load ${errorCode} ${errorDescription} ${validatedURL}`,
      );
    },
  );

  let saveTimer = null;
  const scheduleSave = () => {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(persistWindowState, 400);
  };
  mainWindow.on("resize", scheduleSave);
  mainWindow.on("move", scheduleSave);

  mainWindow.on("close", () => {
    clearTimeout(saveTimer);
    persistWindowState();
  });
  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  return mainWindow;
}

/** @param {string} text @param {boolean} [failed] */
async function setSplashStatus(text, failed = false) {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  try {
    await mainWindow.webContents.executeJavaScript(
      `window.setStatus?.(${JSON.stringify(text)}, ${Boolean(failed)})`,
    );
  } catch {
    // The splash may already have been replaced by the app.
  }
}

// ---------------------------------------------------------------------------
// Menu
// ---------------------------------------------------------------------------

/**
 * Without an application menu, macOS gives the window no Cmd+C/Cmd+V at all —
 * the Edit menu roles are what bind the standard clipboard accelerators.
 */
function buildMenu() {
  const isMac = process.platform === "darwin";

  const template = [
    ...(isMac ? [{ role: "appMenu" }] : []),
    {
      label: "File",
      submenu: [isMac ? { role: "close" } : { role: "quit" }],
    },
    { role: "editMenu" },
    {
      label: "View",
      submenu: [
        { role: "reload" },
        { role: "forceReload" },
        { type: "separator" },
        { role: "resetZoom" },
        { role: "zoomIn" },
        { role: "zoomOut" },
        { type: "separator" },
        { role: "togglefullscreen" },
        { type: "separator" },
        { role: "toggleDevTools" },
      ],
    },
    { role: "windowMenu" },
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// ---------------------------------------------------------------------------
// Smoke check
// ---------------------------------------------------------------------------

/**
 * Boot the real app and assert it actually rendered. Exits the process with a
 * non-zero status on failure so CI and `npm run electron:smoke` can gate on it.
 */
async function runSmokeCheck() {
  const failures = [];

  try {
    const mounted = await mainWindow.webContents.executeJavaScript(
      "!!document.getElementById('root') && document.getElementById('root').childElementCount > 0",
    );
    if (!mounted) {
      failures.push("#root rendered no children — the React tree did not mount");
    }

    const title = await mainWindow.webContents.executeJavaScript(
      "document.title",
    );
    if (!title) {
      failures.push("document.title was empty");
    }

    // Client-side routing under app:// is the thing most likely to be broken,
    // so exercise a real navigation rather than trusting the initial render.
    await mainWindow.webContents.executeJavaScript(
      "window.history.pushState({}, '', '/datasets'); window.dispatchEvent(new PopStateEvent('popstate'));",
    );
    await new Promise((resolve) => setTimeout(resolve, 1_500));

    const afterNav = await mainWindow.webContents.executeJavaScript(
      "({ path: window.location.pathname, children: document.getElementById('root')?.childElementCount ?? 0 })",
    );
    if (afterNav.path !== "/datasets") {
      failures.push(`route did not change, pathname is ${afterNav.path}`);
    }
    if (afterNav.children === 0) {
      failures.push("#root emptied after navigating to /datasets");
    }

    // The application menu binds accelerators at the native level, so a role or
    // a stray Cmd+K entry can swallow the keystroke before the renderer ever
    // sees it. Drive the real handler and confirm the palette opens.
    await mainWindow.webContents.executeJavaScript(
      "window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, ctrlKey: true, bubbles: true }))",
    );
    await new Promise((resolve) => setTimeout(resolve, 800));
    const paletteOpen = await mainWindow.webContents.executeJavaScript(
      "!!document.querySelector('[role=\"dialog\"]')",
    );
    if (!paletteOpen) {
      failures.push("Cmd+K did not open the command palette");
    }
    await mainWindow.webContents.executeJavaScript(
      "window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))",
    );

    const bridge = await mainWindow.webContents.executeJavaScript(
      "({ isDesktop: window.dogma?.isDesktop === true, apiBaseUrl: window.dogma?.apiBaseUrl ?? null })",
    );
    if (!bridge.isDesktop) {
      failures.push("window.dogma bridge was not exposed by the preload");
    }
    if (bridge.apiBaseUrl !== rendererApiBaseUrl) {
      failures.push(
        `window.dogma.apiBaseUrl was ${bridge.apiBaseUrl}, ` +
          `expected ${rendererApiBaseUrl}`,
      );
    }

    // The frameless window draws under the macOS chrome, so the app's own header
    // has to leave room for the traffic lights. This is measured rather than
    // assumed: with no inset the brand mark sits at y=12 — directly beneath the
    // buttons — and the last assertion here is what fails in that state. That is
    // the regression this whole mechanism exists to prevent.
    if (IS_MAC) {
      const chrome = await mainWindow.webContents.executeJavaScript(`
        (() => {
          const root = document.documentElement;
          const brand = document.querySelector('[aria-label="dogma home"]');
          const strip = document.querySelector('[data-testid="titlebar-drag-region"]');
          return {
            inset: getComputedStyle(root).getPropertyValue('--titlebar-inset').trim(),
            hasClass: root.classList.contains('dogma-custom-titlebar'),
            brandTop: brand ? Math.round(brand.getBoundingClientRect().top) : null,
            stripHeight: strip ? Math.round(strip.getBoundingClientRect().height) : null,
          };
        })()
      `);

      const buttonsBottom =
        TRAFFIC_LIGHT_POSITION.y + TRAFFIC_LIGHT_SIZE.height;

      if (!chrome.hasClass) {
        failures.push(
          "renderer did not apply the dogma-custom-titlebar class, so the " +
            "window has no draggable region",
        );
      }
      if (chrome.inset !== `${titlebarInset}px`) {
        failures.push(
          `--titlebar-inset resolved to "${chrome.inset}", expected ${titlebarInset}px`,
        );
      }
      if (chrome.stripHeight !== titlebarInset) {
        failures.push(
          `drag region is ${chrome.stripHeight}px tall, expected ${titlebarInset}px`,
        );
      }
      if (chrome.brandTop === null) {
        failures.push("could not find the brand mark to measure against");
      } else if (chrome.brandTop < buttonsBottom) {
        failures.push(
          `brand mark starts at y=${chrome.brandTop}, underneath the traffic ` +
            `lights (which end at y=${buttonsBottom})`,
        );
      }
    }

    // The crux of the proxy design: a real API round trip from the renderer.
    // If this needed CORS it would fail here, which is exactly what happened
    // when the shell adopted a backend started without app://dogma allowed.
    if (!IS_DEV) {
      const roundTrip = await mainWindow.webContents.executeJavaScript(`
        (async () => {
          try {
            const r = await fetch('${RENDERER_API_BASE_URL}/openapi.json');
            return { ok: r.ok, status: r.status };
          } catch (e) {
            return { ok: false, status: null, error: String(e) };
          }
        })()
      `);
      if (!roundTrip.ok) {
        failures.push(
          `API proxy round trip failed: status=${roundTrip.status} ` +
            `${roundTrip.error ?? ""}`,
        );
      }
    }

    const nodeLeak = await mainWindow.webContents.executeJavaScript(
      "typeof require !== 'undefined' || typeof process !== 'undefined'",
    );
    if (nodeLeak) {
      failures.push("Node globals are reachable from the renderer");
    }
  } catch (error) {
    failures.push(`smoke evaluation threw: ${error.message}`);
  }

  if (rendererErrors.length > 0) {
    failures.push(
      `renderer logged ${rendererErrors.length} console error(s):\n    ` +
        rendererErrors.slice(0, 10).join("\n    "),
    );
  }

  if (failures.length > 0) {
    console.error("\nSMOKE FAILED");
    for (const failure of failures) {
      console.error(`  - ${failure}`);
    }
    await shutdown(1);
    return;
  }

  console.log("SMOKE PASSED: renderer mounted, routed and isolated correctly");
  // Deliberately app.quit() rather than shutdown(0): this is the path a user
  // takes with Cmd+Q, so exiting through it means the smoke run also covers the
  // `before-quit` teardown. smoke.js checks for an orphaned backend afterwards.
  app.quit();
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

async function boot() {
  if (!IS_DEV && !fs.existsSync(path.join(BUILD_DIR, "index.html"))) {
    dialog.showErrorBox(
      "Frontend build missing",
      `No build found at ${BUILD_DIR}.\n\n` +
        "Build it first, from the repository root:\n\n" +
        "  npm run build:frontend",
    );
    await shutdown(1);
    return;
  }

  registerAppProtocol();
  buildMenu();
  createWindow();

  await mainWindow.loadFile(SPLASH_FILE);

  // Resolved after the window exists so a miss can raise a dialog against it.
  let { root: repoRoot, tried } = resolveRepoRootOnce();
  if (!repoRoot) {
    await setSplashStatus("Cannot find the Dogma repository", true);
    repoRoot = await promptForRepoRoot(tried);
    if (!repoRoot) {
      await shutdown(1);
      return;
    }
  }

  try {
    const backend = await startBackend({
      repoRoot,
      corsOrigin: APP_ORIGIN,
      onStatus: (status) => void setSplashStatus(status),
    });
    stopBackend = backend.stop;
    console.log(`[dogma] backend ${backend.mode} at ${backend.baseUrl}`);

    // Informational only. /health reports on Postgres and Redis, which this
    // workspace does not require, so a failure here must not block startup —
    // the UI's own per-feature error states are more useful than a dead window.
    const dependencies = await probeDependencies(backend.baseUrl);
    if (!dependencies.ok) {
      console.log(
        `[dogma] backend dependencies unavailable ` +
          `(/health ${dependencies.status ?? "unreachable"}` +
          `${dependencies.detail ? `: ${dependencies.detail}` : ""}) — ` +
          `features needing a database or cache will not work`,
      );
    }
  } catch (error) {
    const detail =
      error instanceof BackendStartError && error.logs
        ? `${error.message}\n\nLast output from the backend:\n${error.logs}`
        : error.message;

    await setSplashStatus("The backend could not be started.", true);

    if (IS_SMOKE) {
      console.error(`\nSMOKE FAILED\n  - backend did not start\n${detail}`);
      await shutdown(1);
      return;
    }

    const { response } = await dialog.showMessageBox(mainWindow, {
      type: "error",
      title: "Backend unavailable",
      message: "Dogma could not start its Python backend.",
      detail,
      buttons: ["Continue without backend", "Quit"],
      defaultId: 0,
      cancelId: 1,
    });
    if (response === 1) {
      await shutdown(1);
      return;
    }
    // Continuing is deliberate: the UI still renders, and its own error states
    // are more informative than a dead window.
  }

  if (mainWindow.isDestroyed()) return;

  await setSplashStatus("Loading the workspace…");
  // Errors logged while the splash was up are not renderer errors.
  rendererErrors.length = 0;
  await mainWindow.loadURL(RENDERER_URL);

  if (IS_DEV && !IS_SMOKE) {
    mainWindow.webContents.openDevTools({ mode: "detach" });
  }

  if (IS_SMOKE) {
    // Give lazy route chunks and the first paint a moment to settle.
    setTimeout(() => void runSmokeCheck(), 3_000);
  }
}

// A second instance would race the first for port 8000 and the window-state
// file. Focus the existing window instead.
if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (!mainWindow) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  });

  app.whenReady().then(boot);

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      void boot();
    }
  });

  app.on("window-all-closed", () => {
    // Standard macOS behaviour is to stay resident; elsewhere, quit.
    if (process.platform !== "darwin") {
      app.quit();
    }
  });

  app.on("before-quit", (event) => {
    if (!stopBackend || shuttingDown) return;
    // Hold the quit open just long enough to reap the backend.
    event.preventDefault();
    shuttingDown = true;
    stopBackend()
      .catch(() => {})
      .finally(() => {
        stopBackend = null;
        app.quit();
      });
  });

  // A signal-terminated Electron never emits `before-quit`, so without this the
  // uvicorn we spawned survives its parent — the orphan CLAUDE.md warns about.
  // Ctrl-C in `npm run desktop` arrives as SIGINT, process supervisors and
  // `kill` send SIGTERM, and a closed terminal sends SIGHUP; all three have to
  // reach the same teardown that quitting normally does.
  for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    process.on(signal, () => {
      void shutdown(0);
    });
  }
}
