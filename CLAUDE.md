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

The npm scripts call bare `python`, so put the venv on PATH first — otherwise
`test:dogma-service` fails with `python: command not found`:

```bash
export PATH="$PWD/.venv/bin:$PATH"
```

```bash
npm run check:public-safety   # tracked-file safety sweep
npm run test:dogma            # extension + local service + method-validity skill
npm run test:backend          # pytest, excludes the integration marker
npm run test:frontend         # vitest
npm run check:all             # everything above plus the frontend build
git diff --check
```

Verified 2026-07-25 on `codex/unify-dogma-quration`: public-safety passed
(731 files); `test:dogma` green (extension suites, 77 service tests, 14 skill
tests); `test:backend` 789 passed / 41 skipped / 3 deselected; frontend build
untested in that run.

`npm run check:dogma-rename` is vestigial here — it compared a `quration`
checkout against a `dogma` rename target, so in this repo it always reports
"ready". It survives inside `check:dogma` and `check:all`; treat a pass as
meaningless rather than as evidence.
