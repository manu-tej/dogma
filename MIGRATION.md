# quration → Dogma consolidation

This document records how the earlier quration workspace was consolidated into the
public Dogma repository without creating a second maintained product.

## Source and method

- Source repository: `manu-tej/quration` working checkout.
- Source commit: `0443c283ef1c7ebd37380a56d53572620ca940bd`
  (`fix: harden method-validity skill...`).
- Destination base: `e7bc73f7b7b346db682962a5788f223097d3e400`.
- Destination branch: `codex/unify-dogma-quration` in `manu-tej/dogma`.
- Import method: a file snapshot made from the source commit's Git tree.

Only committed files from that source commit were eligible. The source checkout's dirty
working tree was neither copied nor modified. The histories were not merged: importing a
reviewed snapshot keeps the already-public Dogma history small and avoids carrying old
scratch, deployment, or private material into a public repository.

## Imported

- `src/quration/`
- backend `tests/`, excluding load-test material
- `frontend/`, after the exclusions below
- `.claude/skills/method-validity/` (was `dogma-science-skill/`)
- the root Python and command-orchestration manifests

The destination's existing `dogma-local-service/`, `dogma-vscode-extension/`, synthetic
demo workspace, license, and rename checks remained authoritative and were not replaced
by older copies.

## Excluded

- `.env.production` and all populated environment files
- generated Vite caches and scratch notes
- generated Supabase client/function trees and hosted-project constants
- a stale, unrouted landing page and deployment-specific frontend files
- load-test scripts/results and hard-coded local integration notes
- archives, databases, VSIX packages, screenshots, benchmark JSON, and build output
- every uncommitted source-worktree change

Compatibility identifiers such as the `quration` Python namespace and saved browser keys
remain intentionally. Their presence is not evidence of a second product or repository.

## Cutover rule

Dogma becomes the only maintained repository after this branch is reviewed, merged, and
verified from a fresh clone. Until then, the source repository must not be deleted or
archived. Once the cutover is proven, the old repository can be made read-only with a
short pointer to Dogma; no code should continue to be developed in both places.
