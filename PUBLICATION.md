# Publication Readiness

Status: **local consolidation candidate; not yet published from this branch**.

The public `master` branch was released on 2026-07-02 as the reviewed Dogma IDE and
local-control slice. This branch broadens that repository into the canonical monorepo by
adding a committed snapshot of the earlier quration backend, web workspace, tests, and
Claude Science skill. It must pass the full clean-clone and public-safety review before a
merge or release decision.

## Consolidation scope

Included in the candidate:

- the existing public extension, local sidecar, and synthetic demo workspace;
- `src/quration/` and backend tests, retaining the namespace for compatibility;
- the browser graph workspace in `frontend/`;
- the Claude Science method-validity skill;
- unified setup, verification, CI, and migration documentation.

Excluded deliberately:

- populated environment files and deployment configuration;
- generated Supabase code and hosted-project identifiers;
- local databases, generated VSIX packages, build output, caches, and screenshots;
- scratch notes, load-test output, benchmark result bundles, and manuscript sources;
- the source repository's uncommitted working-tree changes and Git history.

See [`MIGRATION.md`](MIGRATION.md) for the exact source commit and cutover rules.

## Claim boundary

The merged code supports graph-grounded planning, selected-edge work packages, guarded
local dry-run/stub-run execution, and evidence-ledger generation. It does not yet close
the entire selected causal edge → execution → result write-back loop. Public descriptions
must remain at research/prototype level and must not imply clinical use, production
reliability, or autonomous scientific validation.

## Attribution and review

Claude Code and Codex provided task-level implementation and documentation assistance.
Agent output remains subject to human review; AI tools are not authors. Manu Arrojwala
owns the scientific framing, integration decisions, claim review, publication decision,
and repository responsibility.

## Release gate

Before this branch is merged or published:

1. Run `npm run check:all` from a clean environment.
2. Verify a non-editable `dogma-local-service` install from outside the checkout.
3. Inspect the staged file list and public-safety report manually.
4. Confirm no source-repository working-tree changes or private history were imported.
5. Merge Dogma first; archive the old quration repository only after the merged repo can
   be cloned, installed, and tested independently.
