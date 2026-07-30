# Claude Code Notes

Dogma is a research/prototype workspace for graph-grounded computational biology.
Keep changes scoped and factual.

## Current Shape

- `dogma-vscode-extension/` is the VS Code/Cursor extension.
- `dogma-local-service/` is the local Python sidecar (`dogma_service`, 127.0.0.1:8765).
- `dogma-science-skill/method-validity/` is the Claude Science skill (`SKILL.md` + `kernel.py`).
- `dogma-demo-workspace/` contains synthetic demo bioinformatics files.
- `src/quration/` and `frontend/` are the backend API and web graph surfaces. The
  `quration` Python namespace is a compatibility identifier, not a second product.
- `frontend/electron/` is the Electron main process for the desktop build of
  `frontend/`. It supervises the Python backend (adopting an already-running one
  rather than competing for port 8000) and serves the renderer over a custom
  `app://dogma` scheme so `BrowserRouter` and absolute asset paths work unchanged.
  `electron` is a devDependency of `frontend/`, so that stays the only npm
  install target. Read `frontend/electron/lib/*.js` header comments before
  changing the boot path — several non-obvious constraints are recorded there.
- Desktop API traffic is proxied through `app://dogma/api/*` to the backend, so
  it is same-origin and CORS never applies. Do not "simplify" this back to
  direct `http://127.0.0.1:8000` calls: an adopted backend (one started by
  `npm run dev`) has no `app://dogma` in its allowlist and every request would
  fail preflight. Dev mode is the deliberate exception — Vite serves the page
  from an origin the backend already allows.
- `npm run desktop:package` builds a real `.app` so macOS shows "dogma" rather
  than "Electron" in the menu bar. Three couplings there are load-bearing and
  each has a guard test in `frontend/electron/test/packaging.test.js`:
  `asar` must stay `false` (the `app://` handler uses `net.fetch`, which cannot
  read inside `app.asar`); `electron/after-pack.js` must keep ad-hoc signing the
  bundle (arm64 refuses to exec an invalid signature, silently, exit 0, entry
  point never reached); and `bake-repo-root.js` must run before electron-builder
  so the packaged app can still find the repo's `.venv`.
- The macOS window is frameless. The reserved strip is derived in
  `lib/config.js` from the traffic-light position the shell sets itself, reaches
  the renderer as `--titlebar-inset`, and defaults to `0px` so the shared
  `frontend/` layout is unchanged on the web. Only that strip is draggable, and
  it is empty by construction — do not move the drag region onto the headers, or
  every interactive child needs a `no-drag` opt-out and the next one added
  silently stops working.
- `ELECTRON_RUN_AS_NODE=1` makes the Electron binary a plain Node interpreter, so
  the app cannot open a window. VS Code and Cursor set it for integrated
  terminals — which is where agent sessions run. `lib/env.js` scrubs it in every
  launcher, and `main.js` now refuses to start with an explanation rather than
  exiting 0 in silence. If you launch a packaged bundle by hand, use
  `env -u ELECTRON_RUN_AS_NODE`.

## This Is The Only Maintained Repo

`MIGRATION.md` records the consolidation from the older `manu-tej/quration`
checkout. Do not develop the same change in both places. The old repo is retired
and kept only until a fresh clone of this one is verified.

## Working Rules

- Do not push, publish a release, or change repository visibility from an agent
  session. This repo is public; anything committed here is public once pushed.
- Do not read or commit populated `.env` files. `.env.example` is the template.
- Do not commit generated `.vsix` packages, local databases, screenshots, scratch
  notes, `.vite/` or `.dogma/` output, or benchmark result JSON.
  `npm run check:public-safety` enforces this mechanically — run it, don't
  re-derive it by hand.
- Keep claims modest: this is a research/prototype workspace, not a clinical,
  diagnostic, or production system. Avoid asserting production readiness, hosted
  availability, or benchmark superiority.
- Never present synthetic or fallback output as a real scientific result. The
  public-safety check greps for unlabeled mock-result paths for this reason.
- Attribute coding-agent help at the task level and keep human review and
  responsibility explicit. See `PUBLICATION.md` for the standing language.

## Checks

On a fresh clone, run the `## Set up the monorepo` steps in `README.md` first —
there is no `.venv` yet, and `npm run install:python` / `install:frontend` have
not run.

After that, the npm scripts call bare `python`, so keep the venv on PATH —
otherwise `test:dogma-service` fails with `python: command not found`:

```bash
export PATH="$PWD/.venv/bin:$PATH"
```

```bash
npm run check:public-safety   # tracked-file safety sweep
npm run test:dogma            # extension + local service + method-validity skill
npm run test:backend          # pytest, excludes the integration marker
npm run test:frontend         # vitest
npm run test:electron         # Electron main-process suites (fast, no display)
npm run check:all             # everything above plus the frontend build
git diff --check
```

`npm run test:desktop-smoke` builds and boots the real desktop app, asserting the
renderer mounted, routed under `app://`, kept Node out of the renderer, and that
Cmd+K still reaches the palette. It is deliberately outside `check:all` because
it needs a display and a populated `.venv`. Run it after touching
`frontend/electron/` or anything in the app's boot path.

When iterating on the desktop app, check for orphaned backends with
`pgrep -fl "quration.api.server"`. Every exit path in `main.js` must go through
its `shutdown()` helper: `app.exit()` skips `before-quit`, so calling it directly
leaks the spawned uvicorn. `SIGINT`/`SIGTERM`/`SIGHUP` are wired to `shutdown()`
for the same reason — a signal-killed Electron never emits `before-quit`.

`npm run desktop:package` produces `frontend/dist/mac-arm64/dogma.app`. To launch
it by hand from an agent session or an editor terminal:

```bash
env -u ELECTRON_RUN_AS_NODE ./frontend/dist/mac-arm64/dogma.app/Contents/MacOS/dogma
```

Without `env -u` it exits 0 with no window and no message. Note also that a
packaged bundle's stdout does not reliably reach the launching terminal, so when
debugging one, write to a file rather than trusting `console.log`.

Verified 2026-07-25 from a fresh `git clone` of `master` with no pre-existing
`.venv`, on Python 3.14.3: `check:public-safety` passed (732 files); `test:dogma`
green (extension suites, 77 service tests, 14 skill tests); `test:backend` 789
passed / 41 skipped / 3 deselected; `test:frontend` 219 passed across 50 files;
`build:frontend` succeeded. That closes the fresh-clone gate in `MIGRATION.md`.

Re-verified 2026-07-29 in-place (not a fresh clone) after adding the Electron
desktop shell, on Python 3.12.10 / Node 25.6.1: `check:public-safety` passed (756
files); `test:backend` 789 passed / 41 skipped / 3 deselected, unchanged;
`test:frontend` 226 passed across 51 files, up from 219/50 by the seven new
`apiBaseUrl` tests; `test:electron` 77 passed; `test:dogma` green;
`build:frontend` succeeded. `test:desktop-smoke` passed on all three boot paths:
spawn (backend reaped on quit), adopt (against a hand-started backend with no
CORS configuration, left running), and dev via `electron:smoke:dev`.
`npm run typecheck` fails with 187 errors, but it did so identically at the
previous commit — it is pre-existing and is not part of `check:all`.

Re-verified 2026-07-30 in-place after the frameless title bar, the packaged
bundle and the brand-colour reconciliation: `check:public-safety` passed (769
files); `test:backend` 789 passed / 41 skipped / 3 deselected, unchanged;
`test:frontend` 239 passed across 52 files, up from 226/51 by the thirteen new
`desktopChrome` tests; `test:electron` 106 passed, up from 77 by the `repoRoot`
and `packaging` suites plus the title-bar geometry cases; `build:frontend`
succeeded; `git diff --check` clean. `test:desktop-smoke` passed on all three
boot paths again, and the smoke run now also asserts the brand mark clears the
traffic lights. `desktop:package` produced a bundle whose `Info.plist` carries
`CFBundleName=dogma`, and the running app shows "dogma" in the menu bar.

The title-bar assertion was mutation-tested rather than assumed: forcing the
inset to 0 makes the smoke run fail with `brand mark starts at y=11, underneath
the traffic lights (which end at y=26)`. If you change that layout, check the
assertion still fails when the fix is removed — a passing check that cannot fail
is worse than none.

The extension and the root package have no npm dependencies of their own - the
extension suite is plain `node --check` plus plain node test files - so only
`frontend/` needs `npm ci`. That install now also downloads the Electron binary
(~100MB) because `electron` is a `frontend/` devDependency.

`npm run check:dogma-rename` is vestigial here — it compared a `quration`
checkout against a `dogma` rename target, so in this repo it always reports
"ready". It survives inside `check:dogma` and `check:all`; treat a pass as
meaningless rather than as evidence.
