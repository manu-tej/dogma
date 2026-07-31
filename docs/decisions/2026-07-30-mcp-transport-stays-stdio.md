# The MCP server stays stdio

Status: **decided** — `.mcp.json` added; no HTTP transport will be built.

Date: 2026-07-30

## The claim this examines

A capability review listed "HTTP transport on the MCP server" as table stakes, on
the basis that Claude Science requires HTTP-wrapped MCP servers. It flagged that
claim as third-party-reported rather than sourced from Anthropic documentation, and
recommended verifying before committing effort.

Verified. The premise is half right, and for this server it is the wrong half.

## What the documentation actually says

**Claude Code treats stdio as a first-class transport, and describes it as the
right one for tools like this.** From the Claude Code MCP reference:

> ### Option 3: Add a local stdio server
> Stdio servers run as local processes on your machine. **They're ideal for tools
> that need direct system access or custom scripts.**

and, listing what it supports:

> **Multiple transport types**: support for stdio, SSE, HTTP, and WebSocket
> transports

**The HTTP requirement is real, but it applies to a different channel.** For
claude.ai custom connectors and the Directory, the server must be remote:

> Remote MCP servers must be publicly exposed through HTTP (supporting both
> Streamable HTTP and SSE transports), while local STDIO servers cannot be
> connected directly.

> Your MCP server must be reachable over the public internet from Anthropic's IP
> ranges.

So: HTTP is required to publish a **hosted service** as a connector. stdio is
correct for a **local tool**.

## Why stdio is right for this server

`dogma-local-service` is a local-workspace tool. Its six tools
(`create_claim_graph`, `record_analysis_run`, `attach_evidence`,
`list_untested_or_stale_claims`, `check_method_assumptions`,
`export_evidence_bundle`) scan a bioinformatics workspace on disk, prepare guarded
dry-run commands, and write evidence artifacts locally. It is precisely the "needs
direct system access" case the documentation points at stdio for.

Wrapping it in HTTP would mean making a tool that reads local files and prepares
commands reachable from the public internet, and doing so is what the connector
channel requires — not an incidental detail. That is a security regression sold as
a distribution win. The data it operates on is local; the tool should be too.

If a hosted Dogma service ever exists, *that* is what would warrant an HTTP MCP
server, and it would be a different server with a different threat model — not this
one re-plumbed.

## What was actually missing

Not the transport. The server had no registration at all: `dogma-service mcp` has
existed and works — a real JSON-RPC handshake returns
`{"name": "dogma-evidence-control-plane", "version": "0.1.0"}` and lists all six
tools — but nothing pointed Claude Code at it, so no clone could use it. That is the
same gap the method-validity skill had, and it is fixed the same way: a checked-in
`.mcp.json` at the repo root.

## How you know it worked

`tests/test_distribution_manifests.py` asserts `.mcp.json` parses, declares the
stdio transport, and names a command that exists. A fresh clone gets the server
registered without manual configuration.

## What this does not claim

That the skill or the server is *published*. Submitting to the Directory is a
separate decision with a separate review, and it is a decision for a human — the
repo's standing rule is that an agent session does not publish. This note only
settles which transport the local server should use, and records that the answer is
"the one it already has".
