# Dogma Deliverables

Dogma is the VS Code/Cursor extension and local companion-service layer for bioinformatics. quration remains the graph-native web UI.

## Product Boundary

- Dogma owns the IDE surface: local files, diagnostics, active-editor context, previews, patch review/apply gates, safe run plans, local service lifecycle, and guarded Claude Code subscription calls.
- quration owns the browser product: routed web shell, causal graph canvas, edge/node chat, dataset/method/pipeline pages, graph/evidence persistence, history, event trails, and collaborative hypothesis review.
- methods-graph owns the audited methodology graph: method IDs, assumptions, diagnostics, execution specs, containers, workflow validation, guardrail verdicts, provenance, and advisory suggestions.
- The shared contract is structured artifacts, not duplicated UI: quration-compatible graph/evaluation/evidence handoffs, methods-graph coverage gaps, evidence ledgers, and typed edge evaluation plans.
- Dogma may render scoped graph workbenches inside VS Code, but those views are local editor workbenches for code/workflow action, not a fork of quration's web canvas.

## Current Artifacts

- `dogma-vscode-extension/` - VS Code/Cursor extension scaffold with Inspector, active-file-aware Sidecar, source-jumpable findings, compact bioinformatics workspace state, grouped quration/guardrail/service action lanes, one-command IDE session preparation, IDE readiness preflight, quration backend/canvas plus `/hypothesis` graph API contract preflight, quration graph history refresh from `/hypothesis`, quration graph context pull from `/hypothesis/{graph_id}`, quration `/hypothesis/build` import, persistent `.dogma/quration-import.*`, `.dogma/quration-graphs.*`, and `.dogma/quration-graph.*` records, editor right-click Dogma actions, selection-aware questions, active-file findings review, active-file patch preview/apply gates with methods-graph preflight gaps, persistent status bar state, background rescans, diagnostics, inline service-backed Quick Fixes, graph workbenches, quration handoff export, quration graph UI launch, methods-graph preflight JSON/Markdown reports, one-click active-file review, active-editor-aware assistant actions, Cursor `.mdc` co-scientist handoff rules, trust checks, and local-service lifecycle commands.
- `dogma-local-service/` - dependency-free Python local service with `python3 -m dogma_service`, workspace scan APIs, methods-graph substrate checks, methods-graph guardrail-chain preflight, evidence ledgers, edge evaluation plans, quration-compatible handoff JSON, safe run plans, patch proposal/apply payloads with methods-graph preflight evidence, active-editor-aware agent prompts, and guarded Claude Code subscription adapter.
- `dogma-ide-prototype/` - static browser mock of Dogma VS Code webview interactions, not the quration web UI.
- `dogma-demo-workspace/` - synthetic bioinformatics workspace with intentional validation findings.
- `dogma-0.2.53.vsix` - current local VS Code/Cursor extension package after rebuilding.
- `DOGMA_QURATION_ALIGNMENT.md` - current product-boundary note from the quration subagent inspection.

## Try It

1. Install `dogma-0.2.53.vsix` with `Extensions: Install from VSIX...`.
2. Open `dogma-demo-workspace` in VS Code or Cursor.
3. Run `Dogma: Start Local Service`.
4. Run `Dogma: Scan Workspace` or `Dogma: Scan With Local Service`.
5. Use `Dogma: Prepare IDE Session`, `Dogma: Check IDE Readiness`, `Dogma: Open Local Workflow Guardrails`, `Dogma: Open Local Biological Edge Guardrails`, `Dogma: Generate Agent Handoff`, `Dogma: Generate Edge Evaluation Plan`, `Dogma: Generate quration Handoff`, `Dogma: Check quration Status`, `Dogma: Refresh quration Graph History`, `Dogma: Pull quration Graph Context`, `Dogma: Import Workspace To quration`, `Dogma: Open Last quration Import`, `Dogma: Open quration Canvas From Workspace`, `Dogma: Open quration Graph UI`, `Dogma: Generate Evidence Ledger`, `Dogma: Generate Methods-Graph Preflight`, and `Dogma: Preview Local Service Patch Apply`.

## Manual Service

```bash
cd dogma-local-service
python3 -m dogma_service serve ../dogma-demo-workspace --host 127.0.0.1 --port 8765
```

Use `DOGMA_METHODS_GRAPH_DB` for an audited methods-graph Kuzu database and `DOGMA_LLM_PROVIDER=claude_subscription` for the local Claude Code subscription adapter. Legacy `BIOCURSOR_*` aliases still work for compatibility.
