# AGENTS.md

Instructions for any coding agent working in this repository, or calling it as a
tool. Claude Code reads `CLAUDE.md` as well; every other agent should read this
file and nothing else is required.

Dogma is a research prototype for **graph-grounded computational biology**. It
keeps a scientific question, the datasets that bear on it, the methods proposed,
and the evidence produced connected to each other, instead of letting an
analysis dissolve into chat history and loose files.

## Using Dogma as a tool

Dogma is designed to be used by other agents, not only worked on. Everything
below runs from a fresh clone with **no install and no virtualenv** — the local
service imports only the Python standard library.

### Over MCP (Cursor, Codex, Zed, Windsurf, Claude Code, any MCP host)

```json
{
  "mcpServers": {
    "dogma": {
      "command": "/absolute/path/to/dogma/bin/dogma",
      "args": ["mcp"]
    }
  }
}
```

Use an absolute path — MCP hosts launch servers from their own working
directory, not yours. This repo's own `.mcp.json` uses `./bin/dogma` because
Claude Code resolves it against the project root.

Six tools, all read-only and all deterministic:

| Tool | Answers |
| --- | --- |
| `create_claim_graph` | What causal claims does this workspace actually assert? |
| `check_method_assumptions` | Are this method's preconditions met, and what is ungrounded? |
| `list_untested_or_stale_claims` | Which edges has nothing measured yet? |
| `attach_evidence` | What evidence records does the workspace support? |
| `record_analysis_run` | What would run, without running it? |
| `export_evidence_bundle` | All of the above as one JSON artifact. |

### Over the shell (agents without MCP)

The same facts, same code path, plain argv and JSON on stdout:

```sh
bin/dogma guardrails <workspace> --format markdown
bin/dogma edge-evaluation-plan <workspace>
bin/dogma evidence-ledger <workspace>
bin/dogma --help
```

If no interpreter is found, set `DOGMA_PYTHON=/path/to/python3`. The launcher
never writes to stdout, so its output is always safe to pipe into a parser.

## The rules that make this domain different

Biology is the domain, and it is the reason for the constraints below. An
analysis that is merely plausible is worse than no analysis, because it is
indistinguishable from a real one downstream. Every rule here exists because the
corresponding failure actually occurred in this repo.

1. **Never present synthetic or fallback output as a real result.** When no LLM
   provider is usable, `/hypothesis/*` returns 503. It does not quietly
   substitute the demo seams. It once did, and answered an ALS question with an
   EGFR/KRAS graph at HTTP 200, labelled as model output, citing a protein
   accession that does not exist. `tests/api/test_no_silent_demo_degradation.py`
   locks this shut; two of its tests are deliberately inverted, so a well-meaning
   revert will look like it is restoring intended behaviour.

2. **Fail closed.** Demo mode requires an explicit `QURATION_PROVIDER=demo`.
   Do not add a catch-all that falls back to it.

   Four providers exist, and two need no API key — they drive a coding-agent
   CLI you are already logged into:

   ```sh
   QURATION_PROVIDER=claude_subscription   # headless `claude -p`
   QURATION_PROVIDER=codex_subscription    # headless `codex exec`
   ANTHROPIC_API_KEY=...                   # metered API
   QURATION_PROVIDER=demo                  # synthetic, offline, clearly labelled
   ```

   Both subscription providers scrub the matching API key from the CLI's
   environment, because a stray `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` would
   silently reroute to metered billing — a failure with no symptom except an
   invoice. **Local, single-operator use only**: serving other users from a
   personal subscription violates the provider's terms.

   `QURATION_PROVIDER` sets the default, not the only option. Several providers
   are live in one process and any request can name one:

   ```sh
   curl localhost:8000/hypothesis/providers          # what this machine can use
   curl -X POST localhost:8000/hypothesis/start \
        -d '{"query":"...","provider":"codex_subscription"}'
   ```

   Each provider gets its own cached loop. The override travels as a copied
   config object and never touches the global — two in-flight requests naming
   different providers is exactly the race this feature invites. A failed build
   is still never cached, per provider: the CLI login can appear between
   requests.

3. **A measurement is not an assessment.** `EvidenceEntry.kind` separates a
   `MEASUREMENT` from a `FEASIBILITY` verdict, and a `MEASUREMENT` must carry
   `PipelineRunProvenance` — meaning a pipeline really ran. A `FEASIBILITY`
   entry must not carry one, because nothing ran. Pydantic enforces both
   directions. Collapsing these is what once let the loop report itself finished
   with every edge "examined" and nothing measured.

4. **No verdicts.** Dogma reports facts: coverage gaps, unmet assumptions,
   missing containers, unpinned versions. It does not emit SUPPORTED/REFUTED and
   it does not emit confidence scores. Tools that return "looks good" are not
   useful to a scientist who has to defend the analysis.

5. **A benchmark number over invented ground truth is not a benchmark number.**
   25 of the bundled tasks are synthetic and 6 come from real published studies.
   `HarnessReport.is_publishable_number` says which you have, and it is
   serialised alongside the score so a consumer cannot take one without the
   other. Use `--published` to score only the grounded tasks, and report `n`.

6. **Keep claims modest.** This is a research prototype, not a clinical,
   diagnostic, or production system. Do not assert production readiness, hosted
   availability, or benchmark superiority.

## Repository rules

- **Do not push, publish a release, or change repository visibility from an
  agent session.** This repo is public; anything pushed here is public
  permanently. Committing locally is fine when asked.
- **Do not read or commit populated `.env` files.** `.env.example` is the
  template.
- Do not commit `.vsix` packages, local databases, screenshots, scratch notes,
  `.vite/` or `.dogma/` output, or benchmark result JSON. Run
  `npm run check:public-safety` rather than re-deriving the list by hand.
- Attribute coding-agent help at the task level and keep human review explicit.
  `PUBLICATION.md` has the standing language.

## Layout

| Path | What it is |
| --- | --- |
| `bin/dogma` | Zero-install launcher — MCP server and CLI. Read its header before changing the boot path. |
| `dogma-local-service/` | The local sidecar (`dogma_service`). Stdlib-only, by design. |
| `src/quration/` | Backend API, graph, epistemics. `quration` is a compatibility namespace, not a second product. |
| `frontend/` | Web workspace. `frontend/electron/` is the desktop shell. |
| `.claude/skills/method-validity/` | Method-validity skill; same kernel the CLI and MCP tools call. |
| `dogma-demo-workspace/` | Synthetic demo files. Safe to point tools at. |
| `docs/decisions/` | Why things are the way they are. Read before reversing one. |

## Checks

On a fresh clone, run the `## Set up the monorepo` steps in `README.md` first,
then keep the venv on PATH (`export PATH="$PWD/.venv/bin:$PATH"`) — the npm
scripts call bare `python`.

```sh
npm run check:public-safety   # tracked-file safety sweep
npm run test:dogma            # extension + local service + skill
npm run test:backend          # pytest
npm run test:frontend         # vitest
npm run test:electron         # Electron main-process suites
npm run check:all             # all of the above plus the frontend build
```

`bin/dogma` itself needs none of that setup — that is the point of it.
