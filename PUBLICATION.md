# Publication Readiness

Status: public repo (released 2026-07-02), a standalone extraction. This is a clean
extraction of the Dogma IDE slice — it does not carry the private research monorepo's
history, scratch notes, benchmark outputs, manuscript files, or deployment config.

## What I built

- Framed the graph-first, IDE-native workflow for computational-biology method guidance.
- Directed the design of the local sidecar (scanning, guardrails, run plans, evidence
  ledger) and the VS Code / Cursor extension surfaces.
- Made the integration and scope decisions, reviewed claims, and own the public framing.

## Where coding agents helped

- Coding agents helped implement and revise the extension, local-service modules, tests,
  and documentation under my direction.
- Agent output was treated as implementation assistance or drafts until reviewed against
  the test suites and the intended workflow.
- AI tools are not authors; responsibility for the published content stays with me.

## Limitations / scope of this repo

- Included: `dogma-vscode-extension/`, `dogma-local-service/`, `dogma-demo-workspace/`,
  `docs/dogma/`, `tools/check-dogma-rename.js`, plus `README`, `LICENSE`, and this file.
- Excluded by design: the legacy research app (dataset curation, web frontend), scratch
  notes, design-history docs, benchmark result bundles, manuscript sources, and any
  deployment / environment config. Those remain in the separate private repository.

## Verification

- 2026-07-02: `dogma-vscode-extension` — `npm test` passed (node test suite, no install).
- 2026-07-02: `dogma-local-service` — `python -m unittest discover -s tests` → 77 tests OK
  (zero runtime dependencies, no install).

## Release

Published 2026-07-02 as the public **Dogma** IDE slice. The broader research
application remains in a separate private repository.
