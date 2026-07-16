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
