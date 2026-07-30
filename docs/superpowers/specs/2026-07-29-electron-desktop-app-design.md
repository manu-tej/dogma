# Electron desktop app for the Dogma frontend

Date: 2026-07-29

## Goal

Run the existing `frontend/` Vite + React workspace as a desktop app that works
without manual setup steps, and without forking the web build.

Scope decisions taken at the outset:

- The Electron shell **owns the Python backend's lifecycle**, spawning `uvicorn`
  from the repo `.venv`. It does not bundle a Python runtime, so the app is not
  redistributable to machines without the repo. That was an accepted trade.
- Packaging stops at a **local unpackaged app**: `electron:dev` and `electron`.
  No installer, no signing, no notarization.

## Architecture

Everything lives in `frontend/electron/`, with `electron` as a devDependency of
`frontend/`. Placing it there preserves the invariant recorded in `CLAUDE.md`
that `frontend/` is the only npm install target; a separate `desktop/` package
would have added a third one for no benefit.

```text
frontend/electron/
  main.js          window, app:// handler, API proxy, menu, lifecycle, smoke
  preload.js       contextBridge → window.dogma (self-contained by necessity)
  run.js           `npm run electron`      — production launch
  dev.js           `npm run electron:dev`  — Vite + Electron
  smoke.js         `npm run electron:smoke` — boots the real app, gates on it
  splash.html      boot status while the backend warms
  lib/             pure, unit-tested helpers
  test/            node:test suites (69 tests)
```

`lib/` holds the logic worth testing in isolation: `paths` (app:// resolution,
interpreter lookup), `backend` (supervision), `links` (navigation policy),
`windowState` (bounds sanitising), `env` (child environment), `config`
(constants), `store` (best-effort JSON persistence).

## Loading the renderer: `app://dogma`, not `file://`

The renderer is served by a privileged custom scheme registered with
`registerSchemesAsPrivileged({standard: true, secure: true})` and handled by
`protocol.handle`.

Rejected alternatives:

- **`file://` with `HashRouter` and `base: './'`** — would have meant editing
  `src/main.tsx`, turning web URLs into `#/foo`, and running a different router
  on desktop than on web. Divergence between the two surfaces is the specific
  thing this design avoids. `file://` also sends `Origin: null`, which a CORS
  allowlist cannot express.
- **An embedded localhost HTTP server** — a random port means the backend's CORS
  allowlist cannot be static.

What the chosen scheme buys: `BrowserRouter` and Vite's absolute `/assets/…`
paths work with **no changes to shared app code**, and the renderer gets a
stable origin instead of the unmatchable `null` that `file://` sends.

### API traffic is proxied, not cross-origin

The first version pointed the renderer straight at `http://127.0.0.1:8000` and
allowed `app://dogma` through the backend's `DOGMA_CORS_ORIGINS` hook. That works
only when the shell *started* the backend — and the adopt path is precisely the
case where it did not. Adopting a backend launched by `npm run dev` produced an
app that opened normally and then failed every request on preflight.

So `app://dogma/api/…` is proxied by the main process to the backend instead.
From the page's point of view every request is same-origin, so CORS never enters
the picture and correctness no longer depends on how the backend was launched.
`DOGMA_CORS_ORIGINS` is still injected on the spawn path, but nothing depends on
it. It also lets the CSP's `connect-src` stay same-origin.

Details that matter: the request body is buffered rather than streamed, because a
streaming body would need `duplex: "half"` and the app only POSTs JSON; the
*response* is passed through untouched so server-sent events still stream;
`Origin`, `Host` and `Referer` are stripped so the backend sees an ordinary
request; and an unreachable backend becomes a `502` with a JSON detail rather
than an opaque network error the renderer cannot tell from its own bug.

Dev mode is the exception: the page is served by Vite from
`http://localhost:3000`, reaching the proxy from there would itself be
cross-origin, and the backend's allowlist already covers that origin — so dev
talks to the backend directly.

The handler resolves requests with an explicit containment guard. A missing
*asset* is a 404; a missing *route* falls back to `index.html`, which is what
makes client-side routing work. Returning HTML for a missing `.js` would surface
as an opaque MIME error instead of the real problem.

## Backend supervision

1. **Probe before spawning.** If `127.0.0.1:8000` already answers, adopt it and
   do not manage its lifecycle. This makes a concurrent `npm run dev:backend`
   harmless instead of an `EADDRINUSE` crash or a duplicate server. Adoption is
   only actually *useful* because API traffic is proxied — see above.
2. **Missing `.venv`** produces a dialog quoting the exact setup commands.
3. **Captured output.** stdout/stderr go to a bounded ring buffer, so a failed
   boot reports the interpreter's own error rather than "could not start".
4. **Teardown** is SIGTERM then SIGKILL after a grace period, for spawned
   processes only.

### Readiness is `/openapi.json`, not `/health`

`/health` (`src/quration/api/routes/health.py`) is a Kubernetes-style readiness
probe that `Depends` on an async Postgres session and a Redis client. With
neither configured, the dependency raises *before* the handler's own
`try/except`, so it answers **500 forever** — gating startup on it would mean the
app never opens without Postgres and Redis.

`/openapi.json` is generated by FastAPI itself with no dependencies. Liveness is
defined as *any* HTTP response from it, including an error status: receiving one
proves the socket is accepting and the ASGI app is routing, which is all the
shell needs before showing UI. Dependency health is probed separately and only
logged; the UI's per-feature error states are more useful than a blocked splash.

## Constraints discovered during implementation

These are the non-obvious ones, each now covered by a regression test.

- **`URL.prototype.origin` is unusable for a custom scheme in the main process.**
  Node returns the string `"null"` for `app://dogma/x`, because the spec assigns
  unregistered schemes an opaque origin. Chromium returns a real tuple origin,
  but only because of our `registerSchemesAsPrivileged` call, which Node knows
  nothing about. `main.js` runs on Node's implementation, so the origin is
  derived from `protocol + "//" + host` instead. Left unfixed, this classified
  every in-app navigation as external and blocked it.
- **A sandboxed preload cannot `require` relative modules.** It gets `electron`
  plus a polyfilled subset of Node built-ins. `preload.js` is therefore
  self-contained, duplicating one constant from `lib/config.js`; a test asserts
  the two stay in sync and that no relative require reappears. Keeping
  `sandbox: true` was preferred over the convenience of sharing the module.
- **`ELECTRON_RUN_AS_NODE` breaks the launch.** VS Code and Cursor set it for the
  processes they host, including integrated terminals. Inherited, it makes the
  Electron binary run as plain Node, so `require("electron")` yields a path
  string and the app dies on the first `protocol` access. All three launchers
  scrub it. This repo ships a VS Code extension, so launching from an integrated
  terminal is a likely path.
- **`app.exit()` does not emit `before-quit`.** Calling it directly skipped
  backend teardown and orphaned uvicorn. Every exit now funnels through a
  `shutdown(code)` helper that reaps the backend first.
- **`titleBarStyle: "hiddenInset"` collides with the app's own header.** The
  NavRail brand mark starts at y=0, so the macOS traffic lights landed on top of
  it. Avoiding that would mean teaching the shared `AppShell` about window
  chrome, for a layout that also ships on the web. A native title bar is correct
  on every platform and costs only a strip of height.

## Targeted fix: one API base URL

Service modules read either `VITE_GEO_API_URL` or `VITE_API_URL` depending on
which file they lived in, so pointing the app at a backend meant setting both.
The desktop app worked only because both defaults happened to be port 8000.

`src/lib/apiBaseUrl.ts` now resolves, most specific first:

1. `window.dogma.apiBaseUrl`, injected by the preload — needed at *runtime*
   because one `frontend/build` artifact serves both surfaces. In production it
   is the `app://dogma/api` proxy; in dev it is `http://127.0.0.1:8000`, using
   the IPv4 loopback rather than `localhost` because uvicorn binds IPv4 and
   `localhost` may resolve to `::1` first and fail to connect.
2. `VITE_API_URL`, then `VITE_GEO_API_URL`.
3. `http://localhost:8000`.

All nine call sites were updated to import it.

## Verification

- `npm run test:electron` — 69 main-process unit tests. Part of `npm test`.
- `npm run test:desktop-smoke` — builds, boots the real app, and asserts the
  React tree mounted, a route change under `app://` re-rendered, an API round
  trip through the proxy succeeded, `window.dogma` is exposed, Node globals are
  *not* reachable from the renderer, Cmd+K opens the palette, and zero console
  errors were logged. It exits through `app.quit()` so the `before-quit` teardown
  is covered too, then fails if a spawned backend outlived the app. Outside
  `check:all` because it needs a display and a populated `.venv`.

  All three boot paths were exercised: **spawn** (clean port, backend reaped on
  quit), **adopt** (a backend started by hand with no CORS configuration at all —
  passes only because of the proxy, and is correctly left running), and **dev**
  (`electron:smoke:dev`, against the Vite server).
- Existing gates unchanged: backend 789 passed / 41 skipped / 3 deselected;
  frontend 226 passed across 51 files (up from 219/50 by the new `apiBaseUrl`
  tests); `check:public-safety` passed; `build:frontend` succeeded.

`npm run typecheck` reports 187 errors. That count is identical at the previous
commit, so it is pre-existing; it is also not part of `check:all`.

## Known limitations

- The app is unpackaged, so macOS shows the menu-bar name as "Electron". Only
  packaging into a real `.app` bundle fixes that; `app.setName()` does not.
- `install:frontend` now also downloads the Electron binary (~100MB).
- Not redistributable: the shell requires this repo and its `.venv`.
- CSP is applied in production only. The Vite dev server needs `eval` for
  react-refresh and a websocket for HMR, and locking those down would break
  `electron:dev` without protecting anything the developer does not control.
  This was originally documented but not *enforced* — the guard now lives inside
  `applyContentSecurityPolicy` so code and comment cannot drift again.
- The proxy buffers request bodies, so a streaming upload would not work. The app
  does not do any; revisit with `duplex: "half"` if that changes.
