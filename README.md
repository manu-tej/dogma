# Dogma

Dogma is a research prototype for graph-grounded computational biology. It keeps
scientific questions, datasets, methods, planned computations, and resulting evidence
connected instead of treating an analysis as an unstructured chat or a pile of files.

This is the canonical Dogma monorepo. The browser workspace that was developed in the
`quration` repository now lives here alongside the VS Code / Cursor extension, local
Python sidecar, Claude Science skill, and synthetic demo workspace. The Python import
and API namespace remains `quration` temporarily so existing artifacts and integrations
do not break; it is not a second product that needs a second repository.

## What Dogma does today

- The web workspace represents hypotheses, evidence, and typed graph edges and includes
  dataset-search and method-planning surfaces.
- The Python backend provides the graph, search, broker, analysis, persistence, and API
  implementation used by that workspace.
- The local sidecar scans a bioinformatics workspace, generates method guardrails and
  selected-edge evaluation plans, prepares reviewable dry-run or stub-run commands,
  proposes patches, and writes evidence-ledger artifacts.
- The VS Code / Cursor extension exposes those local capabilities where the analysis
  files live.
- The Claude Science method-validity skill calls the same deterministic local kernel,
  so Claude can inspect a proposed method without inventing a separate reasoning path.

## Causal graph-based execution: current boundary

The intended loop is:

```text
typed hypothesis edge
  -> evidence and method checks
  -> edge evaluation work package
  -> human review
  -> allowlisted local dry-run/stub-run
  -> evidence ledger and graph update
```

The repository contains the graph workspace, evaluation-plan contracts, guarded local
execution primitives, and evidence-ledger machinery needed for that loop. It does **not**
yet provide a fully closed, autonomous selected-edge-to-result pipeline. In particular,
the final graph-bound orchestration and result write-back still need to be joined and
tested end to end. Dogma should currently be described as a review-first planning and
local-control prototype, not as an autonomous causal execution engine.

## Repository map

- `src/quration/` — Dogma's Python backend under its compatibility namespace.
- `frontend/` — browser graph and research workspace.
- `frontend/electron/` — Electron main process for the desktop build of that workspace.
- `dogma-local-service/` — dependency-light local sidecar and guarded execution layer.
- `dogma-vscode-extension/` — VS Code / Cursor interface.
- `dogma-science-skill/` — Claude Science method-validity skill.
- `dogma-demo-workspace/` — synthetic FASTQ, VCF, BED, GTF, sample-sheet, and Nextflow
  fixtures.
- `tests/` — backend tests; each other runnable component keeps its tests beside it.
- `MIGRATION.md` — provenance and exclusions for the quration-to-Dogma consolidation.

## Set up the monorepo

Use Python 3.10 or newer and Node.js 20. Create an isolated Python environment, then
install the backend, sidecar, and frontend dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
npm run install:all
```

For local configuration, copy `.env.example` to `.env` and fill in only the providers
you intend to use. Never commit `.env`.

Run the browser workspace and backend together:

```bash
npm run dev
```

Run the sidecar against the synthetic workspace:

```bash
npm run dev:dogma-service
```

The extension can be opened in a development host with `npm run dev:dogma-vscode` or
`npm run dev:dogma-cursor`.

## Run the workspace as a desktop app

The same `frontend/` surface also runs as an Electron desktop app. The Electron shell
supervises the Python backend itself, so there is no second terminal to manage:

```bash
npm run build:frontend   # the packaged shell serves frontend/build
npm run desktop
```

For hot reload against the Vite dev server instead:

```bash
npm run dev:desktop
```

What the shell does on launch:

- Probes `http://127.0.0.1:8000`. If a backend is already answering — because
  `npm run dev:backend` is running in another terminal — it **adopts** that one rather
  than starting a competing process, and leaves it running on quit.
- Otherwise spawns `uvicorn` from `.venv` and reaps it on quit. A startup failure is
  reported with the interpreter's own output, not just "could not start".
- Shows a splash with progress until the backend answers, so the window is never blank.

Readiness is judged by `/openapi.json`, not `/health`: `/health` is a Kubernetes-style
probe that depends on Postgres and Redis, neither of which this workspace requires, so
gating on it would stop the app from ever opening. When those dependencies are absent the
shell logs a note and continues — features needing them surface their own errors.

The renderer is served over a custom `app://dogma` scheme rather than `file://`, which
keeps client-side routing and asset paths working unchanged.

On macOS the window is frameless (`titleBarStyle: "hiddenInset"`), so the app draws its
own header the whole width of the window. The shell pins the traffic lights to a known
position and passes the height of the strip they occupy to the renderer, which publishes
it as the `--titlebar-inset` custom property; the NavRail header and TopBar both grow by
that much. The property defaults to `0px`, so the same `frontend/build` output lays out
unchanged in a browser and on platforms that keep a native title bar. Only that strip is
draggable — it is empty by construction, so no control needs a drag opt-out.

API calls go through `app://dogma/api/…`, which the main process proxies to the backend.
Because that is same-origin from the page's point of view, CORS never applies — so the
desktop app works against a backend no matter how it was started. This matters for the
adopt case: `npm run dev` starts uvicorn without `app://dogma` in its allowlist, and
before the proxy existed the app would open but every request failed preflight.

Desktop-specific checks:

```bash
npm run test:electron        # main-process unit suites (fast, no display needed)
npm run test:desktop-smoke   # builds, boots the real app, asserts it rendered
```

The smoke run adapts to whichever backend path it takes. With nothing on port 8000 it
exercises spawn-and-reap and fails if a backend outlives the app; with one already
running it exercises adopt and skips the no-orphan assertion, since that process is not
the app's to kill.

`test:electron` is part of `npm test`. The smoke run is kept separate because it needs a
display and a working `.venv`. Note that `install:frontend` now also downloads Electron's
binary (~100MB) and electron-builder.

### Build a real .app bundle

`npm run desktop` runs unpackaged, which means macOS reads the menu-bar name from
Electron's own bundle and shows "Electron". The menu name comes from `CFBundleName` in the
running bundle's `Info.plist` — `app.setName()` cannot change it — so showing "dogma" needs
a real bundle:

```bash
npm run desktop:package   # -> frontend/dist/mac-arm64/dogma.app
npm run desktop:icon      # regenerate the .icns from assets/icon.svg (rarely needed)
```

The result is **not distributable**. It is unsigned beyond an ad-hoc signature, so
Gatekeeper will block it for anyone who did not build it, and it still runs the backend out
of this repo's `.venv` — it needs the checkout on disk. Three things about that are worth
knowing before changing the packaging:

- **Ad-hoc signing is mandatory on Apple Silicon.** Electron's binary arrives
  linker-signed with a seal over its original bundle; renaming it and rewriting
  `Info.plist` invalidates that seal, and arm64 refuses to exec an invalid signature —
  silently, with exit status 0 and the entry point never reached. `electron/after-pack.js`
  re-signs ad-hoc and then verifies, so a broken signature fails the build instead of
  producing an app that does nothing.
- **`asar` is disabled deliberately.** The `app://` handler serves the renderer with
  `net.fetch(pathToFileURL(...))`, which goes through Chromium's network stack. Electron's
  asar support is an `fs`-layer shim, so a `file://` URL pointing inside `app.asar` does not
  resolve and every asset 404s. Re-enabling asar means either unpacking the build output or
  rewriting the handler to read with `fs` and set MIME types itself.
- **The repo path is baked in at package time.** `electron/bake-repo-root.js` records the
  checkout location so the packaged app can find `.venv`; `__dirname` is inside the bundle
  and cannot be used. That file is gitignored — it is machine-specific, and
  `check:public-safety` rejects tracked files containing a developer-local absolute path.
  If the repo moves after packaging, set `DOGMA_REPO_ROOT`, or let the app prompt for the
  new location (it remembers the answer).

One environment trap, worth knowing because it fails invisibly: with
`ELECTRON_RUN_AS_NODE=1` set, the Electron binary behaves as a plain Node interpreter and
cannot open a window. VS Code and Cursor set it for their integrated terminals. All the npm
scripts scrub it, and launching from Finder or the Dock is unaffected, but running the
packaged binary directly from such a terminal hits it. The app now refuses to start with an
explanation rather than exiting silently.

## Verification

The component checks can be run together:

```bash
npm run check:all
```

This covers the backend, frontend, extension, sidecar, Claude Science skill, frontend
production build, rename compatibility, and public-safety preflight. Backend Ruff and
frontend TypeScript strict checking are not release gates yet; the migrated legacy
surfaces need a separate cleanup pass before those checks can honestly be enabled.

The required gate excludes tests that contact live external archives. Run those
separately, when network access is intentional, with `npm run test:backend:integration`.

## Compatibility names

The following historical identifiers are retained deliberately:

- the Python distribution, imports, and CLI named `quration`;
- existing quration API fields, extension command IDs, environment variables, local
  storage keys, and `.dogma/quration-*` artifacts;
- `biocursor_service`, the sidecar implementation package, with `dogma_service` as its
  public compatibility alias.

These names should be migrated with explicit compatibility tests, not by a bulk rename.

## Status and responsibility

Dogma is research/prototype software. It is not a clinical, regulatory, or production
bioinformatics system. Method suggestions, graph edges, generated commands, patches, and
evidence records require human review; demo inputs are synthetic unless stated otherwise.

Claude Code and Codex helped implement and revise parts of the code, tests, migration,
and documentation. Manu Arrojwala directed the product and scientific framing, workflow
design, integration decisions, claim review, and publication decisions, and remains
responsible for the repository.

MIT licensed. See [`LICENSE`](LICENSE).
