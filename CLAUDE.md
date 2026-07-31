# Claude Code Notes

Dogma is a research/prototype workspace for graph-grounded computational biology.
Keep changes scoped and factual.

## Current Shape

- `dogma-vscode-extension/` is the VS Code/Cursor extension.
- `dogma-local-service/` is the local Python sidecar (`dogma_service`, 127.0.0.1:8765).
- `bin/dogma` is the zero-install launcher other coding agents use — `bin/dogma mcp`
  for MCP hosts, `bin/dogma <subcommand>` for agents that only run shell commands.
  Read its header before changing it; four constraints there are load-bearing and
  each records an observed failure. The two least obvious: in `mcp` mode **stdout
  is the JSON-RPC channel**, so a single stray `echo` corrupts the session and the
  host reports a protocol error naming neither the shell nor the line; and an
  explicitly set `DOGMA_PYTHON` is honoured or refused, never silently replaced,
  because the fallback chain would otherwise reach the repo `.venv` and look
  healthy on a developer machine while staying broken for every external agent.
  `.mcp.json` previously invoked the service module directly with a bare
  `python -m`, which works only in a venv-activated shell — `python` is not a
  command on stock macOS, and MCP hosts launch servers from their own
  environment. The server never started, which reads to a user as "no biology
  tools" rather than as a misconfiguration.
- `AGENTS.md` is the cross-agent instruction file. Codex, Cursor, Zed, Gemini CLI
  and Aider read it; none of them read this file. When a rule here matters to an
  agent *using* the repo rather than editing it, it belongs in both.
- `.claude/skills/method-validity/` is the method-validity skill (`SKILL.md` +
  `kernel.py`). It lives under `.claude/skills/` so a fresh clone discovers it with
  no copying, and `.claude-plugin/` publishes the same directory as an installable
  plugin — one copy, both channels.
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
  public-safety check greps for fabricated-result literals, but a pass is still
  not proof: it is a text grep and cannot see reachability, so the question "can
  this synthetic value reach a user as a result?" has to be answered by reading
  the fallback paths. It previously carried a `generateMockBio` pattern guarding a
  function that had been deleted, so that rule passed vacuously for however long
  while the demo seams carried a hardcoded fold-change-and-adjusted-p-value pair
  as an edge's `magnitude` (see `hypothesis/orchestrator/demo.py`). If you add a
  pattern, plant a matching string in a non-fixture file and confirm the check
  fails — a denylist entry that matches nothing reads as coverage. Note the rule
  is deliberately strict enough that quoting such a literal in prose trips it;
  describe it instead.
- `PipelineRunProvenance` means a pipeline actually ran, and `EvidenceEntry`
  enforces it: a `MEASUREMENT` must carry one, a `FEASIBILITY` entry must not.
  Registry consultations carry `GroundingProvenance`, which has no `run_id` or
  `data_accession` fields — so there is nothing to fabricate. The methods-graph
  evaluator used to stamp a synthesized run id and the literal string
  `"methods-graph"` where an accession belongs, which made the type's own promise
  unfalsifiable for every consumer downstream. This firewall is the part of the
  epistemics layer that is genuinely hard to copy; it is worth nothing unenforced.
- An edge is `EXAMINED` only if something measured it. `EvidenceEntry.kind`
  distinguishes a `MEASUREMENT` from a `FEASIBILITY` verdict (GROUNDED /
  PARTIALLY_GROUNDED / COVERAGE_GAP / NOT_EVALUABLE), and `rollup_edge` maps
  assessments-only to the `ASSESSED` state. The default is `FEASIBILITY`, because
  every live producer emits assessments — claiming a measurement must be
  deliberate. Do not collapse these back together: doing so is what let the loop
  report itself finished with both edges `examined` and nothing measured. Note the
  demo loop reaches `EXAMINED` while the live loop reaches `ASSESSED`; that
  asymmetry is the real gap, now visible rather than hidden. Rationale and the
  deliberately-unresolved half (which edges the loop should re-propose) are in
  `docs/decisions/2026-07-30-what-a-measurement-may-change-on-an-edge.md`.
  This does not reintroduce verdicts — confidence stays 0.0 and no
  SUPPORTED/REFUTED is emitted, per north-star §2.2.
- Fail closed, never into synthetic content. `/hypothesis/*` returns 503 when no
  LLM provider is usable; demo mode requires an explicit `QURATION_PROVIDER=demo`.
  Do not reintroduce a catch-all that substitutes the demo seams — that is what
  made the engine answer an ALS question with an EGFR/KRAS graph at HTTP 200,
  labelled `proposal_source: "llm"`, with a `UniProt:RESIST` accession that does
  not exist. `tests/api/test_no_silent_demo_degradation.py` locks this down; the
  two `test_provider_failure_*` tests were inverted for the same reason, so a
  "helpful" revert will look like it is restoring intended behaviour.
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
                              # includes test_agent_integration.py, which asserts
                              # bin/dogma works with no venv. Careful there: the
                              # venv's editable install masks a broken PYTHONPATH,
                              # so TestNeedsNoVirtualenv forces a foreign
                              # interpreter — those are the only two cases that
                              # actually fail when the launcher regresses.
npm run test:backend          # pytest, excludes the integration marker
npm run test:frontend         # vitest
npm run test:electron         # Electron main-process suites (fast, no display)
npm run check:all             # everything above plus the frontend build
git diff --check
```

`npm run prove:integration` is the only check that tests the cross-agent claim
from outside. Everything else is written by us, run by our tooling, on a machine
with a populated `.venv` and an editable install — conditions no external agent
has. It clones the current branch into a temp dir, strips the repo's `.venv` from
`PATH`, launches `bin/dogma mcp` from an unrelated directory, speaks the real MCP
handshake including `notifications/initialized` and `notifications/cancelled`,
and asserts the answers describe the clone rather than this checkout.

The `PATH` scrub is the load-bearing part. `npm run install:python`
editable-installs the sidecar, and a setuptools editable install registers a
**meta-path finder**, which Python consults *before* `sys.path` — so a clone
launched with this repo's `.venv` on `PATH` would silently serve this repo's
code and every assertion would pass against the wrong checkout. The script
proves the scrub worked rather than assuming it.

It is outside `check:all` because it clones and is slower than a unit test. Run
it after touching `bin/dogma`, `.mcp.json`, or the sidecar's package layout. It
was mutation-tested: commenting out the launcher's `export PYTHONPATH` makes it
fail with the launcher's own stderr quoted back.

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

Re-verified 2026-07-30 in-place after `bin/dogma` and the cross-agent
integration surface: `check:public-safety` passed (786 files); `test:backend`
900 passed / 41 skipped / 3 deselected, up from 899 by the new
`test_the_declared_command_actually_serves_tools`; `test:dogma-service` 90
passed, up from 77 by `test_agent_integration.py`; `test:dogma-skill` 14;
`test:frontend` 247 across 53 files, unchanged; `test:electron` 106, unchanged;
`git diff --check` clean.

Four mutations were run rather than assumed, and the first two are the reason
this section exists — both initially passed, i.e. the checks were vacuous:

- Removing `export PYTHONPATH` from `bin/dogma` at first failed nothing, because
  `npm run install:python` editable-installs `dogma-local-service` into `.venv`
  and the launcher's fallback chain silently reached it. Fixed in the launcher,
  not the test: an explicit `DOGMA_PYTHON` is now honoured or refused.
- It then still failed nothing under the documented workflow, because
  `export PATH="$PWD/.venv/bin:$PATH"` made the test's own interpreter search
  return the venv copy and skip. `system_python()` now probes for an interpreter
  that genuinely cannot import `dogma_service`, from a neutral cwd — the
  suite runs from `dogma-local-service/`, which otherwise puts the package on
  `sys.path` implicitly and makes every candidate look capable.
- Adding a stray `echo` to `bin/dogma` fails `test_every_stdout_line_is_json_rpc`.
- Reverting `.mcp.json` to a bare `python -m` module invocation fails both
  manifest tests. The old assertion compared the string to itself, so it could
  not fail.

If you touch the launcher, re-run those mutations. On this machine three of the
four regressions are masked by local setup that an external agent does not have.

The extension and the root package have no npm dependencies of their own - the
extension suite is plain `node --check` plus plain node test files - so only
`frontend/` needs `npm ci`. That install now also downloads the Electron binary
(~100MB) because `electron` is a `frontend/` devDependency.

`npm run check:dogma-rename` is vestigial here — it compared a `quration`
checkout against a `dogma` rename target, so in this repo it always reports
"ready". It survives inside `check:dogma` and `check:all`; treat a pass as
meaningless rather than as evidence.
