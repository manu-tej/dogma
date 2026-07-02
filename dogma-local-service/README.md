# Dogma Local Service MVP

This is the local companion-service layer for Dogma. It scans a bioinformatics workspace, extracts domain context, returns structured findings, and exposes JSON endpoints for a future VS Code/Cursor extension integration.

The service is dependency-free Python so it can run before heavier parsers such as htslib, pysam, BioPython, or nf-core schema tooling are added.

## Capabilities

- Workspace scan for common bioinformatics files:
  - sample sheets,
  - BED files,
  - VCF files,
  - metadata JSON,
  - Nextflow workflows,
  - FASTA index files,
  - MultiQC general stats tables,
  - FASTQ structure/QC summaries plus BAM and CRAM inventory.
- Domain findings for:
  - sample sheet required columns,
  - duplicate sample IDs,
  - missing FASTQ pairs,
  - mixed strandedness,
  - BED coordinate and chromosome naming risks,
  - VCF header and record issues,
  - FASTQ malformed-record, invalid-base, and quality-length issues,
  - metadata provenance and privacy gaps,
  - Nextflow sample-sheet validation gaps.
- Assistant-ready context for:
  - samples,
  - conditions,
  - reference build and annotation,
  - workflow process names,
  - contig inventory,
  - QC table shape,
  - FASTQ read/base/GC summaries,
  - risk-level summary.
- Privacy-aware assistant context bundles with raw sample-ID redaction for untrusted human-data workspaces.
- Quration/methods-graph-inspired guardrail reports that keep findings factual, surface method/container coverage gaps, and gate execution on dry-run/trust/validation state.
- Factual evidence ledger reports that record observations, guardrails, proposals, and execution gates without support/refute verdicts or confidence grades.
- Biological graph reports that expose measurable biological edges as planning units and ground them through methods-graph when an audited Kuzu substrate is available.
- Edge evaluation plans that turn a workspace into a typed `Readout -> Grounding -> Compose -> Execute -> Interpret` plan without biological verdicts.
- quration handoff artifacts that map Dogma local IDE facts into quration-compatible `CausalGraph`, `EvaluationPlan`, and factual `EvidenceRecord` JSON, with launch/import hints for the quration graph UI.
- Dependency-free MCP stdio server for exposing Dogma as an evidence-control-plane tool provider to MCP hosts such as K-Dense or Claude Desktop.
- Methods-graph substrate reports for audited graph/`ingest.lock.json` configuration and current guardrail contract.
- Methods-graph preflight reports that derive a workspace method chain and dataset facts, then call `methods-graph guardrail-chain --json` when configured.
- Local LLM provider status reports for Claude Code subscription mode and other provider settings.
- Guarded agent suggestions that can include active editor/selection context supplied by the VS Code extension and redacted by the same workspace trust policy.
- Local HTTP API:
  - `GET /health`,
  - `GET /scan`,
  - `GET /context`,
  - `GET /run-plan`,
  - `GET/POST /assistant-context`,
  - `GET/POST /guardrails`,
  - `GET/POST /evidence-ledger`,
  - `GET/POST /edge-evaluation-plan`,
  - `GET/POST /biological-graph`,
  - `GET/POST /methods-graph-substrate`,
  - `GET/POST /methods-graph-preflight`,
  - `GET/POST /llm-status`,
  - `POST /scan` with optional `root` and `max_files`,
  - `POST /run-plan` with optional `root` and `max_files`,
  - `POST /execute` for previewing or explicitly executing an allowlisted dry-run/stub-run command,
  - `GET/POST /patch-proposals`,
  - `POST /apply-patch` for previewing or explicitly applying a proposal,
  - `GET/POST /trust`.

## Run A Scan

From this folder:

```bash
python3 -m dogma_service scan ../dogma-demo-workspace
```

Write JSON to a file:

```bash
python3 -m dogma_service scan ../dogma-demo-workspace --out /tmp/dogma-scan.json
```

## Generate Assistant Context

```bash
python3 -m dogma_service assistant-context ../dogma-demo-workspace --out /tmp/dogma-assistant-context.json
```

Write only the Markdown bundle:

```bash
python3 -m dogma_service assistant-context ../dogma-demo-workspace --format markdown --out /tmp/dogma-assistant-context.md
```

When human data is detected and `.dogma/trust.json` is not trusted, raw sample identifiers are replaced with stable aliases such as `<sample:1>` in the context, findings, Markdown, and prompt templates.

## Generate Method Guardrails

```bash
python3 -m dogma_service guardrails ../dogma-demo-workspace --format markdown --out /tmp/dogma-method-guardrails.md
python3 -m dogma_service methods-graph-preflight ../dogma-demo-workspace --format markdown --out /tmp/dogma-methods-graph-preflight.md
```

This report imports the quration philosophy and methods-graph guardrails into Dogma: graph/chat drive the same workflow substrate, findings are factual ledger entries instead of support/refute verdicts, missing method/container contracts are explicit coverage gaps, and any real execution path stays behind dry-run, trust, and validation gates.

## Generate Evidence And Substrate Reports

```bash
python3 -m dogma_service evidence-ledger ../dogma-demo-workspace --format markdown --out /tmp/dogma-evidence-ledger.md
python3 -m dogma_service biological-graph ../dogma-demo-workspace --format markdown --out /tmp/dogma-biological-graph.md
python3 -m dogma_service edge-evaluation-plan ../dogma-demo-workspace --format markdown --out /tmp/dogma-edge-evaluation-plan.md
python3 -m dogma_service edge-evaluation-plan ../dogma-demo-workspace --format markdown --selected-edge-json '{"id":"pipeline.nf:FASTQC->ALIGN_STAR:1","from":"FASTQC","to":"ALIGN_STAR","title":"FASTQC -> ALIGN_STAR","status":"gap","facts":{"fromMethod":"m:fastqc (sequencing quality control)","toMethod":"m:star (splice-aware RNA-seq alignment)","missingContainers":["FASTQC","ALIGN_STAR"]}}' --out /tmp/dogma-selected-edge-plan.md
python3 -m dogma_service quration-handoff ../dogma-demo-workspace --out /tmp/dogma-quration-handoff.json
python3 -m dogma_service methods-graph-substrate --format markdown --out /tmp/dogma-methods-graph-substrate.md
python3 -m dogma_service llm-status --format markdown --out /tmp/dogma-llm-status.md
```

The biological graph is the bridge between graph UI and execution: it records measurable biological edges such as condition contrast -> transcript abundance, methods-graph grounding status, workflow/reference coverage gaps, and a selected-edge payload that can seed an edge evaluation plan. When an audited methods-graph Kuzu database is configured, Dogma calls `seed_from_edge`, `expand`, and `method_preconditions` read-only; otherwise it records configuration, dependency, seed, suggestion, or query gaps instead of pretending grounding happened.

The edge evaluation plan records the inferred biological question or selected edge, readout, methods-graph grounding status, workflow composition gaps, selected-edge method/container gaps, dry-run execution gates, and facts-only interpretation contract.

The quration handoff is the boundary artifact between Dogma and the graph web UI. It keeps quration as the canonical graph product while exporting Dogma's local workspace facts as quration-shaped graph, plan, and evidence-record JSON. The artifact includes `quration_import` with the default frontend/API URLs, expected `.dogma/quration-handoff.*` paths, and an explicit `handoff_ready_import_endpoint_not_present` status until quration exposes a direct import endpoint.

## Run The MCP Server

Dogma can run as a local MCP stdio server:

```bash
python3 -m dogma_service mcp
```

The MCP adapter exposes these tools:

- `create_claim_graph`
- `record_analysis_run`
- `attach_evidence`
- `list_untested_or_stale_claims`
- `check_method_assumptions`
- `export_evidence_bundle`

Each tool takes a `root` argument pointing at the workspace to inspect. The adapter is intentionally facts-only: it wraps the same deterministic local-service builders used by the CLI/API, does not execute workflows, and does not create support/refute verdicts or confidence grades.

Use `DOGMA_METHODS_GRAPH_DB` or `QURATION_METHODS_GRAPH_DB` to point Dogma at an audited methods-graph Kuzu database. Dogma expects the database to be paired with `ingest.lock.json`; otherwise the report records a configuration gap rather than pretending the graph is authoritative. Set `DOGMA_METHODS_GRAPH_DATASET_FORMAT` to override the dataset seed passed to methods-graph; by default sample-sheet/FASTQ workspaces seed `fmt:format_1930`. The local Python environment also needs the methods-graph `kuzu==0.11.3` dependency for live grounding.

For Claude Code subscription mode, set `DOGMA_LLM_PROVIDER=claude_subscription` and optionally `DOGMA_CLAUDE_CLI_PATH`, `DOGMA_CLAUDE_MODEL`, and `DOGMA_LLM_TIMEOUT_SECONDS`. If `DOGMA_CLAUDE_CLI_PATH` is `claude`, Dogma checks the service PATH plus common macOS developer locations such as `~/.local/bin`, `/opt/homebrew/bin`, and `/usr/local/bin`, then records all attempted paths in the LLM status artifact. This is a local-only adapter pattern: the LLM proposes typed decisions, while the Python service owns redaction, guardrails, and whitelisted actions.

Legacy `BIOCURSOR_*` env vars and `python3 -m biocursor_service` remain compatibility aliases, but new configuration should use `DOGMA_*` and `python3 -m dogma_service`.

## Generate A Safe Run Plan

```bash
python3 -m dogma_service run-plan ../dogma-demo-workspace
```

Preview the first allowlisted dry-run/stub-run command without executing it:

```bash
python3 -m dogma_service execute ../dogma-demo-workspace
```

Execution is intentionally gated. A command only runs when you pass `--execute`, the command is allowlisted as a dry-run/stub-run, the workflow tool is available, and the workspace has no error-level Dogma findings.

Human-data workspaces add another gate: execution is blocked until `.dogma/trust.json` explicitly allows local operations.

## Generate Patch Proposals

```bash
python3 -m dogma_service patch-proposals ../dogma-demo-workspace
```

Preview the first proposal application without mutating files:

```bash
python3 -m dogma_service apply-patch ../dogma-demo-workspace
```

Patch application is also explicitly gated. A proposal is applied only when you pass `--apply`; otherwise the service returns the selected diff and target metadata for review.

Patch application is also blocked for detected human-data workspaces until `.dogma/trust.json` is present and trusted.

Current proposal types:

- Nextflow sample-sheet row validation before tuple creation.
- Metadata `samples.sample_id_policy` insertion for missing sample identifier policy findings.

## Trust A Workspace

Check trust status:

```bash
python3 -m dogma_service trust-status ../dogma-demo-workspace
```

Write `.dogma/trust.json` after you have reviewed the workspace and decided local operations are appropriate:

```bash
python3 -m dogma_service trust-workspace ../dogma-demo-workspace --reason "Reviewed local demo workspace"
```

## Run The Local API

```bash
python3 -m dogma_service serve ../dogma-demo-workspace --host 127.0.0.1 --port 8765
```

Then query it:

```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/scan
curl -s http://127.0.0.1:8765/context
curl -s http://127.0.0.1:8765/run-plan
curl -s http://127.0.0.1:8765/assistant-context
curl -s http://127.0.0.1:8765/guardrails
curl -s http://127.0.0.1:8765/evidence-ledger
curl -s http://127.0.0.1:8765/edge-evaluation-plan
curl -s http://127.0.0.1:8765/biological-graph
curl -s -X POST http://127.0.0.1:8765/edge-evaluation-plan -H 'Content-Type: application/json' -d '{"root":"../dogma-demo-workspace","selected_edge":{"id":"pipeline.nf:FASTQC->ALIGN_STAR:1","from":"FASTQC","to":"ALIGN_STAR","title":"FASTQC -> ALIGN_STAR","facts":{"missingContainers":["FASTQC","ALIGN_STAR"]}}}'
curl -s http://127.0.0.1:8765/methods-graph-substrate
curl -s http://127.0.0.1:8765/llm-status
curl -s http://127.0.0.1:8765/patch-proposals
curl -s http://127.0.0.1:8765/trust
```

## Use From The Extension

Run `Dogma: Start Local Service`, then run `Dogma: Scan With Local Service` in the VS Code/Cursor extension. You can also set `dogma.serviceMode` to `auto` so the normal `Dogma: Scan Workspace` command tries this service and falls back to the in-extension scanner if the service is unavailable.

The extension start command uses these settings:

- `dogma.servicePython`,
- `dogma.serviceModule`,
- `dogma.serviceCwd`,
- `dogma.serviceUrl`,
- `dogma.serviceStartupWaitMs`.

The extension can also request:

- `Dogma: Generate Local Service Assistant Context`,
- `Dogma: Generate Method Guardrails`,
- `Dogma: Generate Evidence Ledger`,
- `Dogma: Generate Edge Evaluation Plan`,
- `Dogma: Generate quration Handoff`,
- `Dogma: Open quration Canvas From Workspace`,
- `Dogma: Open quration Graph UI`,
- `Dogma: Generate Methods-Graph Substrate Report`,
- `Dogma: Generate Methods-Graph Preflight`,
- `Dogma: Check LLM Provider`,
- `Dogma: Generate Local Service Run Plan`,
- `Dogma: Preview Local Service Dry Run`,
- `Dogma: Execute Local Service Dry Run`.
- `Dogma: Generate Local Service Patch Proposals`,
- `Dogma: Preview Local Service Patch Apply`,
- `Dogma: Apply Local Service Patch`.
- `Dogma: Check Workspace Trust`,
- `Dogma: Trust Workspace For Local Operations`.

The execution and patch commands still go through service-side safety and trust gates.

## Test

```bash
python3 -m unittest discover -s tests
```

## MVP Role

This service gives Dogma a real local indexing boundary: the IDE can stay focused on editor UX, diagnostics, and patch application while this process owns domain parsing, safety checks, and assistant-ready workspace facts.
