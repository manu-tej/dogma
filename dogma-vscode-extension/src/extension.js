"use strict";

const vscode = require("vscode");
const { validateFiles } = require("./domainValidators");
const { diagnosticEntries, isCandidatePath } = require("./diagnosticModel");
const { codeActionDescriptors } = require("./codeActions");
const { applySampleValidationPatchText } = require("./sampleValidationPatch");
const { extractWorkspaceContext, renderContextHtml, renderContextReport } = require("./workspaceContext");
const { extractWorkflowGraphs } = require("./workflowGraph");
const { renderWorkflowGraphReport } = require("./workflowGraphReport");
const { buildAssistantPrompt, buildSyntheticTestPlan } = require("./assistantPrompts");
const { renderPreviewHtml } = require("./bioFilePreview");
const { renderRunPlan } = require("./runPlan");
const {
  applyPatchWithLocalService,
  checkLocalService,
  executeWithLocalService,
  getAgentSuggestionWithLocalService,
  getAssistantContextWithLocalService,
  getBiologicalGraphWithLocalService,
  getEdgeEvaluationPlanWithLocalService,
  getEvidenceLedgerWithLocalService,
  getLlmStatusWithLocalService,
  getMethodGuardrailsWithLocalService,
  getMethodsGraphPreflightWithLocalService,
  getMethodsGraphSubstrateWithLocalService,
  getPatchProposalsWithLocalService,
  getQurationHandoffWithLocalService,
  getRunPlanWithLocalService,
  getTrustStatusWithLocalService,
  scanWithLocalService,
  trustWorkspaceWithLocalService
} = require("./localServiceClient");
const { renderExecutionResult, renderServiceRunPlan } = require("./serviceRunPlan");
const { renderPatchApplyResult, renderPatchProposals } = require("./patchProposals");
const { proposalQuickPickItems, selectedProposalId } = require("./patchSelection");
const { activeFilePatchProposals } = require("./activePatchSelection");
const { ServiceProcessManager } = require("./serviceProcessManager");
const { renderTrustStatus, renderTrustWriteResult } = require("./trustPolicy");
const { renderServiceAssistantContext } = require("./serviceAssistantContext");
const { renderMethodGuardrails } = require("./methodGuardrails");
const { renderEvidenceLedger } = require("./evidenceLedger");
const { renderMethodsGraphPreflight } = require("./methodsGraphPreflight");
const { renderMethodsGraphSubstrate } = require("./methodsGraphSubstrate");
const { renderLlmProviderStatus } = require("./llmProviderStatus");
const { buildIdeReadinessReport, renderIdeReadiness } = require("./ideReadiness");
const { buildIdeSessionReport, renderIdeSession } = require("./ideSession");
const { buildGraphWorkbenchModel, renderGraphWorkbenchHtml } = require("./graphWorkbench");
const { renderBiologicalGraphWorkbenchHtml } = require("./biologicalGraphWorkbench");
const { renderEdgeEvaluationPlan } = require("./edgeEvaluationPlan");
const { renderSidecarHtml } = require("./sidecarView");
const { renderAgentSuggestion } = require("./agentSuggestion");
const { renderAgentWorkbenchHtml } = require("./agentWorkbench");
const { buildAgentHandoffRecord, renderAgentHandoffMarkdown, renderCursorRules } = require("./agentHandoff");
const { buildQurationCanvasUrl, buildQurationGraphUrl, DEFAULT_QURATION_CANVAS_URL } = require("./qurationCanvasLink");
const { DEFAULT_QURATION_API_URL, checkQurationConnection, getQurationEdgePlan, getQurationFailedEvents, getQurationGraphEvents, getQurationGraphContext, importQurationHandoff, listQurationGraphs, resolveQurationEdgeReadout } = require("./qurationImportClient");
const { renderQurationConnectionStatus } = require("./qurationConnectionStatus");
const { buildQurationImportRecord, lastQurationGraphUrl, renderQurationImportRecord } = require("./qurationImportRecord");
const { renderQurationGraphHistory } = require("./qurationGraphHistory");
const { renderQurationGraphContext } = require("./qurationGraphContext");
const { renderQurationEvents } = require("./qurationEvents");
const { buildQurationSelectedEdge, pickQurationEdge, qurationEdges, renderQurationEdgeEvaluationPlan } = require("./qurationEdgeEvaluationPlan");
const { renderQurationEdgePlan } = require("./qurationEdgePlan");
const { renderQurationEdgeWorkPackage } = require("./qurationEdgeWorkPackage");
const { buildQurationEdgePatchHandoff, renderQurationEdgePatchHandoff } = require("./qurationEdgePatchHandoff");
const { renderQurationEdgeResolve } = require("./qurationEdgeResolve");
const { buildQurationEdgeQuickPickItems, buildQurationEdgeSelectionRecord, renderQurationEdgeSelection } = require("./qurationEdgeSelection");
const { deriveNextIdeAction } = require("./nextIdeAction");
const { patchDiffDocumentContents, patchDiffTitle, safePatchUriPart } = require("./patchDiffPreview");
const {
  idleStatus,
  renderStatusText,
  renderStatusTooltip,
  scanningStatus,
  serviceOfflineStatus,
  statusColorRole,
  statusFromScanResult
} = require("./statusModel");

const CANDIDATE_GLOB = "**/{sample_sheet.csv,samples.csv,sample_sheet.csv.gz,samples.csv.gz,*.bed,*.bed.gz,*.vcf,*.vcf.gz,*.gtf,*.gtf.gz,*.gff,*.gff.gz,*.gff3,*.gff3.gz,*.fastq,*.fq,metadata.json,project.json,*.nf,nextflow.config,Snakefile,*.smk,*.snakefile,*.fai,multiqc_general_stats.txt}";
const PATCH_PREVIEW_SCHEME = "dogma-patch";
const patchPreviewDocuments = new Map();

class InspectorProvider {
  constructor() {
    this.issues = [];
    this.fileMap = {};
    this.uriByFile = new Map();
    this.context = extractWorkspaceContext({});
    this.scanSource = "not scanned";
    this.activeEditor = null;
    this.artifacts = {};
    this.sidecarView = null;
    this.statusBar = null;
    this.artifactRefreshInFlight = false;
    this._onDidChangeTreeData = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._onDidChangeTreeData.event;
  }

  setScanResult({ issues, fileMap, uriByFile, context, source }) {
    this.issues = issues;
    this.fileMap = fileMap;
    this.uriByFile = uriByFile;
    this.scanSource = source || "extension";
    this.context = { ...context, scanSource: source || context.scanSource || "extension" };
    this.refresh();
  }

  setActiveEditor(editorContext) {
    this.activeEditor = editorContext;
    this.refresh();
  }

  setDogmaArtifacts(artifacts) {
    this.artifacts = artifacts || {};
    this.refresh();
  }

  async refreshDogmaArtifacts() {
    if (this.artifactRefreshInFlight || !vscode.workspace.workspaceFolders?.length) return;
    this.artifactRefreshInFlight = true;
    try {
      this.setDogmaArtifacts(await readSidecarArtifactSnapshot());
    } finally {
      this.artifactRefreshInFlight = false;
    }
  }

  getTreeItem(item) {
    const treeItem = new vscode.TreeItem(
      item ? `${item.file}:${item.line} ${item.message}` : "Open the Dogma Sidecar or run a scan",
      vscode.TreeItemCollapsibleState.None
    );

    if (item) {
      treeItem.description = item.severity;
      treeItem.tooltip = `${item.severity.toUpperCase()} ${item.file}:${item.line}\n${item.message}`;
      treeItem.iconPath = new vscode.ThemeIcon(item.severity === "error" ? "error" : "warning");
      const root = workspaceRootFolder();
      if (root) {
        treeItem.command = {
          command: "vscode.open",
          title: "Open issue file",
          arguments: [vscode.Uri.joinPath(root.uri, ...item.file.split(/[\\/]/))]
        };
      }
    } else {
      treeItem.description = this.scanSource;
      treeItem.iconPath = new vscode.ThemeIcon("beaker");
      treeItem.command = {
        command: "dogma.scanWithLocalService",
        title: "Scan With Local Service"
      };
    }

    return treeItem;
  }

  getChildren() {
    return this.issues.length ? this.issues : [null];
  }

  resolveWebviewView(webviewView) {
    this.sidecarView = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.html = this.render();
    this.refreshDogmaArtifacts();
    webviewView.webview.onDidReceiveMessage(async (message) => {
      if (!message || typeof message.command !== "string") return;
      if (!message.command.startsWith("dogma.")) return;
      const args = Object.prototype.hasOwnProperty.call(message, "payload") ? [message.payload] : [];
      await vscode.commands.executeCommand(message.command, ...args);
      await this.refreshDogmaArtifacts();
    });
  }

  render() {
    return renderSidecarHtml({
      issues: this.issues,
      context: this.context,
      scanSource: this.scanSource,
      activeEditor: this.activeEditor,
      artifacts: this.artifacts
    });
  }

  refresh() {
    this._onDidChangeTreeData.fire();
    if (this.sidecarView) {
      this.sidecarView.webview.html = this.render();
    }
  }
}

class PatchPreviewDocumentProvider {
  provideTextDocumentContent(uri) {
    return patchPreviewDocuments.get(uri.toString()) || "";
  }
}

function patchPreviewUris(proposal) {
  const id = safePatchUriPart(proposal.id || "proposal");
  const target = safePatchUriPart(proposal.target_file || "patch.txt");
  const nonce = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const beforeUri = vscode.Uri.parse(`${PATCH_PREVIEW_SCHEME}:/${id}/before/${target}?${nonce}`);
  const afterUri = vscode.Uri.parse(`${PATCH_PREVIEW_SCHEME}:/${id}/after/${target}?${nonce}`);
  const contents = patchDiffDocumentContents(proposal);
  patchPreviewDocuments.set(beforeUri.toString(), contents.before);
  patchPreviewDocuments.set(afterUri.toString(), contents.after);
  return { beforeUri, afterUri };
}

async function openPatchProposalDiff(proposal) {
  if (!proposal || typeof proposal.before !== "string" || typeof proposal.after !== "string") {
    throw new Error("Patch proposal does not include before/after text for a diff preview.");
  }
  const { beforeUri, afterUri } = patchPreviewUris(proposal);
  await vscode.commands.executeCommand(
    "vscode.diff",
    beforeUri,
    afterUri,
    patchDiffTitle(proposal),
    { preview: false, viewColumn: vscode.ViewColumn.Beside }
  );
  return { beforeUri, afterUri };
}

async function readCandidateFiles() {
  const config = vscode.workspace.getConfiguration("dogma");
  const maxFiles = config.get("maxFiles", 200);
  const uris = await vscode.workspace.findFiles(CANDIDATE_GLOB, "**/{node_modules,.git,.next,out,dist}/**", maxFiles);
  const fileMap = {};
  const uriByFile = new Map();

  for (const uri of uris) {
    const bytes = await vscode.workspace.fs.readFile(uri);
    const relative = vscode.workspace.asRelativePath(uri);
    fileMap[relative] = Buffer.from(bytes).toString("utf8");
    uriByFile.set(relative, uri);
  }

  return { fileMap, uriByFile };
}

function workspaceRootFolder() {
  return vscode.workspace.workspaceFolders?.[0];
}

function findingUri(provider, file) {
  const filePath = String(file || "").trim();
  if (!filePath) return null;
  const mapped = provider.uriByFile?.get(filePath);
  if (mapped) return mapped;

  const root = workspaceRootFolder();
  if (!root) return null;
  const parts = filePath.split(/[\\/]/).filter((part) => part && part !== "." && part !== "..");
  if (!parts.length) return null;
  return vscode.Uri.joinPath(root.uri, ...parts);
}

async function openFinding(provider, payload = {}) {
  const uri = findingUri(provider, payload.file);
  if (!uri) {
    vscode.window.showWarningMessage("Dogma could not resolve that finding to a workspace file.");
    return;
  }

  try {
    const line = Math.max(1, Number(payload.line || 1));
    const document = await vscode.workspace.openTextDocument(uri);
    const editor = await vscode.window.showTextDocument(document, { preview: false });
    const position = new vscode.Position(Math.min(line - 1, Math.max(document.lineCount - 1, 0)), 0);
    editor.selection = new vscode.Selection(position, position);
    editor.revealRange(new vscode.Range(position, position), vscode.TextEditorRevealType.InCenter);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma could not open finding: ${error.message}`);
  }
}

function serviceConfig() {
  const config = vscode.workspace.getConfiguration("dogma");
  return {
    mode: config.get("serviceMode", "auto"),
    url: config.get("serviceUrl", "http://127.0.0.1:8765"),
    timeoutMs: config.get("serviceTimeoutMs", 2000),
    executionTimeoutSeconds: config.get("executionTimeoutSeconds", 30),
    startupWaitMs: config.get("serviceStartupWaitMs", 5000),
    python: config.get("servicePython", "python3"),
    moduleName: config.get("serviceModule", "dogma_service"),
    cwd: config.get("serviceCwd", "auto"),
    agentProvider: config.get("agentProvider", "claude_subscription"),
    agentModel: config.get("agentModel", "sonnet"),
    agentTimeoutSeconds: config.get("agentTimeoutSeconds", 180),
    claudeCliPath: config.get("claudeCliPath", "claude"),
    qurationUrl: config.get("qurationUrl", DEFAULT_QURATION_CANVAS_URL),
    qurationApiUrl: config.get("qurationApiUrl", DEFAULT_QURATION_API_URL),
    qurationTimeoutMs: config.get("qurationTimeoutMs", 5000),
    maxFiles: config.get("maxFiles", 200)
  };
}

function applyStatusBarState(statusBar, status) {
  if (!statusBar) return;

  statusBar.text = renderStatusText(status);
  statusBar.tooltip = renderStatusTooltip(status);
  statusBar.command = "dogma.scanWorkspace";

  const colorRole = statusColorRole(status);
  if (colorRole === "error") {
    statusBar.backgroundColor = new vscode.ThemeColor("statusBarItem.errorBackground");
  } else if (colorRole === "warning") {
    statusBar.backgroundColor = new vscode.ThemeColor("statusBarItem.warningBackground");
  } else {
    statusBar.backgroundColor = undefined;
  }
  statusBar.show();
}

function updateProviderStatus(provider, status) {
  applyStatusBarState(provider?.statusBar, status);
}

function createBackgroundScanner(provider, diagnosticCollection) {
  let timer = null;

  return {
    schedule(delayMs = 350) {
      if (timer) {
        clearTimeout(timer);
      }
      timer = setTimeout(() => {
        timer = null;
        scanWorkspace(provider, diagnosticCollection, { silent: true, background: true }).catch((error) => {
          updateProviderStatus(provider, serviceOfflineStatus(error.message, "background scan"));
        });
      }, delayMs);
    },
    dispose() {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
    }
  };
}

function createActiveEditorTracker(provider) {
  let timer = null;

  return {
    schedule(delayMs = 100) {
      if (timer) {
        clearTimeout(timer);
      }
      timer = setTimeout(() => {
        timer = null;
        provider.setActiveEditor(activeEditorContext());
      }, delayMs);
    },
    dispose() {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
    }
  };
}

function activeEditorContext() {
  const editor = vscode.window.activeTextEditor;
  const root = workspaceRootFolder();
  if (!editor || !root || editor.document.uri.scheme !== "file") {
    return null;
  }

  const document = editor.document;
  const selection = editor.selection;
  const selectedText = selection && !selection.isEmpty ? document.getText(selection).slice(0, 6000) : "";
  const activeLine = document.lineAt(selection?.active?.line ?? 0).text.slice(0, 1000);
  return {
    path: vscode.workspace.asRelativePath(document.uri),
    language_id: document.languageId,
    selection: selection
      ? {
          start: { line: selection.start.line + 1, character: selection.start.character + 1 },
          end: { line: selection.end.line + 1, character: selection.end.character + 1 },
          active: { line: selection.active.line + 1, character: selection.active.character + 1 },
          is_empty: selection.isEmpty
        }
      : {},
    selected_text: selectedText,
    current_line: activeLine
  };
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForLocalService(config) {
  const startedAt = Date.now();
  let lastError;
  while (Date.now() - startedAt < config.startupWaitMs) {
    try {
      return await checkLocalService({
        serviceUrl: config.url,
        timeoutMs: Math.min(config.timeoutMs, 1000)
      });
    } catch (error) {
      lastError = error;
      await sleep(250);
    }
  }
  throw lastError || new Error(`Timed out after ${config.startupWaitMs} ms.`);
}

function runInProcessScan(fileMap) {
  const config = vscode.workspace.getConfiguration("dogma");
  const issues = validateFiles(fileMap, {
    enableHumanDataWarnings: config.get("enableHumanDataWarnings", true)
  });
  const context = extractWorkspaceContext(fileMap);
  return { issues, context, source: "extension" };
}

async function runServiceBackedScan(config) {
  const root = workspaceRootFolder();
  if (!root) {
    throw new Error("Open a workspace folder before using the Dogma local service.");
  }

  const result = await scanWithLocalService({
    serviceUrl: config.url,
    rootPath: root.uri.fsPath,
    maxFiles: config.maxFiles,
    timeoutMs: config.timeoutMs
  });
  return { issues: result.issues, context: result.context, source: "local service" };
}

function summarizeIssues(issues) {
  const errors = issues.filter((item) => item.severity === "error").length;
  const warnings = issues.filter((item) => item.severity === "warning").length;
  return `${issues.length} issue(s): ${errors} error(s), ${warnings} warning(s)`;
}

function summarizePostApplyScan(issues) {
  if (!issues.length) {
    return "Post-apply scan passed with no domain issues.";
  }
  return `Post-apply scan found ${summarizeIssues(issues)}.`;
}

function publishDiagnostics(collection, fileMap, uriByFile, issues) {
  collection.clear();
  const entries = diagnosticEntries(fileMap, issues);

  for (const [file, diagnostics] of entries) {
    const uri = uriByFile.get(file);
    if (!uri) continue;

    collection.set(
      uri,
      diagnostics.map((item) => {
        const range = new vscode.Range(
          item.range.startLine,
          item.range.startCharacter,
          item.range.endLine,
          item.range.endCharacter
        );
        const diagnostic = new vscode.Diagnostic(range, item.message, item.severity);
        diagnostic.source = item.source;
        diagnostic.code = item.code || "dogma.domain";
        return diagnostic;
      })
    );
  }
}

async function scanWorkspace(provider, diagnosticCollection, options = {}) {
  if (!vscode.workspace.workspaceFolders?.length) {
    const message = "Open a workspace folder before running Dogma.";
    updateProviderStatus(provider, idleStatus(message));
    if (!options.silent) {
      vscode.window.showWarningMessage(message);
    }
    return null;
  }

  updateProviderStatus(
    provider,
    scanningStatus(options.forceService ? "local service" : options.background ? "background scan" : "workspace")
  );
  const { fileMap, uriByFile } = await readCandidateFiles();
  const localService = serviceConfig();
  const shouldUseService = options.forceService || localService.mode === "auto" || localService.mode === "required";
  let result;
  let fallbackMessage = "";

  if (shouldUseService) {
    try {
      if (options.startService && options.manager) {
        await ensureLocalServiceReady(localService, options.manager, options.output);
      }
      result = await runServiceBackedScan(localService);
    } catch (error) {
      const message = `Dogma local service unavailable: ${error.message}`;
      if (options.forceService || localService.mode === "required") {
        updateProviderStatus(provider, serviceOfflineStatus(message));
        if (!options.silent) {
          vscode.window.showErrorMessage(message);
        }
        return null;
      }
      fallbackMessage = `${message}. Fell back to in-extension scan.`;
      if (!options.silent) {
        vscode.window.showWarningMessage(fallbackMessage);
      }
    }
  }

  if (!result) {
    result = runInProcessScan(fileMap);
  }

  const { issues, context, source } = result;

  provider.setScanResult({ issues, fileMap, uriByFile, context, source });
  publishDiagnostics(diagnosticCollection, fileMap, uriByFile, issues);
  const message = issues.length ? summarizeIssues(issues) : "Dogma scan passed with no domain issues.";
  updateProviderStatus(provider, statusFromScanResult({ issues, context, source, message: fallbackMessage || message }));
  if (!options.silent) {
    vscode.window.showInformationMessage(`Dogma (${source}): ${message}`);
  }
  return issues;
}

async function refreshAfterServicePatch(provider, diagnosticCollection) {
  if (!provider || !diagnosticCollection) {
    return null;
  }

  const issues = await scanWorkspace(provider, diagnosticCollection, { forceService: true });
  return issues ? summarizePostApplyScan(issues) : "Post-apply scan did not complete.";
}

function buildAssistantHtml(context, issues) {
  const issueRows = issues.length
    ? issues.map((item) => `<li><strong>${escapeHtml(item.severity)}</strong> ${escapeHtml(item.file)}:${item.line} ${escapeHtml(item.message)}</li>`).join("")
    : "<li>No issues found. Run scans after changing sample sheets, BED, VCF, metadata, or workflows.</li>";
  const contextHtml = renderContextHtml(context, issues, escapeHtml);

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: var(--vscode-font-family); color: var(--vscode-foreground); padding: 16px; }
    h1 { font-size: 18px; }
    section { border: 1px solid var(--vscode-panel-border); padding: 12px; margin: 12px 0; }
    button { background: var(--vscode-button-background); color: var(--vscode-button-foreground); border: 0; padding: 7px 10px; margin: 4px 6px 4px 0; cursor: pointer; }
    button:hover { background: var(--vscode-button-hoverBackground); }
    li { margin: 8px 0; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border-bottom: 1px solid var(--vscode-panel-border); padding: 6px 4px; text-align: left; vertical-align: top; }
    th { width: 150px; color: var(--vscode-descriptionForeground); font-weight: 600; }
    code { color: var(--vscode-textPreformat-foreground); }
  </style>
</head>
<body>
  <h1>Dogma Assistant</h1>
  <section>
    <h2>Actions</h2>
    <button data-command="copyPrompt">Copy AI Context Prompt</button>
    <button data-command="scanService">Scan With Local Service</button>
    <button data-command="writeTestPlan">Write Synthetic Test Plan</button>
    <button data-command="generateReport">Generate Context Report</button>
    <button data-command="generateWorkflowGraph">Generate Workflow Graph</button>
    <button data-command="openGraphWorkbench">Open Local Workflow Guardrails</button>
    <button data-command="openBiologicalGraphWorkbench">Open Local Biological Guardrails</button>
    <button data-command="generateRunPlan">Generate Safe Run Plan</button>
    <button data-command="generateServiceAssistantContext">Generate Service Assistant Context</button>
    <button data-command="generateMethodGuardrails">Generate Method Guardrails</button>
    <button data-command="generateEvidenceLedger">Generate Evidence Ledger</button>
    <button data-command="generateEdgeEvaluationPlan">Generate Edge Evaluation Plan</button>
    <button data-command="generateQurationHandoff">Generate quration Handoff</button>
    <button data-command="checkQurationStatus">Check quration Status</button>
    <button data-command="importWorkspaceToQuration">Import Workspace To quration</button>
    <button data-command="openLastQurationImport">Open Last quration Import</button>
    <button data-command="generateMethodsGraphSubstrate">Generate Methods-Graph Substrate</button>
    <button data-command="generateMethodsGraphPreflight">Generate Methods-Graph Preflight</button>
    <button data-command="checkLlmProvider">Check LLM Provider</button>
    <button data-command="openAgentWorkbench">Open Agent Workbench</button>
    <button data-command="generateAgentSuggestion">Generate Agent Suggestion</button>
    <button data-command="generateAgentHandoff">Generate Agent Handoff</button>
    <button data-command="reviewActiveFile">Review Active File</button>
    <button data-command="generateServiceRunPlan">Generate Service Run Plan</button>
    <button data-command="generatePatchProposals">Generate Patch Proposals</button>
    <button data-command="checkTrust">Check Workspace Trust</button>
    <button data-command="applyPatch">Apply Sample Validation Patch</button>
  </section>
  ${contextHtml}
  <section>
    <h2>Domain Findings</h2>
    <ul>${issueRows}</ul>
  </section>
  <section>
    <h2>Suggested Next Actions</h2>
    <ol>
      <li>Fix errors before running a real workflow.</li>
      <li>Use synthetic fixtures for regression tests.</li>
      <li>Record genome build, annotation release, strandedness, and tool versions.</li>
      <li>Run <code>Dogma: Apply Sample Sheet Validation Patch</code> for simple Nextflow sample-sheet validation.</li>
    </ol>
  </section>
  <script>
    const vscode = acquireVsCodeApi();
    document.querySelectorAll("button[data-command]").forEach((button) => {
      button.addEventListener("click", () => vscode.postMessage({ command: button.dataset.command }));
    });
  </script>
</body>
</html>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  })[character]);
}

async function ensureScan(provider, diagnosticCollection) {
  if (!Object.keys(provider.fileMap).length) {
    await scanWorkspace(provider, diagnosticCollection);
  }
}

async function writeWorkspaceFile(relativeParts, contents, viewColumn = vscode.ViewColumn.Beside) {
  const root = vscode.workspace.workspaceFolders[0].uri;
  const directoryParts = relativeParts.slice(0, -1);
  const directoryUri = vscode.Uri.joinPath(root, ...directoryParts);
  if (directoryParts.length) {
    await vscode.workspace.fs.createDirectory(directoryUri);
  }
  const uri = vscode.Uri.joinPath(root, ...relativeParts);
  await vscode.workspace.fs.writeFile(uri, Buffer.from(contents, "utf8"));
  if (viewColumn === null) {
    return uri;
  }
  const document = await vscode.workspace.openTextDocument(uri);
  await vscode.window.showTextDocument(document, viewColumn);
  return uri;
}

async function readWorkspaceText(relativeParts) {
  const root = workspaceRootFolder();
  if (!root) {
    throw new Error("Open a workspace folder before reading Dogma workspace artifacts.");
  }
  const uri = vscode.Uri.joinPath(root.uri, ...relativeParts);
  const bytes = await vscode.workspace.fs.readFile(uri);
  return Buffer.from(bytes).toString("utf8");
}

async function readWorkspaceJson(relativeParts) {
  const root = workspaceRootFolder();
  if (!root) {
    throw new Error("Open a workspace folder before reading Dogma workspace artifacts.");
  }
  const uri = vscode.Uri.joinPath(root.uri, ...relativeParts);
  const bytes = await vscode.workspace.fs.readFile(uri);
  return JSON.parse(Buffer.from(bytes).toString("utf8"));
}

async function readOptionalWorkspaceJson(relativeParts) {
  try {
    return await readWorkspaceJson(relativeParts);
  } catch {
    return null;
  }
}

async function readSidecarArtifactSnapshot() {
  const [
    qurationGraph,
    qurationEdgeSelection,
    qurationStatus,
    ideReadiness,
    methodsGraphPreflight,
    qurationEdgeWorkPackage,
    qurationEdgeAgentSuggestion,
    qurationEdgePatchHandoff,
    agentHandoff,
    trustPolicy,
    llmProviderStatus
  ] = await Promise.all([
    readOptionalWorkspaceJson([".dogma", "quration-graph.json"]),
    readOptionalWorkspaceJson([".dogma", "quration-edge-selection.json"]),
    readOptionalWorkspaceJson([".dogma", "quration-status.json"]),
    readOptionalWorkspaceJson([".dogma", "ide-readiness.json"]),
    readOptionalWorkspaceJson([".dogma", "methods-graph-preflight.json"]),
    readOptionalWorkspaceJson([".dogma", "quration-edge-work-package.json"]),
    readOptionalWorkspaceJson([".dogma", "quration-edge-agent-suggestion.json"]),
    readOptionalWorkspaceJson([".dogma", "quration-edge-patch-handoff.json"]),
    readOptionalWorkspaceJson([".dogma", "agent-handoff.json"]),
    readOptionalWorkspaceJson([".dogma", "trust.json"]),
    readOptionalWorkspaceJson([".dogma", "llm-provider-status.json"])
  ]);

  return {
    qurationGraph,
    qurationEdgeSelection,
    qurationStatus,
    ideReadiness,
    methodsGraphPreflight,
    qurationEdgeWorkPackage,
    qurationEdgeAgentSuggestion,
    qurationEdgePatchHandoff,
    agentHandoff,
    trustPolicy,
    llmProviderStatus
  };
}

async function openAssistant(provider, diagnosticCollection) {
  await ensureScan(provider, diagnosticCollection);
  const panel = vscode.window.createWebviewPanel(
    "dogmaAssistant",
    "Dogma Assistant",
    vscode.ViewColumn.Beside,
    { enableScripts: true }
  );
  panel.webview.html = buildAssistantHtml(provider.context, provider.issues);
  panel.webview.onDidReceiveMessage(async (message) => {
    if (message.command === "copyPrompt") {
      await ensureScan(provider, diagnosticCollection);
      await vscode.env.clipboard.writeText(buildAssistantPrompt(provider.context, provider.issues));
      vscode.window.showInformationMessage("Dogma copied an AI context prompt to the clipboard.");
    }
    if (message.command === "scanService") {
      await scanWorkspace(provider, diagnosticCollection, { forceService: true });
      panel.webview.html = buildAssistantHtml(provider.context, provider.issues);
    }
    if (message.command === "writeTestPlan") {
      await ensureScan(provider, diagnosticCollection);
      const uri = await writeWorkspaceFile([".dogma", "synthetic-test-plan.md"], buildSyntheticTestPlan(provider.context, provider.issues));
      vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)}.`);
    }
    if (message.command === "generateReport") {
      await generateContextReport(provider, diagnosticCollection);
    }
    if (message.command === "generateWorkflowGraph") {
      await generateWorkflowGraph(provider, diagnosticCollection);
    }
    if (message.command === "openGraphWorkbench") {
      await openGraphWorkbench(provider, diagnosticCollection);
    }
    if (message.command === "openBiologicalGraphWorkbench") {
      await openBiologicalGraphWorkbench();
    }
    if (message.command === "generateRunPlan") {
      await generateRunPlan(provider, diagnosticCollection);
    }
    if (message.command === "generateServiceAssistantContext") {
      await generateServiceAssistantContext();
    }
    if (message.command === "generateMethodGuardrails") {
      await generateMethodGuardrails();
    }
    if (message.command === "generateEvidenceLedger") {
      await generateEvidenceLedger();
    }
    if (message.command === "generateEdgeEvaluationPlan") {
      await generateEdgeEvaluationPlan();
    }
    if (message.command === "generateQurationHandoff") {
      await generateQurationHandoff();
    }
    if (message.command === "checkQurationStatus") {
      await checkQurationStatus();
    }
    if (message.command === "importWorkspaceToQuration") {
      await importWorkspaceToQuration();
    }
    if (message.command === "openLastQurationImport") {
      await openLastQurationImport();
    }
    if (message.command === "generateMethodsGraphSubstrate") {
      await generateMethodsGraphSubstrate();
    }
    if (message.command === "generateMethodsGraphPreflight") {
      await generateMethodsGraphPreflight();
    }
    if (message.command === "checkLlmProvider") {
      await checkLlmProvider();
    }
    if (message.command === "openAgentWorkbench") {
      await openAgentWorkbench(provider, diagnosticCollection);
    }
    if (message.command === "generateAgentSuggestion") {
      await generateAgentSuggestion();
    }
    if (message.command === "generateAgentHandoff") {
      await generateAgentHandoff(provider);
    }
    if (message.command === "reviewActiveFile") {
      await reviewActiveFile();
    }
    if (message.command === "generateServiceRunPlan") {
      await generateServiceRunPlan();
    }
    if (message.command === "generatePatchProposals") {
      await generatePatchProposals();
    }
    if (message.command === "checkTrust") {
      await checkWorkspaceTrust();
    }
    if (message.command === "applyPatch") {
      await applySampleValidationPatch();
      await scanWorkspace(provider, diagnosticCollection);
      panel.webview.html = buildAssistantHtml(provider.context, provider.issues);
    }
  });
}

async function generateContextReport(provider, diagnosticCollection) {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a Dogma context report.");
    return;
  }

  await ensureScan(provider, diagnosticCollection);

  const report = renderContextReport(provider.context, provider.issues);
  const reportUri = await writeWorkspaceFile([".dogma", "context-report.md"], report);
  vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(reportUri)}.`);
}

async function generateWorkflowGraph(provider, diagnosticCollection) {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a Dogma workflow graph.");
    return;
  }

  await ensureScan(provider, diagnosticCollection);

  const graphs = extractWorkflowGraphs(provider.fileMap);
  const reportUri = await writeWorkspaceFile([".dogma", "workflow-graph.md"], renderWorkflowGraphReport(graphs));
  vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(reportUri)}.`);
}

async function openGraphWorkbench(provider, diagnosticCollection) {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before opening Dogma local workflow guardrails.");
    return;
  }

  await ensureScan(provider, diagnosticCollection);

  const graphs = extractWorkflowGraphs(provider.fileMap);
  const model = buildGraphWorkbenchModel(graphs, provider.context, provider.issues);
  const panel = vscode.window.createWebviewPanel(
    "dogmaGraphWorkbench",
    "Dogma Local Workflow Guardrails",
    vscode.ViewColumn.Beside,
    { enableScripts: true }
  );
  panel.webview.html = renderGraphWorkbenchHtml(model);
  panel.webview.onDidReceiveMessage(async (message) => {
    if (message.command !== "generateEdgeEvaluationPlan") return;
    const selectedEdge = model.graphs.flatMap((graph) => graph.edges).find((edge) => edge.id === message.edgeId);
    const uri = await writeEdgeEvaluationPlanFromService(selectedEdge);
    if (uri) {
      await panel.webview.postMessage({
        command: "edgeEvaluationPlanStatus",
        message: `Wrote ${vscode.workspace.asRelativePath(uri)} for the selected edge.`
      });
    }
  });
}

async function openBiologicalGraphWorkbench() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before opening Dogma local biological edge guardrails.");
    return;
  }

  const config = serviceConfig();
  try {
    const graph = await getBiologicalGraphWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs
    });
    const panel = vscode.window.createWebviewPanel(
      "dogmaBiologicalGraph",
      "Dogma Local Biological Edge Guardrails",
      vscode.ViewColumn.Beside,
      { enableScripts: true }
    );
    panel.webview.html = renderBiologicalGraphWorkbenchHtml(graph);
    panel.webview.onDidReceiveMessage(async (message) => {
      if (message.command !== "generateEdgeEvaluationPlan") return;
      const selectedEdge = message.selectedEdge || (graph.edges || []).find((edge) => edge.id === message.edgeId)?.selected_edge;
      const uri = await writeEdgeEvaluationPlanFromService(selectedEdge);
      if (uri) {
        await panel.webview.postMessage({
          command: "edgeEvaluationPlanStatus",
          message: `Wrote ${vscode.workspace.asRelativePath(uri)} for the selected biological edge.`
        });
      }
    });
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma local biological edge guardrails failed: ${error.message}`);
  }
}

async function generateRunPlan(provider, diagnosticCollection) {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a Dogma run plan.");
    return;
  }

  await ensureScan(provider, diagnosticCollection);

  const runPlan = renderRunPlan(provider.context, provider.issues);
  const runPlanUri = await writeWorkspaceFile([".dogma", "run-plan.md"], runPlan);
  vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(runPlanUri)}.`);
}

async function generateServiceRunPlan() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a Dogma service run plan.");
    return;
  }

  const config = serviceConfig();
  try {
    const plan = await getRunPlanWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs
    });
    const uri = await writeWorkspaceFile([".dogma", "service-run-plan.md"], renderServiceRunPlan(plan));
    vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)} from the local service.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma local service run plan failed: ${error.message}`);
  }
}

async function generateServiceAssistantContext() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a Dogma service assistant context.");
    return;
  }

  const config = serviceConfig();
  try {
    const result = await getAssistantContextWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs
    });
    const uri = await writeWorkspaceFile([".dogma", "service-assistant-context.md"], renderServiceAssistantContext(result));
    vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)} from the local service.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma local service assistant context failed: ${error.message}`);
  }
}

async function generateMethodGuardrails() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating Dogma method guardrails.");
    return;
  }

  const config = serviceConfig();
  try {
    const result = await getMethodGuardrailsWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs
    });
    const uri = await writeWorkspaceFile([".dogma", "method-guardrails.md"], renderMethodGuardrails(result));
    vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)} from the local service.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma method guardrails failed: ${error.message}`);
  }
}

async function generateEvidenceLedger() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a Dogma evidence ledger.");
    return;
  }

  const config = serviceConfig();
  try {
    const result = await getEvidenceLedgerWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs
    });
    const uri = await writeWorkspaceFile([".dogma", "evidence-ledger.md"], renderEvidenceLedger(result));
    vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)} from the local service.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma evidence ledger failed: ${error.message}`);
  }
}

async function generateEdgeEvaluationPlan() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a Dogma edge evaluation plan.");
    return;
  }

  await writeEdgeEvaluationPlanFromService();
}

async function readOrPullQurationGraphContext() {
  try {
    return await readWorkspaceJson([".dogma", "quration-graph.json"]);
  } catch {
    return pullQurationGraphContext();
  }
}

function qurationGraphIdFromContext(context = {}) {
  return String(context.graph_id || context.graph?.id || "").trim();
}

async function readQurationEdgeSelection(context = {}) {
  try {
    const selection = await readWorkspaceJson([".dogma", "quration-edge-selection.json"]);
    const currentGraphId = qurationGraphIdFromContext(context);
    const selectedGraphId = String(selection.quration_graph?.graph_id || "").trim();
    const edgeId = String(selection.selected_edge?.id || "").trim();
    if (!edgeId || selectedGraphId !== currentGraphId) return null;
    pickQurationEdge(context, edgeId);
    return selection;
  } catch {
    return null;
  }
}

async function writeQurationEdgeSelection(context, edge, selectionSource = "quick_pick") {
  const record = buildQurationEdgeSelectionRecord({ context, edge, selectionSource });
  const jsonUri = await writeWorkspaceFile([".dogma", "quration-edge-selection.json"], JSON.stringify(record, null, 2) + "\n", null);
  const markdownUri = await writeWorkspaceFile([".dogma", "quration-edge-selection.md"], renderQurationEdgeSelection(record), null);
  return { record, jsonUri, markdownUri };
}

async function chooseQurationEdge(context = {}, options = {}) {
  const edges = qurationEdges(context);
  if (!edges.length) {
    throw new Error("No quration edges are available in .dogma/quration-graph.json.");
  }

  if (!options.forcePrompt) {
    const stored = await readQurationEdgeSelection(context);
    if (stored) {
      const edge = pickQurationEdge(context, stored.selected_edge.id);
      return {
        edge,
        selectedEdge: buildQurationSelectedEdge(context, { edgeId: edge.id }),
        selection: stored,
        selectionSource: "stored"
      };
    }
  }

  const items = buildQurationEdgeQuickPickItems(context);
  const item = items.length === 1 && !options.forcePrompt
    ? items[0]
    : await vscode.window.showQuickPick(items, {
        title: options.title || "Select quration Edge",
        placeHolder: options.placeHolder || "Choose the quration edge Dogma should use for local IDE work.",
        matchOnDescription: true,
        matchOnDetail: true
      });
  if (!item) return null;

  const written = await writeQurationEdgeSelection(context, item.edge, items.length === 1 && !options.forcePrompt ? "only_edge" : "quick_pick");
  return {
    edge: item.edge,
    selectedEdge: buildQurationSelectedEdge(context, { edgeId: item.edgeId }),
    selection: written.record,
    markdownUri: written.markdownUri,
    jsonUri: written.jsonUri,
    selectionSource: written.record.selection_source
  };
}

async function selectQurationEdge() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before selecting a quration edge.");
    return null;
  }

  const context = await readOrPullQurationGraphContext();
  if (!context) return null;

  try {
    const selected = await chooseQurationEdge(context, {
      forcePrompt: true,
      title: "Select quration Edge For Dogma",
      placeHolder: "Choose one quration edge as the active local IDE work unit."
    });
    if (!selected) return null;
    vscode.window.showInformationMessage(
      `Dogma selected quration edge ${selected.selectedEdge.id} and wrote ${vscode.workspace.asRelativePath(selected.markdownUri)}.`
    );
    return selected.markdownUri;
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration edge selection failed: ${error.message}`);
    return null;
  }
}

async function fetchQurationEdgePlanRecord(context, edge, config = serviceConfig()) {
  const graphId = qurationGraphIdFromContext(context);
  if (!graphId) {
    throw new Error("quration graph id is missing.");
  }
  return getQurationEdgePlan({
    qurationApiUrl: config.qurationApiUrl,
    qurationCanvasUrl: config.qurationUrl,
    graphId,
    edgeId: edge.id,
    query: context.query,
    timeoutMs: config.qurationTimeoutMs
  });
}

async function getDogmaQurationEdgeEvaluationRecord(context, selectedEdge, config = serviceConfig()) {
  const result = await getEdgeEvaluationPlanWithLocalService({
    serviceUrl: config.url,
    rootPath: workspaceRootFolder().uri.fsPath,
    maxFiles: config.maxFiles,
    selectedEdge,
    timeoutMs: config.timeoutMs
  });
  return {
    contract_version: "dogma-quration-edge-evaluation-plan.v1",
    generated_at: new Date().toISOString(),
    quration_graph: {
      graph_id: context.graph_id || context.graph?.id || null,
      graph_url: context.graph_url || null,
      query: context.query || null
    },
    selected_edge: selectedEdge,
    plan: result
  };
}

async function generateQurationEdgeEvaluationPlan() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a Dogma quration edge evaluation plan.");
    return null;
  }

  const context = await readOrPullQurationGraphContext();
  if (!context) return null;

  let selectedEdge;
  try {
    const selection = await chooseQurationEdge(context, {
      title: "Select quration Edge For Evaluation Plan"
    });
    if (!selection) return null;
    selectedEdge = selection.selectedEdge;
  } catch (error) {
    vscode.window.showWarningMessage(`Dogma could not select a quration edge: ${error.message}`);
    return null;
  }

  const config = serviceConfig();
  try {
    const record = await getDogmaQurationEdgeEvaluationRecord(context, selectedEdge, config);
    const jsonUri = await writeWorkspaceFile([".dogma", "quration-edge-evaluation-plan.json"], JSON.stringify(record, null, 2) + "\n", null);
    const markdownUri = await writeWorkspaceFile(
      [".dogma", "quration-edge-evaluation-plan.md"],
      renderQurationEdgeEvaluationPlan(record.plan, context, selectedEdge)
    );
    vscode.window.showInformationMessage(
      `Dogma wrote ${vscode.workspace.asRelativePath(markdownUri)} and ${vscode.workspace.asRelativePath(jsonUri)} from quration edge ${selectedEdge.id}.`
    );
    return markdownUri;
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration edge evaluation plan failed: ${error.message}`);
    return null;
  }
}

async function fetchQurationEdgePlan() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before fetching a quration edge plan.");
    return null;
  }

  const context = await readOrPullQurationGraphContext();
  if (!context) return null;

  let edge;
  try {
    const selection = await chooseQurationEdge(context, {
      title: "Select quration Edge Plan To Fetch"
    });
    if (!selection) return null;
    edge = selection.edge;
  } catch (error) {
    vscode.window.showWarningMessage(`Dogma could not select a quration edge: ${error.message}`);
    return null;
  }

  const graphId = String(context.graph_id || context.graph?.id || "").trim();
  if (!graphId) {
    vscode.window.showWarningMessage("Dogma could not fetch a quration edge plan because the graph id is missing.");
    return null;
  }

  const config = serviceConfig();
  try {
    const record = await fetchQurationEdgePlanRecord(context, edge, config);
    const jsonUri = await writeWorkspaceFile([".dogma", "quration-edge-plan.json"], JSON.stringify(record, null, 2) + "\n", null);
    const markdownUri = await writeWorkspaceFile([".dogma", "quration-edge-plan.md"], renderQurationEdgePlan(record));
    vscode.window.showInformationMessage(
      `Dogma fetched quration edge plan ${record.edge_id} and wrote ${vscode.workspace.asRelativePath(markdownUri)} and ${vscode.workspace.asRelativePath(jsonUri)}.`
    );
    return markdownUri;
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration edge plan fetch failed: ${error.message}`);
    return null;
  }
}

async function generateQurationEdgeWorkPackage() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a quration edge work package.");
    return null;
  }

  const context = await readOrPullQurationGraphContext();
  if (!context) return null;

  let edge;
  let selectedEdge;
  try {
    const selection = await chooseQurationEdge(context, {
      title: "Select quration Edge Work Package"
    });
    if (!selection) return null;
    edge = selection.edge;
    selectedEdge = selection.selectedEdge;
  } catch (error) {
    vscode.window.showWarningMessage(`Dogma could not select a quration edge: ${error.message}`);
    return null;
  }

  const config = serviceConfig();
  try {
    const [qurationEdgePlan, dogmaEdgeEvaluation] = await Promise.all([
      fetchQurationEdgePlanRecord(context, edge, config),
      getDogmaQurationEdgeEvaluationRecord(context, selectedEdge, config)
    ]);
    await writeWorkspaceFile([".dogma", "quration-edge-plan.json"], JSON.stringify(qurationEdgePlan, null, 2) + "\n", null);
    await writeWorkspaceFile([".dogma", "quration-edge-plan.md"], renderQurationEdgePlan(qurationEdgePlan), null);
    await writeWorkspaceFile([".dogma", "quration-edge-evaluation-plan.json"], JSON.stringify(dogmaEdgeEvaluation, null, 2) + "\n", null);
    await writeWorkspaceFile(
      [".dogma", "quration-edge-evaluation-plan.md"],
      renderQurationEdgeEvaluationPlan(dogmaEdgeEvaluation.plan, context, selectedEdge),
      null
    );

    const record = {
      contract_version: "dogma-quration-edge-work-package.v1",
      generated_at: new Date().toISOString(),
      edge_id: selectedEdge.id,
      quration_graph: {
        graph_id: context.graph_id || context.graph?.id || null,
        graph_url: context.graph_url || null,
        query: context.query || null
      },
      selected_edge: selectedEdge,
      quration_edge_plan: qurationEdgePlan,
      dogma_edge_evaluation: dogmaEdgeEvaluation
    };
    const jsonUri = await writeWorkspaceFile([".dogma", "quration-edge-work-package.json"], JSON.stringify(record, null, 2) + "\n", null);
    const markdownUri = await writeWorkspaceFile([".dogma", "quration-edge-work-package.md"], renderQurationEdgeWorkPackage(record));
    vscode.window.showInformationMessage(
      `Dogma wrote ${vscode.workspace.asRelativePath(markdownUri)} and ${vscode.workspace.asRelativePath(jsonUri)} for quration edge ${selectedEdge.id}.`
    );
    return markdownUri;
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration edge work package failed: ${error.message}`);
    return null;
  }
}

function artifactEditorContext(relativeParts, contents) {
  const text = String(contents || "");
  const path = relativeParts.join("/");
  const firstLine = text.split(/\r?\n/, 1)[0] || path;
  return {
    path,
    language_id: "markdown",
    selection: {
      start: { line: 1, character: 1 },
      end: { line: Math.max(1, text.split(/\r?\n/).length), character: 1 },
      active: { line: 1, character: 1 },
      is_empty: false
    },
    selected_text: text.slice(0, 6000),
    current_line: firstLine.slice(0, 1000)
  };
}

function qurationEdgePackageAgentInstruction() {
  return [
    "Review the quration edge work package in .dogma/quration-edge-work-package.md.",
    "Propose the next smallest safe IDE action for this bioinformatics workspace.",
    "Use quration's canonical edge skeleton, Dogma local guardrails, coverage gaps, patch proposals, and active workflow files when relevant.",
    "Do not assert biological support/refute verdicts, do not resolve quration evidence from the IDE, and do not recommend real execution while blocker gaps remain.",
    "Prefer a concrete patch preview, test-plan, guardrail configuration, or user question."
  ].join(" ");
}

async function requestQurationEdgePackageAgentSuggestion(config, useLlm) {
  const packageUri = await generateQurationEdgeWorkPackage();
  if (!packageUri) return null;

  const relativeParts = [".dogma", "quration-edge-work-package.md"];
  const packageMarkdown = await readWorkspaceText(relativeParts);
  return requestAgentSuggestion(
    config,
    qurationEdgePackageAgentInstruction(),
    useLlm,
    artifactEditorContext(relativeParts, packageMarkdown)
  );
}

function firstPatchPreviewAction(result) {
  const actions = Array.isArray(result?.suggestion?.next_actions) ? result.suggestion.next_actions : [];
  return actions.find((action) => (
    action &&
    action.kind === "patch_preview" &&
    (action.proposal_id || action.proposalId)
  ));
}

async function writeQurationEdgeAgentSuggestionArtifacts(result) {
  const workPackage = await readWorkspaceJson([".dogma", "quration-edge-work-package.json"]);
  const markdownUri = await writeAgentSuggestionArtifact(result, "quration-edge-agent-suggestion.md");
  const actions = Array.isArray(result?.suggestion?.next_actions) ? result.suggestion.next_actions : [];
  const patchPreviewActions = actions.filter((action) => (
    action &&
    action.kind === "patch_preview" &&
    (action.proposal_id || action.proposalId)
  ));
  const record = {
    contract_version: "dogma-quration-edge-agent-suggestion.v1",
    generated_at: new Date().toISOString(),
    edge_id: workPackage.edge_id || workPackage.selected_edge?.id || null,
    quration_graph: workPackage.quration_graph || {},
    suggestion: {
      status: result?.suggestion?.status || result?.status || "unknown",
      llm_executed: Boolean(result?.llm_executed),
      provider: result?.llm_status?.provider || null,
      patch_preview_count: patchPreviewActions.length,
      proposal_ids: patchPreviewActions.map((action) => action.proposal_id || action.proposalId).filter(Boolean)
    },
    artifacts: {
      markdown: ".dogma/quration-edge-agent-suggestion.md",
      json: ".dogma/quration-edge-agent-suggestion.json",
      work_package_json: ".dogma/quration-edge-work-package.json"
    }
  };
  const jsonUri = await writeWorkspaceFile([".dogma", "quration-edge-agent-suggestion.json"], JSON.stringify(record, null, 2) + "\n", null);
  return { result, record, markdownUri, jsonUri };
}

async function suggestFromQurationEdgeWorkPackage() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before asking Dogma about a quration edge work package.");
    return null;
  }

  const config = serviceConfig();
  const useLlm = config.agentProvider !== "none";
  if (useLlm) {
    const confirmed = await confirmLocalClaudeUse();
    if (!confirmed) return null;
  }

  try {
    const result = await requestQurationEdgePackageAgentSuggestion(config, useLlm);
    if (!result) return null;
    return writeQurationEdgeAgentSuggestionArtifacts(result);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration edge agent suggestion failed: ${error.message}`);
    return null;
  }
}

async function previewQurationEdgeSuggestedPatch() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before previewing a quration edge suggested patch.");
    return null;
  }

  const config = serviceConfig();
  const useLlm = config.agentProvider !== "none";
  if (useLlm) {
    const confirmed = await confirmLocalClaudeUse();
    if (!confirmed) return null;
  }

  try {
    const result = await requestQurationEdgePackageAgentSuggestion(config, useLlm);
    if (!result) return null;
    await writeQurationEdgeAgentSuggestionArtifacts(result);
    const action = firstPatchPreviewAction(result);
    const proposalId = action?.proposal_id || action?.proposalId;
    if (!proposalId) {
      vscode.window.showWarningMessage("Dogma did not find a patch_preview proposal in the quration edge agent suggestion.");
      return null;
    }
    const preview = await previewPatchProposalById(config, proposalId);
    vscode.window.showInformationMessage(`Dogma previewed quration edge suggested patch ${proposalId}.`);
    return { proposalId, preview };
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration edge suggested patch preview failed: ${error.message}`);
    return null;
  }
}

async function writeQurationEdgePatchHandoffArtifact(preview, applyResult = null) {
  const workPackage = await readWorkspaceJson([".dogma", "quration-edge-work-package.json"]);
  const record = buildQurationEdgePatchHandoff({
    workPackage,
    patchPreview: preview?.result || preview || {},
    patchApply: applyResult?.result || applyResult || null
  });
  const jsonUri = await writeWorkspaceFile([".dogma", "quration-edge-patch-handoff.json"], JSON.stringify(record, null, 2) + "\n", null);
  const markdownUri = await writeWorkspaceFile([".dogma", "quration-edge-patch-handoff.md"], renderQurationEdgePatchHandoff(record));
  vscode.window.showInformationMessage(
    `Dogma wrote ${vscode.workspace.asRelativePath(markdownUri)} and ${vscode.workspace.asRelativePath(jsonUri)} for quration review.`
  );
  return { record, jsonUri, markdownUri };
}

async function readMatchingQurationEdgePatchHandoff(context = {}, selectedEdge = {}) {
  const graphId = qurationGraphIdFromContext(context);
  const edgeId = String(selectedEdge.id || "").trim();
  let handoff;
  try {
    handoff = await readWorkspaceJson([".dogma", "quration-edge-patch-handoff.json"]);
  } catch {
    throw new Error("Generate a quration edge patch handoff before resolving the edge in quration.");
  }

  const handoffGraphId = String(handoff.quration_graph?.graph_id || "").trim();
  const handoffEdgeId = String(handoff.selected_edge?.id || "").trim();
  if (handoffGraphId !== graphId || handoffEdgeId !== edgeId) {
    throw new Error("The existing quration edge patch handoff does not match the selected graph edge.");
  }
  return handoff;
}

function resolveConfirmationMessage(selectedEdge = {}, handoff = {}) {
  const patchApplied = Boolean(handoff.local_patch?.applied);
  const guardrailStatus = String(handoff.dogma_guardrails?.status || "unknown");
  const gaps = Array.isArray(handoff.dogma_guardrails?.coverage_gaps) ? handoff.dogma_guardrails.coverage_gaps : [];
  const gapText = gaps.length ? ` Coverage gaps: ${gaps.join(", ")}.` : "";
  const patchText = patchApplied ? "The local patch handoff says the patch was applied." : "The local patch handoff says the patch was not applied.";
  return [
    `Dogma will ask quration to resolve readout facts for ${selectedEdge.id}.`,
    "This is a quration evidence-writing operation and may persist an EvidenceRecord in quration.",
    patchText,
    `Dogma guardrail status is ${guardrailStatus}.${gapText}`,
    "Dogma will only write a local audit artifact and will not mark the edge supported or refuted."
  ].join(" ");
}

function buildQurationEdgeResolveRecord(resolveRecord = {}, handoff = {}) {
  return {
    ...resolveRecord,
    dogma_preconditions: {
      confirmation: "explicit_modal_confirmation",
      patch_handoff: {
        present: true,
        artifact: ".dogma/quration-edge-patch-handoff.json",
        generated_at: handoff.generated_at || null,
        patch_applied: Boolean(handoff.local_patch?.applied),
        proposal_id: handoff.local_patch?.proposal_id || null,
        guardrail_status: handoff.dogma_guardrails?.status || null,
        coverage_gaps: Array.isArray(handoff.dogma_guardrails?.coverage_gaps) ? handoff.dogma_guardrails.coverage_gaps : []
      }
    },
    source_artifacts: [
      ".dogma/quration-edge-selection.json",
      ".dogma/quration-edge-patch-handoff.json",
      ".dogma/quration-events.json",
      ".dogma/quration-failed-events.json"
    ]
  };
}

async function generateQurationEdgePatchHandoff() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a quration edge patch handoff.");
    return null;
  }

  try {
    const preview = await previewQurationEdgeSuggestedPatch();
    if (!preview) return null;
    return writeQurationEdgePatchHandoffArtifact(preview.preview);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration edge patch handoff failed: ${error.message}`);
    return null;
  }
}

async function resolveQurationSelectedEdgeReadout() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before resolving a quration edge readout.");
    return null;
  }

  const context = await readOrPullQurationGraphContext();
  if (!context) return null;

  let selection;
  try {
    selection = await chooseQurationEdge(context, {
      title: "Select quration Edge To Resolve"
    });
    if (!selection) return null;
  } catch (error) {
    vscode.window.showWarningMessage(`Dogma could not select a quration edge to resolve: ${error.message}`);
    return null;
  }

  let handoff;
  try {
    handoff = await readMatchingQurationEdgePatchHandoff(context, selection.selectedEdge);
  } catch (error) {
    vscode.window.showWarningMessage(error.message);
    return null;
  }

  const choice = await vscode.window.showWarningMessage(
    resolveConfirmationMessage(selection.selectedEdge, handoff),
    { modal: true },
    "Resolve In quration"
  );
  if (choice !== "Resolve In quration") return null;

  const config = serviceConfig();
  try {
    const resolved = await resolveQurationEdgeReadout({
      qurationApiUrl: config.qurationApiUrl,
      qurationCanvasUrl: config.qurationUrl,
      graphId: qurationGraphIdFromContext(context),
      edgeId: selection.selectedEdge.id,
      query: context.query,
      timeoutMs: config.qurationTimeoutMs
    });
    const record = buildQurationEdgeResolveRecord(resolved, handoff);
    const jsonUri = await writeWorkspaceFile([".dogma", "quration-edge-resolve.json"], JSON.stringify(record, null, 2) + "\n", null);
    const markdownUri = await writeWorkspaceFile([".dogma", "quration-edge-resolve.md"], renderQurationEdgeResolve(record));
    vscode.window.showInformationMessage(
      `Dogma resolved quration edge ${selection.selectedEdge.id} and wrote ${vscode.workspace.asRelativePath(markdownUri)} plus ${vscode.workspace.asRelativePath(jsonUri)}.`
    );
    return record;
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration edge resolve failed: ${error.message}`);
    return null;
  }
}

async function applyQurationEdgeSuggestedPatch(provider, diagnosticCollection) {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before applying a quration edge suggested patch.");
    return null;
  }

  const config = serviceConfig();
  const useLlm = config.agentProvider !== "none";
  if (useLlm) {
    const confirmed = await confirmLocalClaudeUse();
    if (!confirmed) return null;
  }

  try {
    const result = await requestQurationEdgePackageAgentSuggestion(config, useLlm);
    if (!result) return null;
    await writeQurationEdgeAgentSuggestionArtifacts(result);
    const action = firstPatchPreviewAction(result);
    const proposalId = action?.proposal_id || action?.proposalId;
    if (!proposalId) {
      vscode.window.showWarningMessage("Dogma did not find a patch_preview proposal in the quration edge agent suggestion.");
      return null;
    }
    const preview = await previewPatchProposalById(config, proposalId);
    const applyResult = await applyPatchProposalById(config, proposalId, {
      afterApply: () => refreshAfterServicePatch(provider, diagnosticCollection)
    });
    if (applyResult) {
      await writeQurationEdgePatchHandoffArtifact(preview, applyResult);
    }
    return applyResult;
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration edge suggested patch apply failed: ${error.message}`);
    return null;
  }
}

async function writeEdgeEvaluationPlanFromService(selectedEdge) {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a Dogma edge evaluation plan.");
    return null;
  }

  const config = serviceConfig();
  try {
    const result = await getEdgeEvaluationPlanWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      selectedEdge,
      timeoutMs: config.timeoutMs
    });
    const uri = await writeWorkspaceFile([".dogma", "edge-evaluation-plan.md"], renderEdgeEvaluationPlan(result));
    vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)} from the local service.`);
    return uri;
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma edge evaluation plan failed: ${error.message}`);
    return null;
  }
}

async function generateQurationHandoff() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a quration handoff.");
    return;
  }

  const config = serviceConfig();
  try {
    const result = await getQurationHandoffWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs
    });
    const jsonUri = await writeWorkspaceFile([".dogma", "quration-handoff.json"], JSON.stringify(result, null, 2) + "\n");
    let markdownUri = null;
    if (typeof result.markdown === "string" && result.markdown.trim()) {
      markdownUri = await writeWorkspaceFile([".dogma", "quration-handoff.md"], result.markdown.endsWith("\n") ? result.markdown : `${result.markdown}\n`);
    }
    const suffix = markdownUri ? ` and ${vscode.workspace.asRelativePath(markdownUri)}` : "";
    const choice = await vscode.window.showInformationMessage(
      `Dogma wrote ${vscode.workspace.asRelativePath(jsonUri)}${suffix} for quration.`,
      "Open quration Canvas"
    );
    if (choice === "Open quration Canvas") {
      await openQurationCanvas(result);
    }
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration handoff failed: ${error.message}`);
  }
}

async function openQurationUrl(query) {
  const config = serviceConfig();
  try {
    const target = buildQurationCanvasUrl(config.qurationUrl, query);
    await vscode.env.openExternal(vscode.Uri.parse(target));
    vscode.window.showInformationMessage(`Dogma opened quration canvas at ${target}.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma could not open quration canvas: ${error.message}`);
  }
}

async function openQurationGraphUi() {
  await openQurationUrl();
}

function qurationGraphUrlFromFields(fields = {}, config = serviceConfig()) {
  const graphUrl = String(fields.graph_url || fields.graphUrl || "").trim();
  if (graphUrl) return graphUrl;
  const graphId = String(fields.graph_id || fields.graphId || fields.id || "").trim();
  return buildQurationGraphUrl(config.qurationUrl, graphId);
}

async function resolveCurrentQurationGraphTarget(config = serviceConfig()) {
  try {
    const context = await readWorkspaceJson([".dogma", "quration-graph.json"]);
    const url = qurationGraphUrlFromFields(context, config);
    if (url) return { url, source: ".dogma/quration-graph.json" };
  } catch {
    // Fall through to other local quration records.
  }

  try {
    const selection = await readWorkspaceJson([".dogma", "quration-edge-selection.json"]);
    const url = qurationGraphUrlFromFields(selection.quration_graph || {}, config);
    if (url) return { url, source: ".dogma/quration-edge-selection.json" };
  } catch {
    // Fall through to the import record.
  }

  try {
    const record = await readWorkspaceJson([".dogma", "quration-import.json"]);
    const url = lastQurationGraphUrl(record) || qurationGraphUrlFromFields(record.quration || {}, config);
    if (url) return { url, source: ".dogma/quration-import.json" };
  } catch {
    // Fall through to graph history.
  }

  try {
    const history = await readWorkspaceJson([".dogma", "quration-graphs.json"]);
    const newest = history.graphs?.[0] || {};
    const url = qurationGraphUrlFromFields(newest, config);
    if (url) return { url, source: ".dogma/quration-graphs.json" };
  } catch {
    // Fall through to live graph history.
  }

  const history = await listQurationGraphs({
    qurationApiUrl: config.qurationApiUrl,
    qurationCanvasUrl: config.qurationUrl,
    timeoutMs: config.qurationTimeoutMs
  });
  const newest = history.graphs?.[0] || {};
  const url = qurationGraphUrlFromFields(newest, config);
  if (url) return { url, source: "quration /hypothesis" };
  return null;
}

async function openCurrentQurationGraph() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before opening the current quration graph.");
    return null;
  }

  const config = serviceConfig();
  try {
    const target = await resolveCurrentQurationGraphTarget(config);
    if (!target?.url) {
      vscode.window.showWarningMessage("Dogma could not find a current quration graph. Pull graph context, refresh graph history, or import the workspace first.");
      return null;
    }
    await vscode.env.openExternal(vscode.Uri.parse(target.url));
    vscode.window.showInformationMessage(`Dogma opened the current quration graph from ${target.source}.`);
    return target;
  } catch (error) {
    vscode.window.showWarningMessage(`Dogma could not open the current quration graph: ${error.message}`);
    return null;
  }
}

async function runNextIdeAction() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before running Dogma's next IDE action.");
    return null;
  }

  try {
    const artifacts = await readSidecarArtifactSnapshot();
    const action = deriveNextIdeAction(artifacts);
    if (!action?.command) {
      vscode.window.showWarningMessage("Dogma could not derive a next IDE action from the current workspace state.");
      return null;
    }
    vscode.window.showInformationMessage(`Dogma next action: ${action.label}. ${action.reason}`);
    await vscode.commands.executeCommand(action.command);
    return action;
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma next IDE action failed: ${error.message}`);
    return null;
  }
}

async function openQurationCanvas(result) {
  const query = result?.causal_graph?.query;
  await openQurationUrl(query);
}

async function openQurationCanvasFromWorkspace() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before opening quration from Dogma workspace context.");
    return;
  }

  const config = serviceConfig();
  try {
    const result = await getQurationHandoffWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs
    });
    const jsonUri = await writeWorkspaceFile([".dogma", "quration-handoff.json"], JSON.stringify(result, null, 2) + "\n");
    await openQurationCanvas(result);
    vscode.window.showInformationMessage(`Dogma opened quration canvas from ${vscode.workspace.asRelativePath(jsonUri)}.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration canvas launch failed: ${error.message}`);
  }
}

async function checkQurationStatus() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before checking quration status.");
    return;
  }

  const config = serviceConfig();
  try {
    const status = await checkQurationConnection({
      qurationApiUrl: config.qurationApiUrl,
      qurationCanvasUrl: config.qurationUrl,
      timeoutMs: config.qurationTimeoutMs
    });
    await writeWorkspaceFile([".dogma", "quration-status.json"], JSON.stringify(status, null, 2) + "\n", null);
    const markdownUri = await writeWorkspaceFile([".dogma", "quration-status.md"], renderQurationConnectionStatus(status));
    const readiness = status.import_ready ? "ready" : "not ready";
    vscode.window.showInformationMessage(`Dogma quration status is ${readiness}; wrote ${vscode.workspace.asRelativePath(markdownUri)}.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration status check failed: ${error.message}`);
  }
}

async function refreshQurationGraphHistory() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before refreshing quration graph history.");
    return null;
  }

  const config = serviceConfig();
  try {
    const history = await listQurationGraphs({
      qurationApiUrl: config.qurationApiUrl,
      qurationCanvasUrl: config.qurationUrl,
      timeoutMs: config.qurationTimeoutMs
    });
    const jsonUri = await writeWorkspaceFile([".dogma", "quration-graphs.json"], JSON.stringify(history, null, 2) + "\n", null);
    await writeWorkspaceFile([".dogma", "quration-graphs.md"], renderQurationGraphHistory(history), null);
    const newest = history.graphs?.[0];
    const choice = newest?.graph_url
      ? await vscode.window.showInformationMessage(
        `Dogma read ${history.count} quration graph(s) and wrote ${vscode.workspace.asRelativePath(jsonUri)}.`,
        "Open Newest Graph"
      )
      : await vscode.window.showInformationMessage(`Dogma read no quration graphs and wrote ${vscode.workspace.asRelativePath(jsonUri)}.`);
    if (choice === "Open Newest Graph") {
      await vscode.env.openExternal(vscode.Uri.parse(newest.graph_url));
    }
    return history;
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration graph history refresh failed: ${error.message}`);
    return null;
  }
}

async function resolveQurationGraphId(config) {
  try {
    const record = await readWorkspaceJson([".dogma", "quration-import.json"]);
    const graphId = String(record.quration?.graph_id || "").trim();
    if (graphId) return { graphId, source: ".dogma/quration-import.json" };
  } catch {
    // Fall through to graph history.
  }

  try {
    const history = await readWorkspaceJson([".dogma", "quration-graphs.json"]);
    const graphId = String(history.graphs?.[0]?.id || "").trim();
    if (graphId) return { graphId, source: ".dogma/quration-graphs.json" };
  } catch {
    // Fall through to live quration history.
  }

  const history = await listQurationGraphs({
    qurationApiUrl: config.qurationApiUrl,
    qurationCanvasUrl: config.qurationUrl,
    timeoutMs: config.qurationTimeoutMs
  });
  const graphId = String(history.graphs?.[0]?.id || "").trim();
  if (graphId) return { graphId, source: "quration /hypothesis" };
  return { graphId: null, source: "quration /hypothesis" };
}

async function pullQurationGraphContext() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before pulling quration graph context.");
    return null;
  }

  const config = serviceConfig();
  try {
    const { graphId, source } = await resolveQurationGraphId(config);
    if (!graphId) {
      vscode.window.showWarningMessage("Dogma could not find a quration graph id. Import a workspace graph or refresh quration graph history first.");
      return null;
    }
    const context = await getQurationGraphContext({
      qurationApiUrl: config.qurationApiUrl,
      qurationCanvasUrl: config.qurationUrl,
      graphId,
      timeoutMs: config.qurationTimeoutMs
    });
    const jsonUri = await writeWorkspaceFile([".dogma", "quration-graph.json"], JSON.stringify(context, null, 2) + "\n", null);
    await writeWorkspaceFile([".dogma", "quration-graph.md"], renderQurationGraphContext(context), null);
    const choice = context.graph_url
      ? await vscode.window.showInformationMessage(
        `Dogma pulled quration graph ${context.graph_id} from ${source} and wrote ${vscode.workspace.asRelativePath(jsonUri)}.`,
        "Open Graph"
      )
      : await vscode.window.showInformationMessage(`Dogma pulled quration graph ${context.graph_id} from ${source} and wrote ${vscode.workspace.asRelativePath(jsonUri)}.`);
    if (choice === "Open Graph") {
      await vscode.env.openExternal(vscode.Uri.parse(context.graph_url));
    }
    return context;
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration graph context pull failed: ${error.message}`);
    return null;
  }
}

async function pullQurationGraphEvents() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before pulling quration graph events.");
    return null;
  }

  const config = serviceConfig();
  try {
    const context = await readOrPullQurationGraphContext();
    if (!context) return null;
    const graphId = qurationGraphIdFromContext(context);
    if (!graphId) {
      vscode.window.showWarningMessage("Dogma could not pull quration graph events because the graph id is missing.");
      return null;
    }
    const events = await getQurationGraphEvents({
      qurationApiUrl: config.qurationApiUrl,
      qurationCanvasUrl: config.qurationUrl,
      graphId,
      query: context.query,
      timeoutMs: config.qurationTimeoutMs
    });
    const jsonUri = await writeWorkspaceFile([".dogma", "quration-events.json"], JSON.stringify(events, null, 2) + "\n", null);
    const markdownUri = await writeWorkspaceFile([".dogma", "quration-events.md"], renderQurationEvents(events), null);
    vscode.window.showInformationMessage(
      `Dogma pulled ${events.count} quration event(s) for graph ${graphId} and wrote ${vscode.workspace.asRelativePath(markdownUri)}.`
    );
    return events;
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration graph event pull failed: ${error.message}`);
    return null;
  }
}

async function pullQurationFailedEvents() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before pulling quration failed events.");
    return null;
  }

  const config = serviceConfig();
  try {
    const events = await getQurationFailedEvents({
      qurationApiUrl: config.qurationApiUrl,
      qurationCanvasUrl: config.qurationUrl,
      timeoutMs: config.qurationTimeoutMs,
      limit: 100
    });
    const jsonUri = await writeWorkspaceFile([".dogma", "quration-failed-events.json"], JSON.stringify(events, null, 2) + "\n", null);
    const markdownUri = await writeWorkspaceFile([".dogma", "quration-failed-events.md"], renderQurationEvents(events), null);
    vscode.window.showInformationMessage(
      `Dogma pulled ${events.count} failed quration event(s) and wrote ${vscode.workspace.asRelativePath(markdownUri)}.`
    );
    return events;
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration failed event pull failed: ${error.message}`);
    return null;
  }
}

async function captureReadinessStep(fn) {
  try {
    return { ok: true, result: await fn() };
  } catch (error) {
    return { ok: false, error: error.message };
  }
}

async function writeIdeReadinessReport(config = serviceConfig()) {
  const rootPath = workspaceRootFolder().uri.fsPath;
  const [localService, trust, llmProvider, methodsGraph, quration] = await Promise.all([
    captureReadinessStep(() => checkLocalService({
      serviceUrl: config.url,
      timeoutMs: config.timeoutMs
    })),
    captureReadinessStep(() => getTrustStatusWithLocalService({
      serviceUrl: config.url,
      rootPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs
    })),
    captureReadinessStep(() => getLlmStatusWithLocalService({
      serviceUrl: config.url,
      rootPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs,
      provider: config.agentProvider,
      cliPath: config.claudeCliPath,
      model: config.agentModel,
      timeoutSeconds: config.agentTimeoutSeconds
    })),
    captureReadinessStep(() => getMethodsGraphPreflightWithLocalService({
      serviceUrl: config.url,
      rootPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs
    })),
    captureReadinessStep(() => checkQurationConnection({
      qurationApiUrl: config.qurationApiUrl,
      qurationCanvasUrl: config.qurationUrl,
      timeoutMs: config.qurationTimeoutMs
    }))
  ]);

  const report = buildIdeReadinessReport({
    localService,
    trust,
    llmProvider,
    methodsGraph,
    quration,
    settings: {
      service_url: config.url,
      quration_canvas_url: config.qurationUrl,
      quration_api_url: config.qurationApiUrl,
      agent_provider: config.agentProvider
    }
  });
  const jsonUri = await writeWorkspaceFile([".dogma", "ide-readiness.json"], JSON.stringify(report, null, 2) + "\n", null);
  const markdownUri = await writeWorkspaceFile([".dogma", "ide-readiness.md"], renderIdeReadiness(report));
  return { report, jsonUri, markdownUri };
}

async function checkIdeReadiness() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before checking Dogma IDE readiness.");
    return null;
  }

  try {
    const result = await writeIdeReadinessReport();
    vscode.window.showInformationMessage(`Dogma IDE readiness is ${result.report.status}; wrote ${vscode.workspace.asRelativePath(result.markdownUri)}.`);
    return result;
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma IDE readiness check failed: ${error.message}`);
    return null;
  }
}

async function importWorkspaceToQuration() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before importing a Dogma graph into quration.");
    return;
  }

  const config = serviceConfig();
  try {
    const handoff = await getQurationHandoffWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs
    });
    const jsonUri = await writeWorkspaceFile([".dogma", "quration-handoff.json"], JSON.stringify(handoff, null, 2) + "\n", null);
    const result = await importQurationHandoff({
      qurationApiUrl: config.qurationApiUrl,
      qurationCanvasUrl: config.qurationUrl,
      handoff,
      timeoutMs: config.qurationTimeoutMs
    });
    const record = buildQurationImportRecord({
      result,
      handoff,
      qurationApiUrl: config.qurationApiUrl,
      qurationCanvasUrl: config.qurationUrl
    });
    const recordJsonUri = await writeWorkspaceFile([".dogma", "quration-import.json"], JSON.stringify(record, null, 2) + "\n", null);
    await writeWorkspaceFile([".dogma", "quration-import.md"], renderQurationImportRecord(record), null);
    if (result.graph_url) {
      await vscode.env.openExternal(vscode.Uri.parse(result.graph_url));
    }
    const target = result.graph_id ? ` as ${result.graph_id}` : "";
    vscode.window.showInformationMessage(`Dogma imported ${vscode.workspace.asRelativePath(jsonUri)} into quration${target} and wrote ${vscode.workspace.asRelativePath(recordJsonUri)}.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma quration import failed: ${error.message}`);
  }
}

async function openLastQurationImport() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before opening the last quration import.");
    return;
  }

  try {
    const record = await readWorkspaceJson([".dogma", "quration-import.json"]);
    const url = lastQurationGraphUrl(record);
    if (!url) {
      vscode.window.showWarningMessage("Dogma found .dogma/quration-import.json, but it does not contain a quration graph URL.");
      return;
    }
    await vscode.env.openExternal(vscode.Uri.parse(url));
    vscode.window.showInformationMessage(`Dogma opened the last quration import at ${url}.`);
  } catch (error) {
    vscode.window.showWarningMessage(`Dogma could not open the last quration import: ${error.message}`);
  }
}

async function generateMethodsGraphSubstrate() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a Dogma methods-graph substrate report.");
    return;
  }

  const config = serviceConfig();
  try {
    const result = await getMethodsGraphSubstrateWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs
    });
    const uri = await writeWorkspaceFile([".dogma", "methods-graph-substrate.md"], renderMethodsGraphSubstrate(result));
    vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)} from the local service.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma methods-graph substrate report failed: ${error.message}`);
  }
}

async function generateMethodsGraphPreflight() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a Dogma methods-graph preflight report.");
    return;
  }

  const config = serviceConfig();
  try {
    const result = await getMethodsGraphPreflightWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs
    });
    await writeWorkspaceFile([".dogma", "methods-graph-preflight.json"], JSON.stringify(result, null, 2) + "\n", null);
    const uri = await writeWorkspaceFile([".dogma", "methods-graph-preflight.md"], renderMethodsGraphPreflight(result));
    vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)} and .dogma/methods-graph-preflight.json from the local service.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma methods-graph preflight failed: ${error.message}`);
  }
}

async function checkLlmProvider() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before checking the Dogma LLM provider.");
    return;
  }

  const config = serviceConfig();
  try {
    const result = await getLlmStatusWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs,
      provider: config.agentProvider,
      cliPath: config.claudeCliPath,
      model: config.agentModel,
      timeoutSeconds: config.agentTimeoutSeconds
    });
    await writeWorkspaceFile([".dogma", "llm-provider-status.json"], JSON.stringify(result, null, 2) + "\n", null);
    const uri = await writeWorkspaceFile([".dogma", "llm-provider-status.md"], renderLlmProviderStatus(result));
    const readiness = await writeIdeReadinessReport(config);
    vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)} from the local service and refreshed ${vscode.workspace.asRelativePath(readiness.markdownUri)}.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma LLM provider check failed: ${error.message}`);
  }
}

async function confirmLocalClaudeUse() {
  const choice = await vscode.window.showWarningMessage(
    "Dogma will send redacted workspace context, findings, graph facts, and guardrails to the local Claude Code CLI through the Python sidecar. It will not grant Claude tool access or apply edits.",
    { modal: true },
    "Generate Suggestion"
  );
  return choice === "Generate Suggestion";
}

async function requestAgentSuggestion(config, instruction, useLlm, editorContext) {
  return getAgentSuggestionWithLocalService({
    serviceUrl: config.url,
    rootPath: workspaceRootFolder().uri.fsPath,
    maxFiles: config.maxFiles,
    timeoutMs: config.timeoutMs + config.agentTimeoutSeconds * 1000,
    instruction,
    useLlm,
    provider: config.agentProvider,
    cliPath: config.claudeCliPath,
    model: config.agentModel,
    timeoutSeconds: config.agentTimeoutSeconds,
    editorContext
  });
}

async function writeAgentSuggestionArtifact(result, fileName = "agent-suggestion.md") {
  const uri = await writeWorkspaceFile([".dogma", fileName], renderAgentSuggestion(result));
  const suffix = result.llm_executed ? "using the local Claude Code adapter" : "as a prompt-ready guardrail artifact";
  vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)} ${suffix}.`);
  return uri;
}

function isPatchBlockedByTrust(result) {
  return result?.status === "blocked" && result?.trust?.trusted === false && result?.trust?.status === "untrusted";
}

async function requestPatchApply(config, proposalId) {
  return applyPatchWithLocalService({
    serviceUrl: config.url,
    rootPath: workspaceRootFolder().uri.fsPath,
    proposalId,
    maxFiles: config.maxFiles,
    timeoutMs: config.timeoutMs,
    apply: true
  });
}

async function writeTrustPolicyForPatchRetry(config, proposalId) {
  const result = await trustWorkspaceWithLocalService({
    serviceUrl: config.url,
    rootPath: workspaceRootFolder().uri.fsPath,
    maxFiles: config.maxFiles,
    timeoutMs: config.timeoutMs,
    reason: `User trusted this workspace while applying Dogma patch proposal ${proposalId || "selected proposal"}.`
  });
  const uri = await writeWorkspaceFile([".dogma", "trust-write-result.md"], renderTrustWriteResult(result));
  vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)} and will retry the patch apply.`);
  return result;
}

async function maybeTrustAndRetryPatchApply(config, proposalId, result) {
  if (!isPatchBlockedByTrust(result)) {
    return result;
  }

  const blockers = Array.isArray(result.trust?.blockers) ? result.trust.blockers.join(" ") : "Workspace trust is required.";
  const choice = await vscode.window.showWarningMessage(
    `Dogma blocked patch application because this workspace is not trusted for local operations. ${blockers} Write .dogma/trust.json and retry this reviewed patch?`,
    { modal: true },
    "Trust And Retry"
  );
  if (choice !== "Trust And Retry") {
    return result;
  }

  await writeTrustPolicyForPatchRetry(config, proposalId);
  return requestPatchApply(config, proposalId);
}

async function previewPatchProposalById(config, proposalId) {
  const result = await applyPatchWithLocalService({
    serviceUrl: config.url,
    rootPath: workspaceRootFolder().uri.fsPath,
    proposalId,
    maxFiles: config.maxFiles,
    timeoutMs: config.timeoutMs,
    apply: false
  });
  const uri = await writeWorkspaceFile([".dogma", "patch-apply-preview.md"], renderPatchApplyResult(result));
  if (result.proposal) {
    await openPatchProposalDiff(result.proposal);
  }
  vscode.window.showInformationMessage(`Dogma opened a diff and wrote ${vscode.workspace.asRelativePath(uri)}${proposalId ? ` for ${proposalId}` : ""} without applying changes.`);
  return { uri, result };
}

async function applyPatchProposalById(config, proposalId, options = {}) {
  const choice = await vscode.window.showWarningMessage(
    `Dogma will ask the local service to apply ${proposalId || "the selected patch proposal"}. Review the preview before applying.`,
    { modal: true },
    "Apply Proposal"
  );
  if (choice !== "Apply Proposal") return null;

  let result = await requestPatchApply(config, proposalId);
  result = await maybeTrustAndRetryPatchApply(config, proposalId, result);
  const uri = await writeWorkspaceFile([".dogma", "patch-apply-result.md"], renderPatchApplyResult(result));
  let scanMessage = null;
  if (result.applied && options.afterApply) {
    scanMessage = await options.afterApply(result);
  }
  const suffix = scanMessage ? ` ${scanMessage}` : "";
  vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)}.${suffix}`);
  return { uri, result, scanMessage };
}

async function generateAgentSuggestion() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a Dogma agent suggestion.");
    return;
  }

  const instruction = await vscode.window.showInputBox({
    title: "Dogma Agent Suggestion",
    prompt: "What should the Dogma agent plan or fix next?",
    value: "Propose the next smallest safe edit for this bioinformatics workspace.",
    ignoreFocusOut: true
  });
  if (!instruction) return;

  const config = serviceConfig();
  const editorContext = activeEditorContext();
  const useLlm = config.agentProvider !== "none";
  if (useLlm) {
    const confirmed = await confirmLocalClaudeUse();
    if (!confirmed) return;
  }

  try {
    const result = await requestAgentSuggestion(config, instruction, useLlm, editorContext);
    await writeAgentSuggestionArtifact(result);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma agent suggestion failed: ${error.message}`);
  }
}

async function refreshMethodsGraphPreflightArtifact(config) {
  const result = await getMethodsGraphPreflightWithLocalService({
    serviceUrl: config.url,
    rootPath: workspaceRootFolder().uri.fsPath,
    maxFiles: config.maxFiles,
    timeoutMs: config.timeoutMs
  });
  await writeWorkspaceFile([".dogma", "methods-graph-preflight.json"], JSON.stringify(result, null, 2) + "\n", null);
  await writeWorkspaceFile([".dogma", "methods-graph-preflight.md"], renderMethodsGraphPreflight(result), null);
  return result;
}

async function generateAgentHandoff(provider) {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating a Dogma agent handoff.");
    return null;
  }

  try {
    const root = workspaceRootFolder();
    const config = serviceConfig();
    let artifacts = await readSidecarArtifactSnapshot();
    try {
      const methodsGraphPreflight = await refreshMethodsGraphPreflightArtifact(config);
      artifacts = { ...artifacts, methodsGraphPreflight };
    } catch (error) {
      artifacts = {
        ...artifacts,
        methodsGraphPreflight: artifacts.methodsGraphPreflight || {
          status: "unavailable",
          substrate_status: "unknown",
          coverage_gaps: ["methods_graph.preflight_unavailable"],
          next_actions: [
            `Start the Dogma local service at ${config.url} and rerun Dogma: Generate Agent Handoff.`,
            "Treat methods-graph grounding as unavailable until the preflight can run."
          ],
          error: error.message
        }
      };
    }
    const issueCounts = {
      errors: provider.issues.filter((issue) => issue.severity === "error").length,
      warnings: provider.issues.filter((issue) => issue.severity === "warning").length
    };
    const record = buildAgentHandoffRecord({
      workspaceName: root.name,
      scan: {
        scan_source: provider.scanSource,
        issue_count: provider.issues.length,
        issue_counts: issueCounts,
        trust_status: provider.context?.trust?.status || artifacts.trustPolicy?.status || "unknown",
        human_data: Boolean(provider.context?.trust?.human_data || provider.context?.privacy?.contains_human_data)
      },
      artifacts,
      activeEditor: activeEditorContext(),
      settings: config
    });
    const jsonUri = await writeWorkspaceFile([".dogma", "agent-handoff.json"], JSON.stringify(record, null, 2) + "\n", null);
    const markdownUri = await writeWorkspaceFile([".dogma", "agent-handoff.md"], renderAgentHandoffMarkdown(record), null);
    const rulesUri = await writeWorkspaceFile([".cursor", "rules", "dogma-bioinformatics.mdc"], renderCursorRules(record), null);
    await provider.refreshDogmaArtifacts();
    vscode.window.showInformationMessage(
      `Dogma wrote ${vscode.workspace.asRelativePath(markdownUri)}, ${vscode.workspace.asRelativePath(jsonUri)}, and ${vscode.workspace.asRelativePath(rulesUri)}.`
    );
    return { record, jsonUri, markdownUri, rulesUri };
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma agent handoff failed: ${error.message}`);
    return null;
  }
}

async function reviewActiveFile() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before reviewing an active file with Dogma.");
    return;
  }

  const editorContext = activeEditorContext();
  if (!editorContext) {
    vscode.window.showWarningMessage("Open a file-backed editor before running Dogma: Review Active File.");
    return;
  }

  const config = serviceConfig();
  const selectedScope = editorContext.selection?.is_empty === false ? "selected region" : "active file";
  const instruction = [
    `Review the ${selectedScope} at ${editorContext.path}.`,
    "Focus on bioinformatics correctness, reproducibility, sample/metadata consistency, privacy constraints, and the next smallest safe edit.",
    "Use Dogma findings, graph facts, methods-graph guardrails, and patch proposals when relevant.",
    "Do not recommend real workflow execution until validation, dry-run, and trust gates pass."
  ].join(" ");
  const useLlm = config.agentProvider !== "none";
  if (useLlm) {
    const confirmed = await confirmLocalClaudeUse();
    if (!confirmed) return;
  }

  try {
    const result = await requestAgentSuggestion(config, instruction, useLlm, editorContext);
    await writeAgentSuggestionArtifact(result, "active-file-review.md");
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma active file review failed: ${error.message}`);
  }
}

async function askDogmaAboutSelection() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before asking Dogma about a selection.");
    return;
  }

  const editorContext = activeEditorContext();
  if (!editorContext) {
    vscode.window.showWarningMessage("Open a file-backed editor before running Dogma: Ask About Selection.");
    return;
  }

  const selectedScope = editorContext.selection?.is_empty === false ? "selected text" : "current line";
  const question = await vscode.window.showInputBox({
    title: "Ask Dogma About Selection",
    prompt: `Ask a bioinformatics question about the ${selectedScope} in ${editorContext.path}.`,
    value: "Explain the bioinformatics risk and safest next edit for this context.",
    ignoreFocusOut: true
  });
  if (!question) return;

  const config = serviceConfig();
  const instruction = [
    `Answer this user question about the ${selectedScope} in ${editorContext.path}: ${question}`,
    `Current editor line: ${editorContext.current_line || "not available"}.`,
    "Use the selected text when present, Dogma findings, graph facts, methods-graph guardrails, and patch proposals when relevant.",
    "Keep the answer factual and action-oriented; do not recommend real workflow execution until validation, dry-run, and trust gates pass."
  ].join(" ");
  const useLlm = config.agentProvider !== "none";
  if (useLlm) {
    const confirmed = await confirmLocalClaudeUse();
    if (!confirmed) return;
  }

  try {
    const result = await requestAgentSuggestion(config, instruction, useLlm, editorContext);
    await writeAgentSuggestionArtifact(result, "selection-question.md");
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma selection question failed: ${error.message}`);
  }
}

function activeFindingForEditor(issues = [], editorContext) {
  if (!editorContext?.path) return null;

  const activeLine = editorContext.selection?.active?.line || editorContext.selection?.start?.line;
  const fileIssues = issues.filter((issue) => issue.file === editorContext.path);
  if (!fileIssues.length) return null;
  return fileIssues.find((issue) => Number(issue.line) === Number(activeLine)) || fileIssues[0];
}

async function reviewActiveFinding(provider, diagnosticCollection) {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before reviewing a Dogma finding.");
    return;
  }

  await ensureScan(provider, diagnosticCollection);

  const editorContext = activeEditorContext();
  if (!editorContext) {
    vscode.window.showWarningMessage("Open a file-backed editor before running Dogma: Review Active Finding.");
    return;
  }

  const finding = activeFindingForEditor(provider.issues, editorContext);
  if (!finding) {
    vscode.window.showInformationMessage(`Dogma found no findings for ${editorContext.path}. Use Review Active File for a broader pass.`);
    return;
  }

  const config = serviceConfig();
  const instruction = [
    `Review this Dogma finding in ${finding.file}:${finding.line}.`,
    `Finding: ${finding.severity || "warning"} ${finding.code || "dogma.domain"} - ${finding.message || "Dogma finding"}.`,
    `Current editor line: ${editorContext.current_line || "not available"}.`,
    "Explain the likely bioinformatics/reproducibility risk and propose the next smallest safe edit.",
    "Prefer existing Dogma patch proposals when they match the finding, and do not recommend real workflow execution until validation, dry-run, and trust gates pass."
  ].join(" ");
  const useLlm = config.agentProvider !== "none";
  if (useLlm) {
    const confirmed = await confirmLocalClaudeUse();
    if (!confirmed) return;
  }

  try {
    const result = await requestAgentSuggestion(config, instruction, useLlm, editorContext);
    await writeAgentSuggestionArtifact(result, "active-finding-review.md");
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma active finding review failed: ${error.message}`);
  }
}

async function openAgentWorkbench(provider, diagnosticCollection) {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before opening the Dogma agent workbench.");
    return;
  }

  const config = serviceConfig();
  const workbenchEditorContext = activeEditorContext();
  const state = {
    instruction: "Propose the next smallest safe edit for this bioinformatics workspace.",
    useLlm: config.agentProvider !== "none",
    editorContext: workbenchEditorContext,
    result: null,
    patchProposals: null,
    statusMessage: "Ready."
  };

  const panel = vscode.window.createWebviewPanel(
    "dogmaAgentWorkbench",
    "Dogma Agent",
    vscode.ViewColumn.Beside,
    { enableScripts: true }
  );

  async function refreshPatchProposals() {
    state.patchProposals = await getPatchProposalsWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs
    });
  }

  async function render() {
    panel.webview.html = renderAgentWorkbenchHtml(state);
  }

  try {
    await refreshPatchProposals();
  } catch (error) {
    state.statusMessage = `Patch proposal load failed: ${error.message}`;
  }
  await render();

  panel.webview.onDidReceiveMessage(async (message) => {
    try {
      if (message.command === "runAgent") {
        const instruction = String(message.instruction || "").trim();
        if (!instruction) return;
        const useLlm = Boolean(message.useLlm);
        if (useLlm) {
          const confirmed = await confirmLocalClaudeUse();
          if (!confirmed) return;
        }
        state.instruction = instruction;
        state.useLlm = useLlm;
        state.statusMessage = "Running agent...";
        await render();
        state.result = await requestAgentSuggestion(config, instruction, useLlm, state.editorContext);
        state.statusMessage = state.result.message || "Agent completed.";
        await writeAgentSuggestionArtifact(state.result);
        await refreshPatchProposals();
        await render();
      }
      if (message.command === "previewProposal") {
        await previewPatchProposalById(config, message.proposalId);
        state.statusMessage = `Previewed ${message.proposalId}.`;
        await render();
      }
      if (message.command === "applyProposal") {
        state.statusMessage = `Applying ${message.proposalId}...`;
        await render();
        const applied = await applyPatchProposalById(config, message.proposalId, {
          afterApply: () => refreshAfterServicePatch(provider, diagnosticCollection)
        });
        if (applied) {
          state.statusMessage = applied.scanMessage
            ? `Applied ${message.proposalId}. ${applied.scanMessage}`
            : `Applied ${message.proposalId}.`;
          await refreshPatchProposals();
          await render();
        }
      }
    } catch (error) {
      state.statusMessage = error.message;
      await render();
      vscode.window.showErrorMessage(`Dogma agent workbench failed: ${error.message}`);
    }
  });
}

async function previewServiceDryRun() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before previewing a Dogma service dry run.");
    return;
  }

  const config = serviceConfig();
  try {
    const result = await executeWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs,
      timeoutSeconds: config.executionTimeoutSeconds,
      execute: false
    });
    const uri = await writeWorkspaceFile([".dogma", "service-execution-preview.md"], renderExecutionResult(result));
    vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)} without executing workflow tools.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma local service execution preview failed: ${error.message}`);
  }
}

async function executeServiceDryRun() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before executing a Dogma service dry run.");
    return;
  }

  const choice = await vscode.window.showWarningMessage(
    "Dogma will ask the local service to execute the first allowed dry-run/stub-run command. Error-level findings still block execution.",
    { modal: true },
    "Execute Dry Run"
  );
  if (choice !== "Execute Dry Run") return;

  const config = serviceConfig();
  try {
    const result = await executeWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs + config.executionTimeoutSeconds * 1000,
      timeoutSeconds: config.executionTimeoutSeconds,
      execute: true
    });
    const uri = await writeWorkspaceFile([".dogma", "service-execution-result.md"], renderExecutionResult(result));
    vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)}.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma local service execution failed: ${error.message}`);
  }
}

async function generatePatchProposals() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before generating Dogma patch proposals.");
    return;
  }

  const config = serviceConfig();
  try {
    const result = await getPatchProposalsWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs
    });
    const uri = await writeWorkspaceFile([".dogma", "patch-proposals.md"], renderPatchProposals(result));
    vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)} from the local service.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma local service patch proposals failed: ${error.message}`);
  }
}

async function choosePatchProposal(config, placeHolder) {
  const proposalResult = await getPatchProposalsWithLocalService({
    serviceUrl: config.url,
    rootPath: workspaceRootFolder().uri.fsPath,
    maxFiles: config.maxFiles,
    timeoutMs: config.timeoutMs
  });
  const items = proposalQuickPickItems(proposalResult);
  if (!items.length) {
    vscode.window.showInformationMessage("Dogma found no local service patch proposals for the current workspace.");
    return null;
  }

  const selected = await vscode.window.showQuickPick(items, {
    placeHolder,
    matchOnDescription: true,
    matchOnDetail: true
  });
  const proposalId = selectedProposalId(selected);
  return proposalId ? { proposalId, proposalResult } : null;
}

async function chooseActiveFilePatchProposal(config, placeHolder) {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before using Dogma active-file patches.");
    return null;
  }

  const editorContext = activeEditorContext();
  if (!editorContext) {
    vscode.window.showWarningMessage("Open a file-backed editor before using active-file Dogma patches.");
    return null;
  }

  const proposalResult = await getPatchProposalsWithLocalService({
    serviceUrl: config.url,
    rootPath: workspaceRootFolder().uri.fsPath,
    maxFiles: config.maxFiles,
    timeoutMs: config.timeoutMs
  });
  const activeProposals = activeFilePatchProposals(proposalResult, editorContext.path);
  if (!activeProposals.length) {
    vscode.window.showInformationMessage(`Dogma found no patch proposals for ${editorContext.path}.`);
    return null;
  }

  let proposalId = activeProposals[0].id;
  if (activeProposals.length > 1) {
    const selected = await vscode.window.showQuickPick(proposalQuickPickItems({ proposals: activeProposals }), {
      placeHolder: placeHolder || `Select a Dogma patch proposal for ${editorContext.path}`,
      matchOnDescription: true,
      matchOnDetail: true
    });
    proposalId = selectedProposalId(selected);
    if (!proposalId) return null;
  }

  return { proposalId, proposalResult, editorContext };
}

async function previewActiveFilePatch() {
  const config = serviceConfig();
  try {
    const selection = await chooseActiveFilePatchProposal(config, "Select a Dogma patch proposal to preview for the active file");
    if (!selection) return;

    await previewPatchProposalById(config, selection.proposalId);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma active-file patch preview failed: ${error.message}`);
  }
}

async function applyActiveFilePatch(provider, diagnosticCollection) {
  const config = serviceConfig();
  try {
    const selection = await chooseActiveFilePatchProposal(config, "Select a Dogma patch proposal to apply for the active file");
    if (!selection) return;

    await previewPatchProposalById(config, selection.proposalId);
    await applyPatchProposalById(config, selection.proposalId, {
      afterApply: () => refreshAfterServicePatch(provider, diagnosticCollection)
    });
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma active-file patch apply failed: ${error.message}`);
  }
}

async function previewServicePatchApply() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before previewing a Dogma patch proposal.");
    return;
  }

  const config = serviceConfig();
  try {
    const selection = await choosePatchProposal(config, "Select a Dogma patch proposal to preview");
    if (!selection) return;

    await previewPatchProposalById(config, selection.proposalId);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma local service patch preview failed: ${error.message}`);
  }
}

async function applyServicePatch(provider, diagnosticCollection) {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before applying a Dogma service patch.");
    return;
  }

  const config = serviceConfig();
  let selection;
  try {
    selection = await choosePatchProposal(config, "Select a Dogma patch proposal to apply");
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma local service patch selection failed: ${error.message}`);
    return;
  }
  if (!selection) return;

  try {
    await applyPatchProposalById(config, selection.proposalId, {
      afterApply: () => refreshAfterServicePatch(provider, diagnosticCollection)
    });
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma local service patch apply failed: ${error.message}`);
  }
}

async function previewServicePatchProposal(proposalId) {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before previewing a Dogma patch proposal.");
    return;
  }
  try {
    await previewPatchProposalById(serviceConfig(), proposalId);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma local service patch preview failed: ${error.message}`);
  }
}

async function applyServicePatchProposal(provider, diagnosticCollection, proposalId) {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before applying a Dogma patch proposal.");
    return;
  }
  try {
    await applyPatchProposalById(serviceConfig(), proposalId, {
      afterApply: () => refreshAfterServicePatch(provider, diagnosticCollection)
    });
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma local service patch apply failed: ${error.message}`);
  }
}

async function checkWorkspaceTrust() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before checking Dogma workspace trust.");
    return;
  }

  const config = serviceConfig();
  try {
    const result = await getTrustStatusWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs
    });
    const uri = await writeWorkspaceFile([".dogma", "trust-status.md"], renderTrustStatus(result));
    vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)}.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma workspace trust check failed: ${error.message}`);
  }
}

async function trustWorkspaceForLocalOperations() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before writing a Dogma trust policy.");
    return;
  }

  const choice = await vscode.window.showWarningMessage(
    "Dogma will write .dogma/trust.json, allowing local operations for human-data workspaces in this workspace only.",
    { modal: true },
    "Trust Workspace"
  );
  if (choice !== "Trust Workspace") return;

  const config = serviceConfig();
  try {
    const result = await trustWorkspaceWithLocalService({
      serviceUrl: config.url,
      rootPath: workspaceRootFolder().uri.fsPath,
      maxFiles: config.maxFiles,
      timeoutMs: config.timeoutMs,
      reason: "User trusted this workspace through the Dogma extension."
    });
    await writeWorkspaceFile([".dogma", "trust-write-result.json"], JSON.stringify(result, null, 2) + "\n", null);
    const uri = await writeWorkspaceFile([".dogma", "trust-write-result.md"], renderTrustWriteResult(result));
    const readiness = await writeIdeReadinessReport(config);
    vscode.window.showInformationMessage(`Dogma wrote ${vscode.workspace.asRelativePath(uri)}, updated workspace trust, and refreshed ${vscode.workspace.asRelativePath(readiness.markdownUri)}.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma trust policy write failed: ${error.message}`);
  }
}

async function previewActiveBioFile() {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showWarningMessage("Open a bioinformatics file before running Dogma preview.");
    return;
  }

  const fileName = vscode.workspace.asRelativePath(editor.document.uri);
  const panel = vscode.window.createWebviewPanel(
    "dogmaPreview",
    `Dogma Preview: ${fileName}`,
    vscode.ViewColumn.Beside,
    { enableScripts: false }
  );
  panel.webview.html = renderPreviewHtml(fileName, editor.document.getText());
}

async function applySampleValidationPatch() {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before applying a Dogma patch.");
    return;
  }

  const matches = await vscode.workspace.findFiles("**/*.nf", "**/{node_modules,.git,out,dist}/**", 20);
  if (!matches.length) {
    vscode.window.showWarningMessage("Dogma could not find a Nextflow .nf file to patch.");
    return;
  }

  const uri = matches.find((item) => item.path.endsWith("pipeline.nf")) || matches[0];
  const doc = await vscode.workspace.openTextDocument(uri);
  const text = doc.getText();

  if (text.includes("def validateSampleRow")) {
    vscode.window.showInformationMessage("Dogma sample validation helper is already present.");
    return;
  }

  const patch = applySampleValidationPatchText(text);

  if (!patch.changed) {
    vscode.window.showWarningMessage("Dogma could not find the expected sample tuple pattern to patch.");
    return;
  }

  const edit = new vscode.WorkspaceEdit();
  const fullRange = new vscode.Range(doc.positionAt(0), doc.positionAt(text.length));
  edit.replace(uri, fullRange, patch.text);
  await vscode.workspace.applyEdit(edit);
  await doc.save();
  vscode.window.showInformationMessage(`Dogma patched ${vscode.workspace.asRelativePath(uri)}.`);
}

async function ensureLocalServiceReady(config, manager, output) {
  try {
    const health = await checkLocalService({
      serviceUrl: config.url,
      timeoutMs: config.timeoutMs
    });
    return {
      ready: true,
      status: health.status || "reachable",
      url: health.url || config.url,
      already_reachable: true,
      started_by_extension: false,
      already_running: Boolean(manager.isRunning?.()),
      health
    };
  } catch (initialError) {
    const root = workspaceRootFolder();
    if (!root) {
      throw new Error("Open a workspace folder before starting the Dogma local service.");
    }
    const started = manager.start(config, root.uri.fsPath);
    output.show(true);

    try {
      const health = await waitForLocalService(config);
      return {
        ready: true,
        status: health.status || "reachable",
        url: health.url || config.url,
        already_reachable: false,
        started_by_extension: Boolean(started.started),
        already_running: Boolean(started.alreadyRunning),
        initial_error: initialError.message,
        health
      };
    } catch (error) {
      throw new Error(`Dogma local service did not become reachable at ${config.url}: ${error.message}`);
    }
  }
}

async function prepareIdeSession(provider, diagnosticCollection, manager, output) {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before preparing a Dogma IDE session.");
    return null;
  }

  const config = serviceConfig();
  try {
    const service = await ensureLocalServiceReady(config, manager, output);
    const issues = await scanWorkspace(provider, diagnosticCollection, { forceService: true, silent: true });
    if (!issues) {
      throw new Error("local-service scan did not complete.");
    }
    const readiness = await writeIdeReadinessReport(config);
    const report = buildIdeSessionReport({
      service,
      scan: {
        completed: true,
        source: provider.scanSource,
        issues
      },
      readiness: readiness.report
    });
    await writeWorkspaceFile([".dogma", "ide-session.json"], JSON.stringify(report, null, 2) + "\n", null);
    const markdownUri = await writeWorkspaceFile([".dogma", "ide-session.md"], renderIdeSession(report));
    vscode.window.showInformationMessage(`Dogma IDE session is ${report.status}; wrote ${vscode.workspace.asRelativePath(markdownUri)}.`);
    return { report, markdownUri };
  } catch (error) {
    updateProviderStatus(provider, serviceOfflineStatus(`Dogma IDE session preparation failed: ${error.message}`));
    vscode.window.showErrorMessage(`Dogma IDE session preparation failed: ${error.message}`);
    return null;
  }
}

async function checkLocalServiceCommand() {
  const config = serviceConfig();
  try {
    const health = await checkLocalService({
      serviceUrl: config.url,
      timeoutMs: config.timeoutMs
    });
    vscode.window.showInformationMessage(`Dogma local service is ${health.status || "reachable"} at ${config.url}.`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma local service is not reachable at ${config.url}: ${error.message}`);
  }
}

async function startLocalServiceCommand(manager, output) {
  if (!vscode.workspace.workspaceFolders?.length) {
    vscode.window.showWarningMessage("Open a workspace folder before starting the Dogma local service.");
    return;
  }

  const config = serviceConfig();
  const root = workspaceRootFolder().uri.fsPath;
  const started = manager.start(config, root);
  output.show(true);

  if (started.alreadyRunning) {
    vscode.window.showInformationMessage("Dogma local service process is already running from this extension session.");
    return;
  }

  try {
    const health = await waitForLocalService(config);
    vscode.window.showInformationMessage(`Dogma local service started at ${config.url} (${health.status || "reachable"}).`);
  } catch (error) {
    vscode.window.showErrorMessage(`Dogma local service did not become reachable at ${config.url}: ${error.message}`);
  }
}

async function stopLocalServiceCommand(manager) {
  const stopped = manager.stop();
  if (stopped.stopped) {
    vscode.window.showInformationMessage("Dogma local service stop requested.");
  } else {
    vscode.window.showInformationMessage("Dogma local service was not started by this extension session.");
  }
}

class DogmaCodeActionProvider {
  provideCodeActions(document, range, context) {
    if (!isCandidatePath(document.fileName)) return [];

    return codeActionDescriptors(context.diagnostics).map((descriptor) => {
      const action = new vscode.CodeAction(descriptor.title, vscode.CodeActionKind.QuickFix);
      action.command = {
        command: descriptor.command || "dogma.applySampleValidationPatch",
        title: descriptor.title,
        arguments: descriptor.proposalId ? [descriptor.proposalId] : []
      };
      action.diagnostics = context.diagnostics.filter((diagnostic) => diagnostic.source === "Dogma");
      action.isPreferred = Boolean(descriptor.isPreferred);
      return action;
    });
  }
}

function activate(context) {
  const provider = new InspectorProvider();
  const diagnosticCollection = vscode.languages.createDiagnosticCollection("dogma");
  const serviceOutput = vscode.window.createOutputChannel("Dogma Local Service");
  const serviceManager = new ServiceProcessManager({ output: serviceOutput, extensionRoot: context.extensionUri.fsPath });
  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  provider.statusBar = statusBar;
  applyStatusBarState(statusBar, idleStatus());
  const backgroundScanner = createBackgroundScanner(provider, diagnosticCollection);
  const activeEditorTracker = createActiveEditorTracker(provider);
  const artifactWatcher = vscode.workspace.createFileSystemWatcher("**/.dogma/*.json");
  artifactWatcher.onDidCreate(() => provider.refreshDogmaArtifacts());
  artifactWatcher.onDidChange(() => provider.refreshDogmaArtifacts());
  artifactWatcher.onDidDelete(() => provider.refreshDogmaArtifacts());
  context.subscriptions.push(vscode.window.registerTreeDataProvider("dogma.inspector", provider));
  context.subscriptions.push(vscode.window.registerWebviewViewProvider("dogma.sidecar", provider));
  context.subscriptions.push(vscode.workspace.registerTextDocumentContentProvider(PATCH_PREVIEW_SCHEME, new PatchPreviewDocumentProvider()));
  context.subscriptions.push(diagnosticCollection);
  context.subscriptions.push(serviceOutput);
  context.subscriptions.push(statusBar);
  context.subscriptions.push(backgroundScanner);
  context.subscriptions.push(activeEditorTracker);
  context.subscriptions.push(artifactWatcher);
  context.subscriptions.push({ dispose: () => serviceManager.stop() });
  context.subscriptions.push(vscode.commands.registerCommand("dogma.prepareIdeSession", () => prepareIdeSession(provider, diagnosticCollection, serviceManager, serviceOutput)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.scanWorkspace", () => scanWorkspace(provider, diagnosticCollection, { startService: true, manager: serviceManager, output: serviceOutput })));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.scanWithLocalService", () => scanWorkspace(provider, diagnosticCollection, { forceService: true, startService: true, manager: serviceManager, output: serviceOutput })));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.checkLocalService", checkLocalServiceCommand));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.startLocalService", () => startLocalServiceCommand(serviceManager, serviceOutput)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.stopLocalService", () => stopLocalServiceCommand(serviceManager)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.runNextIdeAction", runNextIdeAction));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.openAssistant", () => openAssistant(provider, diagnosticCollection)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.previewActiveBioFile", previewActiveBioFile));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateContextReport", () => generateContextReport(provider, diagnosticCollection)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateWorkflowGraph", () => generateWorkflowGraph(provider, diagnosticCollection)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.openGraphWorkbench", () => openGraphWorkbench(provider, diagnosticCollection)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.openBiologicalGraphWorkbench", openBiologicalGraphWorkbench));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateRunPlan", () => generateRunPlan(provider, diagnosticCollection)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateServiceAssistantContext", generateServiceAssistantContext));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateMethodGuardrails", generateMethodGuardrails));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateEvidenceLedger", generateEvidenceLedger));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateEdgeEvaluationPlan", generateEdgeEvaluationPlan));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateQurationEdgeEvaluationPlan", generateQurationEdgeEvaluationPlan));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.fetchQurationEdgePlan", fetchQurationEdgePlan));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateQurationEdgeWorkPackage", generateQurationEdgeWorkPackage));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.suggestFromQurationEdgeWorkPackage", suggestFromQurationEdgeWorkPackage));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.previewQurationEdgeSuggestedPatch", previewQurationEdgeSuggestedPatch));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateQurationEdgePatchHandoff", generateQurationEdgePatchHandoff));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.resolveQurationSelectedEdgeReadout", resolveQurationSelectedEdgeReadout));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.applyQurationEdgeSuggestedPatch", () => applyQurationEdgeSuggestedPatch(provider, diagnosticCollection)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateQurationHandoff", generateQurationHandoff));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.openQurationGraphUi", openQurationGraphUi));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.openCurrentQurationGraph", openCurrentQurationGraph));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.openQurationCanvasFromWorkspace", openQurationCanvasFromWorkspace));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.checkQurationStatus", checkQurationStatus));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.refreshQurationGraphHistory", refreshQurationGraphHistory));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.pullQurationGraphContext", pullQurationGraphContext));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.pullQurationGraphEvents", pullQurationGraphEvents));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.pullQurationFailedEvents", pullQurationFailedEvents));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.selectQurationEdge", selectQurationEdge));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.checkIdeReadiness", checkIdeReadiness));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.importWorkspaceToQuration", importWorkspaceToQuration));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.openLastQurationImport", openLastQurationImport));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateMethodsGraphSubstrate", generateMethodsGraphSubstrate));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateMethodsGraphPreflight", generateMethodsGraphPreflight));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.checkLlmProvider", checkLlmProvider));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.openAgentWorkbench", () => openAgentWorkbench(provider, diagnosticCollection)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateAgentSuggestion", generateAgentSuggestion));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateAgentHandoff", () => generateAgentHandoff(provider)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.reviewActiveFile", reviewActiveFile));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.askDogmaAboutSelection", askDogmaAboutSelection));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.reviewActiveFinding", () => reviewActiveFinding(provider, diagnosticCollection)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.openFinding", (payload) => openFinding(provider, payload)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generateServiceRunPlan", generateServiceRunPlan));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.previewServiceDryRun", previewServiceDryRun));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.executeServiceDryRun", executeServiceDryRun));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.generatePatchProposals", generatePatchProposals));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.previewServicePatchApply", previewServicePatchApply));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.previewActiveFilePatch", previewActiveFilePatch));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.applyActiveFilePatch", () => applyActiveFilePatch(provider, diagnosticCollection)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.applyServicePatch", () => applyServicePatch(provider, diagnosticCollection)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.previewServicePatchProposal", (proposalId) => previewServicePatchProposal(proposalId)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.applyServicePatchProposal", (proposalId) => applyServicePatchProposal(provider, diagnosticCollection, proposalId)));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.checkWorkspaceTrust", checkWorkspaceTrust));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.trustWorkspaceForLocalOperations", trustWorkspaceForLocalOperations));
  context.subscriptions.push(vscode.commands.registerCommand("dogma.applySampleValidationPatch", applySampleValidationPatch));
  context.subscriptions.push(vscode.languages.registerCodeActionsProvider(
    { scheme: "file" },
    new DogmaCodeActionProvider(),
    { providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] }
  ));
  context.subscriptions.push(vscode.workspace.onDidSaveTextDocument((document) => {
    if (isCandidatePath(document.fileName)) {
      backgroundScanner.schedule(250);
    }
  }));
  context.subscriptions.push(vscode.workspace.onDidChangeWorkspaceFolders(() => {
    backgroundScanner.schedule(250);
    activeEditorTracker.schedule(50);
  }));
  context.subscriptions.push(vscode.window.onDidChangeActiveTextEditor(() => {
    activeEditorTracker.schedule(50);
  }));
  context.subscriptions.push(vscode.window.onDidChangeTextEditorSelection((event) => {
    if (event.textEditor === vscode.window.activeTextEditor) {
      activeEditorTracker.schedule(100);
    }
  }));
  if (vscode.workspace.workspaceFolders?.length) {
    activeEditorTracker.schedule(50);
    backgroundScanner.schedule(750);
  }
}

function deactivate() {}

module.exports = { activate, deactivate };
