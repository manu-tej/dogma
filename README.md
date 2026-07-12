# Dogma

Dogma is an in-progress AI-scientist platform for computational biology. It connects
scientific questions, data, methods, execution, and evidence through graph-grounded
workflows. This public release brings that approach into the IDE: it scans a
bioinformatics workspace, applies local guardrails and method checks, keeps an evidence
ledger, and proposes reviewable patches through a VS Code / Cursor extension backed by
a dependency-light local sidecar.

This repository is the reviewed, MIT-licensed **Dogma IDE and local-control slice**. The
browser graph workspace and earlier data-curation and analysis surfaces remain in Dogma's
original working repository, whose repository, Python-package, and API namespace is
`quration` for historical reasons. They are parts of the same Dogma project, not a separate
product.

## What's here

- `dogma-vscode-extension/` — the VS Code / Cursor extension: commands, views, diagnostics,
  patch proposals, and IDE surfaces.
- `dogma-local-service/` — the local sidecar (Python, zero runtime dependencies): workspace
  scanning, method guardrails, run plans, evidence ledgers, and a stable graph-handoff
  contract.
- `dogma-demo-workspace/` — synthetic FASTQ / VCF / BED / GTF / sample-sheet / Nextflow
  fixtures for safe, reproducible checks.
- `tools/check-dogma-rename.js` — rename-safety preflight.

### Legacy identifiers

`quration` was Dogma's original working name. Existing `quration` command IDs, settings,
environment variables, API fields, and `.dogma/quration-*` filenames remain unchanged for
compatibility; in this repository they refer to Dogma's browser graph workspace and graph
handoff contract. They do not denote a separate product. Renaming those identifiers is out
of scope for this reviewed release because it would break existing integrations and saved
artifacts.

Inside `dogma-local-service/`, the sidecar's implementation package is still named
`biocursor_service/` for backward compatibility while `dogma_service` is a thin alias that
re-exports it — this naming is retained deliberately, since a full package rename carries
more risk than its marginal benefit.

## Status

Working prototype. Not a clinical, regulatory, or production bioinformatics system —
method recommendations and graph-grounding outputs need human review, and demo fixtures
are synthetic unless documented otherwise. MIT licensed.

## What I built

- The graph-first workspace concept: computational-biology hypotheses, evidence paths,
  and method checks surfaced where the analysis actually happens.
- A local sidecar that indexes bioinformatics workspaces and emits guardrails, run plans,
  evidence ledgers, and patch proposals.
- A VS Code / Cursor extension exposing those capabilities in an IDE workflow.
- Synthetic demo fixtures for reproducible checks.

## Where coding agents helped

Claude Code and Codex helped implement and revise the extension surfaces, local-service
modules, tests, and documentation. I directed the product and scientific framing, the
workflow design, integration decisions, review of claims, and the final publication
choices. AI tools are not authors; responsibility for the content here stays with me.

## Getting started

Local sidecar (Python 3, no dependencies to install):

```bash
cd dogma-local-service
python -m unittest discover -s tests      # 77 tests
```

VS Code / Cursor extension (no dependencies to install):

```bash
cd dogma-vscode-extension
npm test                                   # node-based test suite
```

Point the extension at `dogma-demo-workspace/` for a safe, synthetic run.

## Verification

Last run on the current public branch (2026-07-11):

- `dogma-vscode-extension` — `npm test` passed (full node test suite, including demo
  workspace, local-service client, and VSIX-package checks).
- `dogma-local-service` — `python -m unittest discover -s tests` passed: 77 tests OK.

## Limitations

Research / prototype code. No hosted service is implied. The `methods_graph` grounding
path is optional and degrades gracefully when the broader research package is absent.

## License

MIT. See [`LICENSE`](LICENSE).
