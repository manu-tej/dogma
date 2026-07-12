# Publication Readiness

Status: public repo (released 2026-07-02), a reviewed release artifact extracted from
Dogma's original working repository. This public IDE and local-control slice does not
carry the private repository's history, scratch notes, benchmark outputs, manuscript
files, or deployment config.

## What I built

- Framed the graph-first, IDE-native workflow for computational-biology method guidance.
- Directed the design of the local sidecar (scanning, guardrails, run plans, evidence
  ledger) and the VS Code / Cursor extension surfaces.
- Made the integration and scope decisions, reviewed claims, and own the public framing.

## Where coding agents helped

- Claude Code and Codex helped implement and revise the extension, local-service modules,
  tests, and documentation under my direction.
- Agent output was treated as implementation assistance or drafts until reviewed against
  the test suites and the intended workflow.
- AI tools are not authors; responsibility for the published content stays with me.

## Limitations / scope of this repo

- Included: `dogma-vscode-extension/`, `dogma-local-service/`, `dogma-demo-workspace/`,
  `docs/dogma/`, `tools/check-dogma-rename.js`, plus `README`, `LICENSE`, and this file.
- Excluded by design: Dogma's earlier dataset-curation surfaces and browser graph
  workspace, scratch notes, design-history docs, benchmark result bundles, manuscript
  sources, and any deployment / environment config. Those remain in the original private
  working repository. Its historical `quration` repository/package/API namespace is a
  compatibility detail, not a separate product identity.

## Verification

- 2026-07-11: `dogma-vscode-extension` — `npm test` passed (node test suite, no install).
- 2026-07-11: `dogma-local-service` — `python -m unittest discover -s tests` → 77 tests OK
  (zero runtime dependencies, no install).

## Release

Published 2026-07-02 as the public **Dogma** IDE and local-control slice. The broader
Dogma AI-scientist platform remains in progress in its original private working
repository.
