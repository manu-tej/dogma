# Using Dogma from another coding agent

Dogma is meant to be called by whatever agent you already use, not to replace it.
The same deterministic kernel is reachable three ways — MCP, shell, and (for
Claude Code) a skill — and all three run the same code.

Nothing here needs an install. `bin/dogma` exports the one path variable the
service needs and the service itself imports only the Python standard library,
so a fresh `git clone` is enough. If you have run `npm run install:python` it
will use the repo `.venv` instead; either way the tools behave identically.

Replace `/abs/path/to/dogma` below with the absolute path to your clone. Use an
absolute path: MCP hosts launch servers from their own working directory, and a
relative one resolves against a directory you did not choose.

## Verify it works first

```sh
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | /abs/path/to/dogma/bin/dogma mcp
```

You should get one line of JSON listing six tools. If you get nothing, the
launcher prints the reason to stderr — it never fails silently. If you need a
specific interpreter, set `DOGMA_PYTHON=/path/to/python3`; that choice is
honoured or refused, never quietly swapped.

## Cursor

`~/.cursor/mcp.json` for every project, or `.cursor/mcp.json` inside one:

```json
{
  "mcpServers": {
    "dogma": {
      "command": "/abs/path/to/dogma/bin/dogma",
      "args": ["mcp"]
    }
  }
}
```

## Codex CLI

`~/.codex/config.toml`:

```toml
[mcp_servers.dogma]
command = "/abs/path/to/dogma/bin/dogma"
args = ["mcp"]
```

Codex also reads `AGENTS.md`, so working *inside* the repo needs no setup at all.

## Claude Code

Already configured — the repo's `.mcp.json` is picked up automatically, and
`.claude/skills/method-validity/` is discovered on clone. To use Dogma's tools
while working in a *different* project:

```sh
claude mcp add dogma -- /abs/path/to/dogma/bin/dogma mcp
```

## Zed

`settings.json`:

```json
{
  "context_servers": {
    "dogma": {
      "command": { "path": "/abs/path/to/dogma/bin/dogma", "args": ["mcp"] }
    }
  }
}
```

## Windsurf

`~/.codeium/windsurf/mcp_config.json`, same shape as Cursor's.

## VS Code

`.vscode/mcp.json`:

```json
{
  "servers": {
    "dogma": {
      "type": "stdio",
      "command": "/abs/path/to/dogma/bin/dogma",
      "args": ["mcp"]
    }
  }
}
```

There is also a VS Code / Cursor extension in `dogma-vscode-extension/` that
exposes the local capabilities directly where the analysis files are.

## Agents with no MCP support

Anything that can run a shell command can use Dogma. Output is JSON on stdout;
diagnostics never appear there.

```sh
bin/dogma guardrails <workspace>                      # method contracts, gaps, containers
bin/dogma guardrails <workspace> --format markdown    # same, human-readable
bin/dogma edge-evaluation-plan <workspace>            # how one claim could be measured
bin/dogma evidence-ledger <workspace>                 # what the workspace actually supports
bin/dogma run-plan <workspace>                        # what would run, without running it
bin/dogma --help                                      # all subcommands
```

Point them at `dogma-demo-workspace/` to see the output shape against synthetic
files before using a real one.

## What the tools will and will not tell you

**All six MCP tools are read-only and deterministic**, and none of them call a
model. An MCP host cannot make Dogma change your workspace.

**The CLI is not read-only.** Two subcommands act, and both are preview-by-default
behind an explicit flag — but an agent that can compose shell commands can supply
that flag, so do not treat `bin/dogma` as inert:

| Subcommand | Without the flag | With it |
| --- | --- | --- |
| `execute` | prints the selected command | `--execute` runs it (`subprocess.run`) |
| `apply-patch` | prints the diff | `--apply` writes the file |

Both are additionally gated by the trust policy (`.dogma/trust.json`) and an
allowlist restricted to dry-run and stub-run invocations, so `execute` cannot
launch a real pipeline. That is a narrower guarantee than "read-only", and the
distinction is the one that matters if you are granting an agent shell access.

They report **facts**: which workflow steps have a grounded method contract,
which are coverage gaps, which containers are unpinned, which assumptions are
unmet, which claims nothing has measured yet.

They do not report **verdicts**. There is no SUPPORTED/REFUTED, no pass/fail
grade, and no confidence score, because a tool that says "looks good" is no help
to someone who has to defend the analysis. The `record_analysis_run` tool
(`bin/dogma run-plan` on the CLI) returns a plan with `"executed": false`; it is
not a record that anything ran.

If you are wiring Dogma into an agent loop, the useful shape is: call
`check_method_assumptions` **before** proposing a method, and
`list_untested_or_stale_claims` **before** reporting a conclusion. Both answer
questions a model cannot answer about itself.
