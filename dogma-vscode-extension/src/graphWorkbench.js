"use strict";

const METHOD_CONTRACTS = {
  FASTQC: {
    methodId: "m:fastqc",
    operation: "sequencing quality control",
    assumptions: ["FASTQ reads are paired with declared samples."]
  },
  ALIGN_STAR: {
    methodId: "m:star",
    operation: "splice-aware RNA-seq alignment",
    assumptions: ["Genome build and annotation are declared before interpreting alignments."]
  },
  FEATURECOUNTS: {
    methodId: "m:featurecounts",
    operation: "gene-level count assignment",
    assumptions: ["Annotation release and strandedness are explicit."]
  },
  MULTIQC: {
    methodId: "m:multiqc",
    operation: "aggregate sequencing QC",
    assumptions: ["Upstream QC outputs are attributable to samples."]
  },
  DESEQ2: {
    methodId: "m:deseq2",
    operation: "differential expression",
    assumptions: ["Replicates and contrasts are declared."]
  }
};

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  })[character]);
}

function edgeId(graph, edge, index) {
  return `${graph.file}:${edge.from}->${edge.to}:${index + 1}`.replace(/[^A-Za-z0-9_.:>-]/g, "_");
}

function issueSummary(issues) {
  const errors = issues.filter((issue) => issue.severity === "error").length;
  const warnings = issues.filter((issue) => issue.severity === "warning").length;
  return {
    errors,
    warnings,
    status: errors ? "blocked" : warnings ? "review" : "ready"
  };
}

function processByName(graph) {
  return Object.fromEntries((graph.processes || []).map((process) => [process.name, process]));
}

function methodLabel(name) {
  const contract = METHOD_CONTRACTS[name];
  return contract ? `${contract.methodId} (${contract.operation})` : "coverage gap";
}

function edgeStatus(summary, fromProcess, toProcess) {
  if (summary.errors > 0) return "blocked";
  if (!METHOD_CONTRACTS[fromProcess.name] || !METHOD_CONTRACTS[toProcess.name]) return "gap";
  if (!fromProcess.container || !toProcess.container) return "gap";
  return summary.warnings > 0 ? "review" : "ready";
}

function edgeDossier(summary, graph, edge, id) {
  const processes = processByName(graph);
  const fromProcess = processes[edge.from] || { name: edge.from, file: graph.file };
  const toProcess = processes[edge.to] || { name: edge.to, file: graph.file };
  const status = edgeStatus(summary, fromProcess, toProcess);
  const missingContainers = [fromProcess, toProcess].filter((process) => !process.container).map((process) => process.name);
  const missingMethods = [fromProcess, toProcess].filter((process) => !METHOD_CONTRACTS[process.name]).map((process) => process.name);
  const assumptions = [METHOD_CONTRACTS[fromProcess.name], METHOD_CONTRACTS[toProcess.name]]
    .filter(Boolean)
    .flatMap((contract) => contract.assumptions);

  return {
    id,
    from: edge.from,
    to: edge.to,
    title: `${edge.from} -> ${edge.to}`,
    status,
    source: `${graph.file}: inferred call order`,
    facts: {
      fromMethod: methodLabel(edge.from),
      toMethod: methodLabel(edge.to),
      fromContainer: fromProcess.container || "missing",
      toContainer: toProcess.container || "missing",
      blockers: summary.errors,
      warnings: summary.warnings,
      missingContainers,
      missingMethods,
      assumptions
    },
    nextActions: [
      missingMethods.length ? `Add or connect methods-graph contracts for ${missingMethods.join(", ")}.` : "Method contracts are locally grounded.",
      missingContainers.length ? `Declare containers for ${missingContainers.join(", ")} before real execution.` : "Executor/container coverage is present.",
      summary.errors ? "Resolve error-level Dogma findings before execution." : "Keep execution dry-run/stub-run until explicitly approved.",
      "Record evidence as factual observations, not support/refute verdicts."
    ]
  };
}

function buildGraphWorkbenchModel(graphs, context = {}, issues = []) {
  const summary = issueSummary(issues || []);
  const graphModels = (graphs || []).map((graph) => {
    const edges = (graph.edges || []).map((edge, index) => edgeDossier(summary, graph, edge, edgeId(graph, edge, index)));
    return {
      file: graph.file,
      processes: graph.processes || [],
      channels: graph.channels || [],
      calls: graph.calls || [],
      edges
    };
  });
  const allEdges = graphModels.flatMap((graph) => graph.edges);

  return {
    title: "Dogma Local Workflow Guardrails",
    summary,
    context: {
      assay: context.assay || context.metadata?.assay || "not declared",
      reference: context.reference?.genome_build || context.reference?.genomeBuild || "not declared",
      annotation: context.reference?.annotation || "not declared",
      workflowProcesses: context.workflowProcesses || context.workflow_processes || []
    },
    graphs: graphModels,
    selectedEdgeId: allEdges[0]?.id || null,
    policy: [
      "Local workflow guardrails and chat should operate on the same workflow substrate.",
      "A selected edge is the unit for method grounding, evidence, and workflow gating.",
      "Missing method/container coverage is a gap, not inferred success.",
      "The workbench records factual observations, not biological support/refute verdicts."
    ]
  };
}

function renderGraphWorkbenchHtml(model) {
  const payload = JSON.stringify(model).replace(/</g, "\\u003c");
  const edgeButtons = model.graphs.flatMap((graph) => graph.edges.map((edge) => (
    `<button class="edge-button ${edge.id === model.selectedEdgeId ? "active" : ""}" data-edge="${escapeHtml(edge.id)}">
      <span>${escapeHtml(edge.title)}</span>
      <strong>${escapeHtml(edge.status)}</strong>
    </button>`
  ))).join("") || '<div class="empty-state">No inferred workflow edges were detected. Add process calls or run a workflow scan.</div>';
  const processNodes = model.graphs.flatMap((graph) => graph.processes.map((process) => (
    `<div class="process-node">
      <strong>${escapeHtml(process.name)}</strong>
      <span>${escapeHtml(graph.file)}:${process.line}</span>
      <em>${escapeHtml(process.container || "container missing")}</em>
    </div>`
  ))).join("") || '<div class="empty-state">No workflow processes detected.</div>';
  const policyItems = model.policy.map((item) => `<li>${escapeHtml(item)}</li>`).join("");

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { margin: 0; font-family: var(--vscode-font-family); color: var(--vscode-foreground); background: var(--vscode-editor-background); }
    .shell { display: grid; grid-template-columns: minmax(260px, 330px) minmax(420px, 1fr) minmax(300px, 380px); height: 100vh; }
    aside, main { min-width: 0; min-height: 0; overflow: auto; }
    aside { border-right: 1px solid var(--vscode-panel-border); padding: 14px; }
    .right { border-left: 1px solid var(--vscode-panel-border); border-right: 0; }
    h1, h2, h3 { margin: 0; }
    h1 { font-size: 17px; }
    h2 { font-size: 12px; text-transform: uppercase; color: var(--vscode-descriptionForeground); margin: 18px 0 8px; }
    .summary { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-top: 12px; }
    .metric, .process-node, .dossier-section { border: 1px solid var(--vscode-panel-border); border-radius: 6px; padding: 10px; background: var(--vscode-sideBar-background); }
    .metric span, .process-node span, .process-node em, .muted { display: block; color: var(--vscode-descriptionForeground); font-size: 12px; font-style: normal; }
    .edge-button { width: 100%; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; text-align: left; align-items: center; border: 1px solid var(--vscode-panel-border); background: var(--vscode-button-secondaryBackground); color: var(--vscode-button-secondaryForeground); border-radius: 6px; padding: 9px; margin-bottom: 8px; cursor: pointer; }
    .edge-button.active { border-color: var(--vscode-focusBorder); background: var(--vscode-list-activeSelectionBackground); color: var(--vscode-list-activeSelectionForeground); }
    .edge-button strong, .status { font-size: 11px; text-transform: uppercase; letter-spacing: 0; }
    .canvas { padding: 18px; }
    .process-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }
    .edge-lane { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
    .edge-chip { border: 1px solid var(--vscode-panel-border); border-radius: 999px; padding: 7px 10px; font-size: 12px; background: var(--vscode-editorWidget-background); }
    .dossier-section { margin-bottom: 10px; }
    .dossier-section h3 { font-size: 13px; margin-bottom: 6px; }
    .action-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
    .action-row button { border: 0; border-radius: 6px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); padding: 8px 10px; cursor: pointer; }
    .action-row button:hover { background: var(--vscode-button-hoverBackground); }
    dl { margin: 0; }
    .fact-row { display: grid; grid-template-columns: 120px minmax(0, 1fr); gap: 8px; padding: 5px 0; border-bottom: 1px solid var(--vscode-panel-border); }
    .fact-row:last-child { border-bottom: 0; }
    dt { color: var(--vscode-descriptionForeground); }
    dd { margin: 0; }
    ul, ol { padding-left: 18px; }
    li { margin: 6px 0; }
    .empty-state { color: var(--vscode-descriptionForeground); border: 1px dashed var(--vscode-panel-border); border-radius: 6px; padding: 12px; }
    @media (max-width: 980px) { .shell { grid-template-columns: 1fr; height: auto; } aside, .right { border: 0; border-bottom: 1px solid var(--vscode-panel-border); } }
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <h1>Dogma Local Workflow Guardrails</h1>
      <div class="summary">
        <div class="metric"><strong>${escapeHtml(model.summary.status)}</strong><span>status</span></div>
        <div class="metric"><strong>${model.summary.errors}</strong><span>errors</span></div>
        <div class="metric"><strong>${model.summary.warnings}</strong><span>warnings</span></div>
      </div>
      <h2>Workflow Edges</h2>
      <div id="edgeButtons">${edgeButtons}</div>
      <h2>Policy</h2>
      <ul>${policyItems}</ul>
    </aside>
    <main class="canvas">
      <h2>Workflow Processes</h2>
      <div class="process-grid">${processNodes}</div>
      <h2>Edge Map</h2>
      <div class="edge-lane">${model.graphs.flatMap((graph) => graph.edges.map((edge) => `<span class="edge-chip">${escapeHtml(edge.from)} -> ${escapeHtml(edge.to)}</span>`)).join("") || '<span class="muted">No edges</span>'}</div>
    </main>
    <aside class="right">
      <h2>Selected Edge Dossier</h2>
      <div id="dossier"></div>
    </aside>
  </div>
  <script>
    const vscode = typeof acquireVsCodeApi === "function" ? acquireVsCodeApi() : null;
    const model = ${payload};
    const edges = model.graphs.flatMap((graph) => graph.edges);
    const byId = Object.fromEntries(edges.map((edge) => [edge.id, edge]));
    const dossier = document.getElementById("dossier");
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (character) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
      })[character]);
    }
    function renderEdge(id) {
      const edge = byId[id] || edges[0];
      if (!edge) {
        dossier.innerHTML = '<div class="empty-state">No selected edge.</div>';
        return;
      }
      document.querySelectorAll(".edge-button").forEach((button) => button.classList.toggle("active", button.dataset.edge === edge.id));
      const factRows = Object.entries(edge.facts).map(([key, value]) => {
        const formatted = Array.isArray(value) ? (value.length ? value.join(", ") : "none") : value;
        return '<div class="fact-row"><dt>' + escapeHtml(key) + '</dt><dd>' + escapeHtml(formatted) + '</dd></div>';
      }).join("");
      dossier.innerHTML = '<div class="dossier-section"><h3>' + escapeHtml(edge.title) + ' <span class="status">' + escapeHtml(edge.status) + '</span></h3><p class="muted">' + escapeHtml(edge.source) + '</p><div class="action-row"><button data-action="generate-edge-plan" data-edge="' + escapeHtml(edge.id) + '">Generate Edge Evaluation Plan</button></div></div>' +
        '<div class="dossier-section"><h3>Facts</h3><dl>' + factRows + '</dl></div>' +
        '<div class="dossier-section"><h3>Next Actions</h3><ol>' + edge.nextActions.map((item) => '<li>' + escapeHtml(item) + '</li>').join("") + '</ol></div>';
      const planButton = dossier.querySelector('[data-action="generate-edge-plan"]');
      if (planButton) {
        planButton.addEventListener("click", () => {
          if (vscode) {
            vscode.postMessage({ command: "generateEdgeEvaluationPlan", edgeId: edge.id });
          }
        });
      }
    }
    window.addEventListener("message", (event) => {
      if (event.data && event.data.command === "edgeEvaluationPlanStatus") {
        const notice = document.createElement("div");
        notice.className = "dossier-section";
        notice.textContent = event.data.message || "Edge evaluation plan request completed.";
        dossier.prepend(notice);
      }
    });
    document.querySelectorAll(".edge-button").forEach((button) => button.addEventListener("click", () => renderEdge(button.dataset.edge)));
    renderEdge(model.selectedEdgeId);
  </script>
</body>
</html>`;
}

module.exports = {
  buildGraphWorkbenchModel,
  renderGraphWorkbenchHtml
};
