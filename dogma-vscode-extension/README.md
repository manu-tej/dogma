# Dogma VS Code/Cursor Extension

This is a VS Code/Cursor-compatible extension for a bioinformatics-first IDE and local co-scientist.

It is intentionally dependency-free JavaScript so the core validators can run locally without an install step.

## Product Boundary

Dogma is the shipped, MIT-licensed IDE slice: this VS Code/Cursor extension plus a dependency-light local sidecar. The browser-based graph workspace (quration) is a separate, private repository and owns the canonical graph UI and `/canvas` routes. This extension scans local bioinformatics workspaces, prepares guarded IDE work packages, calls the quration graph and methods-graph contracts, and deep-links into the graph UI instead of duplicating the React Flow graph product inside VS Code.

## Capabilities

- Sidebar views: `Dogma > Sidecar` and `Dogma > Inspector`.
- Active-file Sidecar context showing the current file, language, selection state, file-local finding count, source-jump links, and preview/review actions.
- Sidecar Bioinformatics State cards for samples/conditions, FASTQ read counts, workflow processes, reference/annotation, and local trust gate status.
- Sidecar action lanes for primary IDE work, quration canvas handoff, methods-graph/guardrail artifacts, and local service/trust operations.
- Status bar item showing idle, scanning, blocked, review, ready, or service-offline workspace state.
- Problems panel diagnostics with `Dogma` as the diagnostic source.
- Quick Fix actions for the Nextflow sample-sheet validation warning and service-backed patch proposals.
- Command: `Dogma: Prepare IDE Session`, which starts or verifies the local service, runs a service-backed scan, writes `.dogma/ide-readiness.*`, and writes `.dogma/ide-session.*`.
- Command: `Dogma: Scan Workspace`.
- Command: `Dogma: Scan With Local Service`.
- Command: `Dogma: Check Local Service`.
- Command: `Dogma: Start Local Service`.
- Command: `Dogma: Stop Local Service`.
- Command: `Dogma: Check IDE Readiness`, which writes `.dogma/ide-readiness.*` across local service, trust, Claude, methods-graph, and quration gates.
- Command: `Dogma: Open Assistant`.
- Command: `Dogma: Preview Active Bio File`.
- Command: `Dogma: Generate Context Report`.
- Command: `Dogma: Generate Workflow Graph`.
- Command: `Dogma: Open Local Workflow Guardrails`.
- Command: `Dogma: Open Local Biological Edge Guardrails`.
- Command: `Dogma: Generate Safe Run Plan`.
- Command: `Dogma: Generate Local Service Assistant Context`.
- Command: `Dogma: Generate Method Guardrails`.
- Command: `Dogma: Generate Evidence Ledger`.
- Command: `Dogma: Generate Edge Evaluation Plan`.
- Command: `Dogma: Generate quration Edge Evaluation Plan`, which adapts a pulled quration graph edge into a local Dogma guardrail plan while quration remains the canonical graph UI.
- Command: `Dogma: Fetch quration Edge Plan`, which fetches quration's side-effect-free `/hypothesis/{graph_id}/edges/{edge_id}/plan` skeleton and writes `.dogma/quration-edge-plan.*`.
- Command: `Dogma: Generate quration Edge Work Package`, which refreshes both quration and Dogma edge-plan artifacts and writes one agent-ready `.dogma/quration-edge-work-package.*` bundle.
- Command: `Dogma: Suggest From quration Edge Work Package`, which sends the generated work-package Markdown through the guarded local agent path and writes `.dogma/quration-edge-agent-suggestion.md`.
- Command: `Dogma: Preview quration Edge Suggested Patch`, which uses the edge-package suggestion's first `patch_preview` proposal and opens Dogma's review-first patch preview without applying it.
- Command: `Dogma: Apply quration Edge Suggested Patch`, which previews the same suggested proposal first, then applies it only after explicit confirmation and trust checks.
- Command: `Dogma: Generate quration Handoff`.
- Command: `Dogma: Check quration Status`, which checks quration backend/canvas reachability plus the `/hypothesis` graph API contract and writes `.dogma/quration-status.*`.
- Command: `Dogma: Refresh quration Graph History`, which reads quration `/hypothesis`, writes `.dogma/quration-graphs.*`, and can open the newest graph in quration.
- Command: `Dogma: Pull quration Graph Context`, which fetches the last imported or newest quration graph and writes `.dogma/quration-graph.*`.
- Command: `Dogma: Import Workspace To quration`, which posts the Dogma seed graph to quration `/hypothesis/build` and opens `/canvas/<graphId>`.
- Command: `Dogma: Open Last quration Import`, which reopens the graph recorded in `.dogma/quration-import.json`.
- Command: `Dogma: Open quration Canvas From Workspace`.
- Command: `Dogma: Open quration Graph UI`.
- Command: `Dogma: Generate Methods-Graph Substrate Report`.
- Command: `Dogma: Generate Methods-Graph Preflight`.
- Command: `Dogma: Check LLM Provider`.
- Command: `Dogma: Generate Local Service Run Plan`.
- Command: `Dogma: Generate Agent Suggestion`, which includes the active editor path, cursor line, and selected text when available.
- Command: `Dogma: Generate Agent Handoff`, which refreshes methods-graph preflight when possible, then writes `.dogma/agent-handoff.json`, `.dogma/agent-handoff.md`, and `.cursor/rules/dogma-bioinformatics.mdc` so Cursor or another coding agent inherits Dogma and methods-graph guardrails.
- Command: `Dogma: Review Active File`, which sends the current file or selection through the guarded local agent path and writes `.dogma/active-file-review.md`.
- Command: `Dogma: Ask About Selection`, which asks a custom question about the selected text or current line and writes `.dogma/selection-question.md`.
- Command: `Dogma: Review Active Finding`, which reviews the current-line Dogma finding or first finding in the active file and writes `.dogma/active-finding-review.md`.
- Command: `Dogma: Open Finding`, which opens the file and line for a Sidecar finding inside the editor.
- Command: `Dogma: Preview Local Service Dry Run`.
- Command: `Dogma: Execute Local Service Dry Run`.
- Command: `Dogma: Generate Local Service Patch Proposals`.
- Command: `Dogma: Preview Local Service Patch Apply`.
- Command: `Dogma: Preview Active File Patch`.
- Command: `Dogma: Apply Active File Patch`.
- Command: `Dogma: Apply Local Service Patch`.
- Command: `Dogma: Check Workspace Trust`.
- Command: `Dogma: Trust Workspace For Local Operations`.
- Command: `Dogma: Apply Sample Sheet Validation Patch`.
- Workspace scanning for:
  - `sample_sheet.csv` and `samples.csv`,
  - compressed sample sheets, BED, VCF, GTF, GFF, and FASTQ files when using the local service,
  - `*.bed`,
  - `*.vcf`,
  - `*.gtf`, `*.gff`, and `*.gff3`,
  - `*.fastq` and `*.fq`,
  - `*.fai` FASTA indexes,
  - `multiqc_general_stats.txt`,
  - `metadata.json` and `project.json`,
  - `*.nf` and `nextflow.config`.
- Background rescans after candidate bioinformatics files are saved; routine refreshes update diagnostics and the status bar without toast notifications.
- Active file previews for:
  - sample sheets and other CSV files,
  - BED intervals,
  - VCF variants,
  - GTF/GFF annotation features,
  - FASTQ read summaries,
  - JSON metadata.
- Active-file findings in the Sidecar, including current-file issue list, source jumps, and review/patch actions.
- Selection-aware Dogma questions from the Sidecar or command palette, routed through the guarded local agent path.
- Editor right-click menu entries for Dogma selection, finding, active-file preview, and active-file patch workflows.
- Domain warnings for:
  - missing sample sheet columns,
  - duplicate sample IDs,
  - missing FASTQ pairs,
  - mixed strandedness,
  - BED coordinate errors,
  - mixed chromosome naming,
  - VCF header and record issues,
  - FASTQ malformed-record, invalid-base, and quality-length issues,
  - metadata provenance gaps,
  - Nextflow sample sheet validation gaps.
- Assistant-ready workspace context:
  - sample counts,
  - conditions and strandedness,
  - reference build and annotation,
  - workflow, BED, and VCF file inventory,
  - Nextflow process/call graph summaries,
  - Markdown context report at `.dogma/context-report.md`.
- Workflow graph export:
  - Mermaid workflow diagram at `.dogma/workflow-graph.md`,
  - process, channel, call, and inferred-edge tables,
  - conservative call-order edges for review before workflow changes.
- Interactive local workflow guardrail workbench:
  - command `Dogma: Open Local Workflow Guardrails`,
  - selectable workflow edges inside a webview,
  - edge dossier with method grounding, container coverage, blockers, assumptions, and next actions,
  - selected-edge action to generate `.dogma/edge-evaluation-plan.md`,
  - quration-style policy that edges are factual work items, not support/refute verdicts.
- Local biological edge guardrail workbench:
  - command `Dogma: Open Local Biological Edge Guardrails`,
  - service-backed biological nodes and edges for measurable questions,
  - selected biological edge action to generate `.dogma/edge-evaluation-plan.md`,
  - read-only methods-graph grounding status, suggestions, precondition diagnostics, and explicit workflow/reference/contrast coverage gaps.
- Privacy-aware local-service assistant context:
  - Markdown bundle at `.dogma/service-assistant-context.md`,
  - sample-ID redaction for untrusted human-data workspaces,
  - task prompts for review, debug, patch, and synthetic-test planning.
- Quration/methods-graph-inspired guardrails:
  - Markdown bundle at `.dogma/method-guardrails.md`,
  - factual ledger posture instead of support/refute verdicts,
  - explicit method-contract, container, trust, dry-run, and coverage-gap checks.
- Factual evidence ledger and substrate reports:
  - Markdown bundle at `.dogma/evidence-ledger.md`,
  - typed edge evaluation plan at `.dogma/edge-evaluation-plan.md`,
  - methods-graph substrate report at `.dogma/methods-graph-substrate.md`,
  - methods-graph guardrail-chain preflight at `.dogma/methods-graph-preflight.json` and `.dogma/methods-graph-preflight.md`,
  - local LLM provider status at `.dogma/llm-provider-status.md`.
- Interactive assistant actions:
  - copy AI-ready context prompt,
  - scan with the local companion service,
  - write `.dogma/synthetic-test-plan.md`,
  - generate context report,
  - generate `.dogma/workflow-graph.md`,
  - open the graph workbench,
  - open the biological graph workbench,
  - generate `.dogma/run-plan.md`,
  - generate `.dogma/service-assistant-context.md`,
  - generate `.dogma/method-guardrails.md`,
  - generate `.dogma/evidence-ledger.md`,
  - generate `.dogma/edge-evaluation-plan.md`,
  - generate `.dogma/quration-handoff.json`,
  - generate `.dogma/methods-graph-substrate.md`,
  - generate `.dogma/llm-provider-status.md`,
  - generate `.dogma/service-run-plan.md`,
  - review the current file or selection into `.dogma/active-file-review.md`,
  - generate `.dogma/patch-proposals.md`,
  - preview patch proposals scoped to the active file,
  - apply active-file patch proposals after diff preview and trust confirmation,
  - generate `.dogma/trust-status.md`,
  - apply the sample validation patch.

## Try The Validator Logic

```bash
npm test
```

or without npm:

```bash
node test/domainValidators.test.js
```

## Try In VS Code Or Cursor

Open this folder in VS Code or Cursor, then run:

```bash
code --extensionDevelopmentPath="$(pwd)"
```

If you are launching from Cursor and its command-line launcher is installed, use the equivalent Cursor launcher command with the same `--extensionDevelopmentPath` argument.

In the extension development host, open a bioinformatics workspace and run `Dogma: Scan Workspace`.

The scan populates both the Dogma Inspector sidebar and the editor Problems panel. Saving a candidate file such as `sample_sheet.csv`, `*.bed`, `*.vcf`, `*.gtf`, `*.gff3`, or `*.nf` triggers another scan.

For the Nextflow workflow warning, use the editor Quick Fix menu or run `Dogma: Apply Sample Sheet Validation Patch`. When diagnostics correspond to local-service patch proposals, the Quick Fix menu can also open the service diff preview or apply the reviewed proposal through Dogma's trust gates.

Open `Dogma: Open Assistant` after scanning to use the context-aware assistant actions. `Copy AI Context Prompt` places a grounded prompt on the clipboard for use with an AI coding assistant.

When the local service is running, `Dogma: Generate Local Service Assistant Context` writes `.dogma/service-assistant-context.md`. For detected human-data workspaces that are not trusted, the service redacts raw sample identifiers before producing Markdown or prompt templates.

Open a sample sheet, BED, VCF, GTF/GFF, or metadata JSON file and run `Dogma: Preview Active Bio File` to get a table-style preview beside the editor.

Run `Dogma: Generate Safe Run Plan` to write `.dogma/run-plan.md`. It lists manual dry-run/stub-run commands and blocks real execution guidance when error-level findings remain.

Run `Dogma: Generate Workflow Graph` to write `.dogma/workflow-graph.md`. It includes a Mermaid diagram and tables for Nextflow processes, channels, calls, and inferred call-order edges.

Run `Dogma: Open Local Workflow Guardrails` to inspect the same workflow graph interactively. Select an edge to view the edge dossier: grounded method IDs where known, missing method/container coverage gaps, current Dogma blockers, assumptions, and safe next actions. From the selected edge, use `Generate Edge Evaluation Plan` to send that selected edge to the local service and write a typed plan artifact scoped to the edge.

Run `Dogma: Open Local Biological Edge Guardrails` to inspect service-backed biological edges such as declared condition contrast -> transcript abundance. Select a biological edge and use `Generate Evaluation Plan` to preserve that biological question, readout, methods-graph grounding status, method candidates, precondition diagnostics, and coverage gaps in `.dogma/edge-evaluation-plan.md`.

## Use The Local Service

Start the companion service from the extension:

```text
Dogma: Start Local Service
```

The default service settings use `dogma.serviceCwd = auto`. In an installed VSIX, Dogma starts the bundled `python-service` copy first; in this generated output layout it can also fall back to sibling `dogma-local-service` folders. You can also start it from a terminal:

```bash
cd ../dogma-local-service
python3 -m dogma_service serve ../dogma-demo-workspace --host 127.0.0.1 --port 8765
```

Then run `Dogma: Scan With Local Service` from VS Code or Cursor.

Optional settings:

- `dogma.serviceMode`: `auto`, `off`, or `required`. The default `auto` starts or reuses the bundled local service for user-triggered scans and falls back to the in-extension scanner when the sidecar is unavailable.
- `dogma.serviceUrl`: defaults to `http://127.0.0.1:8765`.
- `dogma.serviceTimeoutMs`: defaults to `2000`.
- `dogma.executionTimeoutSeconds`: defaults to `30`.
- `dogma.servicePython`: defaults to `python3`.
- `dogma.serviceModule`: defaults to `dogma_service`; `biocursor_service` remains a compatibility alias.
- `dogma.serviceCwd`: defaults to `auto`, preferring the bundled VSIX `python-service`, sibling/dev service folders, then the workspace Python environment.
- `dogma.serviceStartupWaitMs`: defaults to `5000`.
- `dogma.qurationUrl`: defaults to `http://localhost:3000/canvas`.
- `dogma.qurationApiUrl`: defaults to `http://localhost:8000`.
- `dogma.qurationTimeoutMs`: defaults to `5000`.

`off` uses the in-extension scanner. `auto` starts or reuses the local service for user-triggered scans, keeps background scans quiet, and falls back to the in-extension scanner when the service is unavailable. `required` treats an unavailable local service as a scan failure.

For assistant context:

- `Dogma: Prepare IDE Session` starts or verifies the local service, runs a service-backed workspace scan, writes `.dogma/ide-readiness.json`, `.dogma/ide-readiness.md`, `.dogma/ide-session.json`, and `.dogma/ide-session.md`, and records the boundary that Dogma is the VS Code/Cursor IDE surface while quration remains the graph web UI.
- `Dogma: Check IDE Readiness` writes `.dogma/ide-readiness.json` and `.dogma/ide-readiness.md`, a single readiness gate for local service reachability, workspace trust, Claude Code subscription readiness, methods-graph preflight, and quration import readiness.
- `Dogma: Generate Local Service Assistant Context` writes `.dogma/service-assistant-context.md`.
- `Dogma: Generate Agent Handoff` refreshes `.dogma/methods-graph-preflight.json/md` when the local service is reachable, then writes `.dogma/agent-handoff.json`, `.dogma/agent-handoff.md`, and `.cursor/rules/dogma-bioinformatics.mdc`. The Cursor rule file makes concrete methods-graph coverage gaps, Dogma trust gates, quration graph ownership, dry-run execution policy, and no-biological-verdict constraints durable for Cursor or another coding agent.
- `Dogma: Generate Agent Suggestion`, `Dogma: Review Active File`, and quration-edge agent suggestions route through the local sidecar prompt, which includes the current methods-graph preflight status, method IDs, dataset facts, coverage gaps, and preflight next actions.
- The bundle includes workspace facts, findings, trust status, redaction status, indexed files, and task prompts.
- Raw sample IDs are replaced with stable aliases when human data is detected and `.dogma/trust.json` does not explicitly allow local operations.

For method guardrails:

- `Dogma: Generate Method Guardrails` writes `.dogma/method-guardrails.md`.
- The report follows the quration/methods-graph stance: findings are facts rather than verdicts, method grounding is a safety rail, missing method/container contracts are coverage gaps, and execution remains dry-run/trust-gated until validation passes.
- `Dogma: Generate Evidence Ledger` writes `.dogma/evidence-ledger.md`, a factual ledger of workspace observations, findings, guardrail checks, patch proposals, and execution gates.
- `Dogma: Open Local Biological Edge Guardrails` opens a service-backed biological edge workbench whose selected biological edge can seed `.dogma/edge-evaluation-plan.md`. If an audited methods-graph Kuzu database and the `kuzu` Python dependency are available, the service calls methods-graph read-only for seeds, suggestions, chosen methods, and preconditions; otherwise the workbench shows the grounding gap.
- `Dogma: Generate Edge Evaluation Plan` writes `.dogma/edge-evaluation-plan.md`, a typed `Readout -> Grounding -> Compose -> Execute -> Interpret` plan. From the Graph Workbench or Biological Graph action, the selected edge is preserved in the service request and the generated plan records its method/container/data coverage gaps.
- `Dogma: Generate quration Edge Evaluation Plan` reads `.dogma/quration-graph.json` or pulls the newest quration graph, selects a quration edge, sends that selected biological edge to the local service, and writes `.dogma/quration-edge-evaluation-plan.json` plus `.dogma/quration-edge-evaluation-plan.md`. This keeps Dogma as the editor-side guardrail adapter and quration as the graph-native web UI.
- `Dogma: Fetch quration Edge Plan` reads `.dogma/quration-graph.json` or pulls the newest quration graph, selects a quration edge, calls quration's side-effect-free `/hypothesis/{graph_id}/edges/{edge_id}/plan`, and writes `.dogma/quration-edge-plan.json` plus `.dogma/quration-edge-plan.md`. This is quration's canonical edge plan skeleton; `resolve` remains a separate evidence-writing quration operation.
- `Dogma: Generate quration Edge Work Package` refreshes both `.dogma/quration-edge-plan.*` and `.dogma/quration-edge-evaluation-plan.*`, then writes `.dogma/quration-edge-work-package.json` and `.dogma/quration-edge-work-package.md` as the single IDE-side work unit for an agent or human to inspect before proposing workflow/code changes.
- `Dogma: Suggest From quration Edge Work Package` regenerates the work package, passes its Markdown as redacted editor context through the local service's guarded agent-suggestion route, and writes `.dogma/quration-edge-agent-suggestion.md`. Claude Code subscription mode stays behind the Python sidecar: no tool access, no automatic patch application, and no biological verdicts.
- `Dogma: Preview quration Edge Suggested Patch` regenerates the work package, asks the guarded agent path for the next action, writes `.dogma/quration-edge-agent-suggestion.md`, then previews the first `patch_preview` proposal with Dogma's existing patch diff flow. It does not mutate workspace files.
- `Dogma: Apply quration Edge Suggested Patch` follows the same edge-package suggestion path, opens the diff preview first, then applies the selected proposal only after explicit confirmation and workspace trust checks. It never resolves quration evidence or emits biological verdicts.
- `Dogma: Generate quration Handoff` writes `.dogma/quration-handoff.json` and `.dogma/quration-handoff.md`, a quration-compatible `CausalGraph`, `EvaluationPlan`, and factual `EvidenceRecord` handoff for the graph-native web UI.
- `Dogma: Check quration Status` writes `.dogma/quration-status.json` and `.dogma/quration-status.md`, confirming whether the configured quration backend API, canonical canvas, and `/hypothesis` graph API contract are reachable before import.
- `Dogma: Refresh quration Graph History` writes `.dogma/quration-graphs.json` and `.dogma/quration-graphs.md`, reading quration's saved graph summaries from `/hypothesis` and linking each graph back to the canonical quration canvas.
- `Dogma: Pull quration Graph Context` writes `.dogma/quration-graph.json` and `.dogma/quration-graph.md`, fetching the last imported or newest quration graph from `/hypothesis/{graph_id}` and summarizing its nodes, edges, edge states, validation states, and proposed tests for local IDE work.
- `Dogma: Import Workspace To quration` writes `.dogma/quration-handoff.json`, converts the graph to a quration `SeedSkeleton`, posts it to `dogma.qurationApiUrl` `/hypothesis/build`, writes `.dogma/quration-import.json` and `.dogma/quration-import.md`, and opens the saved graph in `dogma.qurationUrl`.
- `Dogma: Open Last quration Import` reopens the saved graph URL from `.dogma/quration-import.json`.
- `Dogma: Open quration Canvas From Workspace` generates the handoff, extracts the workspace-derived graph query, and opens quration at `/canvas?q=...`.
- `Dogma: Open quration Graph UI` opens `dogma.qurationUrl` (default `http://localhost:3000/canvas`) so the sidecar stays an IDE surface while quration remains the canonical graph canvas.
- `Dogma: Generate Methods-Graph Substrate Report` writes `.dogma/methods-graph-substrate.md`, showing whether an audited methods-graph database and `ingest.lock.json` are configured and how Dogma should use the current methods-graph surface.
- `Dogma: Generate Methods-Graph Preflight` writes `.dogma/methods-graph-preflight.json` and `.dogma/methods-graph-preflight.md`, deriving a workflow method chain and dataset facts, then calling `methods-graph guardrail-chain --json` when `DOGMA_METHODS_GRAPH_DB` and `DOGMA_METHODS_GRAPH_CLI` are configured. Missing graph/CLI/runtime support is reported as a preflight gap, not a pass.
- `Dogma: Check LLM Provider` writes `.dogma/llm-provider-status.md`. Claude Code subscription mode is treated as local-only: tools disabled, no session persistence, and Python-owned biomedical actions.

For execution safety:

- `Dogma: Generate Local Service Run Plan` writes `.dogma/service-run-plan.md`.
- `Dogma: Preview Local Service Dry Run` writes `.dogma/service-execution-preview.md` without running workflow tools.
- `Dogma: Execute Local Service Dry Run` asks for confirmation and then asks the local service to run the first allowed dry-run/stub-run command.
- The service blocks execution when error-level Dogma findings remain.
- The service also blocks execution when human data is detected and `.dogma/trust.json` is missing or does not allow local operations.

For patch proposals:

- `Dogma: Generate Local Service Patch Proposals` writes `.dogma/patch-proposals.md`.
- `Dogma: Preview Local Service Patch Apply` lets you choose a proposal, then writes `.dogma/patch-apply-preview.md` without mutating workflow files.
- `Dogma: Preview Active File Patch` filters service proposals to the current editor file and opens the matching diff preview.
- `Dogma: Apply Active File Patch` filters service proposals to the current editor file, opens the diff preview first, then applies only after explicit confirmation and workspace trust checks.
- `Dogma: Apply Local Service Patch` lets you choose a proposal, asks for confirmation, then asks the local service to apply that proposal.
- The current service proposals cover Nextflow sample-sheet row validation and metadata sample identifier policy insertion.
- Patch application is blocked for detected human-data workspaces until the workspace trust policy is explicit.

For privacy/trust:

- `Dogma: Check Workspace Trust` writes `.dogma/trust-status.md`.
- `Dogma: Trust Workspace For Local Operations` asks for confirmation, then writes `.dogma/trust.json` through the local service.
- Trust is scoped to the current workspace only.

## Build A Local VSIX

The extension includes a dependency-free local packager for quick installation tests:

```bash
npm run package:vsix
```

That writes `../dogma-0.2.34.vsix`.

Install it from VS Code or Cursor with `Extensions: Install from VSIX...`, then choose the generated VSIX file.

## Demo Workspace

A synthetic demo workspace is included next to this extension at `../dogma-demo-workspace`.

Use it to verify the user flow:

1. Launch the extension development host.
2. Open `dogma-demo-workspace`.
3. Run `Dogma: Start Local Service`.
4. Run `Dogma: Check Workspace Trust`.
5. Run `Dogma: Prepare IDE Session`, or run `Dogma: Scan Workspace` / `Dogma: Scan With Local Service` for a narrower scan-only check.
6. Confirm the Dogma Inspector, Problems panel, and Sidecar finding `Open` buttons show the expected domain findings and jump to source lines.
7. Run `Dogma: Generate Context Report` to write `.dogma/context-report.md`.
8. Run `Dogma: Generate Workflow Graph` to write `.dogma/workflow-graph.md`.
9. Run `Dogma: Open Local Workflow Guardrails` to select workflow edges, inspect edge dossiers, and generate an edge evaluation plan from the selected edge.
10. Run `Dogma: Open Local Biological Edge Guardrails` to select biological edges, inspect readout/method/coverage facts, and generate an edge evaluation plan from the selected biological edge.
11. Run `Dogma: Generate Safe Run Plan` to write `.dogma/run-plan.md`.
12. Run `Dogma: Generate Local Service Assistant Context` to write `.dogma/service-assistant-context.md`.
13. Run `Dogma: Generate Agent Handoff` to write `.dogma/agent-handoff.*` and `.cursor/rules/dogma-bioinformatics.mdc`.
14. Run `Dogma: Generate Method Guardrails` to write `.dogma/method-guardrails.md`.
15. Run `Dogma: Generate Evidence Ledger` to write `.dogma/evidence-ledger.md`.
16. Run `Dogma: Generate Edge Evaluation Plan` to write `.dogma/edge-evaluation-plan.md`.
17. Run `Dogma: Generate quration Handoff` to write `.dogma/quration-handoff.json` and `.dogma/quration-handoff.md`, run `Dogma: Check quration Status`, then use `Dogma: Import Workspace To quration` when quration's backend and web UI are running. Use `Dogma: Open Last quration Import` to return to the recorded graph later.
18. Run `Dogma: Pull quration Graph Context`, then `Dogma: Generate quration Edge Work Package` to write `.dogma/quration-edge-work-package.json` and `.dogma/quration-edge-work-package.md` plus its quration/Dogma source artifacts.
19. Run `Dogma: Suggest From quration Edge Work Package` to write `.dogma/quration-edge-agent-suggestion.md` through the guarded local Claude Code adapter when configured, or as a prompt-ready artifact when LLM use is disabled.
19. Run `Dogma: Preview quration Edge Suggested Patch` to open a review-first diff for the first `patch_preview` action from the edge-package suggestion.
20. Run `Dogma: Apply quration Edge Suggested Patch` only after reviewing the diff; Dogma will ask for explicit confirmation and enforce trust gates before mutating files.
21. Optionally run `Dogma: Fetch quration Edge Plan` or `Dogma: Generate quration Edge Evaluation Plan` separately when you only need one side of the edge package.
22. Run `Dogma: Check IDE Readiness`, `Dogma: Generate Methods-Graph Substrate Report`, `Dogma: Generate Methods-Graph Preflight`, and `Dogma: Check LLM Provider` to inspect guardrail and local Claude Code provider configuration.
23. Open `Dogma: Open Assistant`, then use `Copy AI Context Prompt` or `Write Synthetic Test Plan`.
24. Open `sample_sheet.csv`, `intervals.bed`, `variants.vcf`, `genes.gtf`, or `metadata.json` and run `Dogma: Preview Active Bio File`.

## MVP Direction

This extension is the practical bridge between the static Dogma prototype and a real IDE:

- keep the familiar VS Code/Cursor editor surface,
- add domain-aware bioinformatics scanning,
- add assistant panels grounded in parsed workspace facts,
- generate AI-ready context prompts from parsed workspace facts,
- generate workflow graph reports from parsed Nextflow structure,
- open an interactive graph workbench where selected workflow edges show method grounding and coverage gaps,
- open a biological graph workbench where selected biological edges seed typed EvaluationPlans,
- generate privacy-aware local-service assistant context bundles,
- generate quration/methods-graph-inspired method guardrail reports,
- generate typed edge evaluation plans from workspace context, a selected workflow edge, or a selected biological edge,
- generate quration-compatible graph/evaluation/evidence handoff JSON for the web UI,
- fetch quration's canonical side-effect-free edge plan skeleton from the graph API into local `.dogma/` artifacts,
- generate quration-edge evaluation plans by consuming quration graph context as editor-side guardrail input rather than duplicating the quration canvas,
- generate an agent-ready quration edge work package that combines quration's canonical edge skeleton with Dogma's local guardrails,
- ask the guarded local Claude Code adapter for a next-action suggestion scoped to that quration edge work package,
- preview the first patch proposal recommended from that quration edge package without mutating files,
- apply the reviewed quration-edge patch proposal through explicit confirmation and trust-gated local service patch application,
- prepare the IDE session in one command by starting/verifying the service, scanning, and writing readiness/session reports,
- check quration backend/canvas readiness and required `/hypothesis` graph API endpoints from the VS Code sidecar before handoff import,
- read quration graph history from `/hypothesis`, write `.dogma/quration-graphs.*`, and open saved graphs in the canonical quration canvas,
- pull a quration graph from `/hypothesis/{graph_id}` into `.dogma/quration-graph.*` for edge-aware local IDE context,
- check IDE readiness across local service, trust, Claude Code, methods-graph, and quration gates,
- import the workspace-derived seed graph into quration through `/hypothesis/build`, record `.dogma/quration-import.*`, and reopen the saved canvas,
- generate factual evidence ledgers, methods-graph substrate reports, and methods-graph preflight reports,
- check local-only Claude Code subscription provider readiness through the service,
- send redacted active-editor selection context into guarded Dogma agent suggestions,
- ask custom questions about the current selection or line from the editor Sidecar,
- use right-click editor context menu actions for selection questions, finding review, active-file review, previews, and patch gates,
- review the active file or selection with the guarded local Claude Code adapter,
- jump from Sidecar findings to source files and review the active Dogma finding directly from the Sidecar/editor context,
- preview common bioinformatics data files inside the editor,
- generate reviewable safe run plans instead of executing workflows implicitly,
- request local-service dry-run/stub-run plans with explicit execution gating,
- request service-generated workflow and metadata patch proposals with explicit apply gating,
- preview active-file patch proposals directly from the editor Sidecar,
- apply active-file patch proposals only after opening the diff and passing trust gates,
- use inline Quick Fix preview/apply actions for matching local-service patch proposals,
- keep a persistent status bar signal for scan, review, blocked, ready, and service-offline states,
- enforce a local workspace trust policy for human-data operations,
- start and stop the local companion service from the command palette,
- create reusable workspace context reports for AI handoff,
- apply narrow workflow-safe patches through editor workspace edits,
- connect to the included local companion service for heavier parsing and sandboxed execution.

## Local Service Integration

The output set includes `../dogma-local-service`, a dependency-free Python indexer API. Run it with:

```bash
cd ../dogma-local-service
python3 -m dogma_service serve ../dogma-demo-workspace --host 127.0.0.1 --port 8765
```

The extension can start the service with `Dogma: Start Local Service`, call it through `Dogma: Scan With Local Service`, or use it automatically when `dogma.serviceMode` is set to `auto` or `required`.
