"use strict";

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;"
  })[character]);
}

function listText(value) {
  if (Array.isArray(value)) return value.length ? value.join(", ") : "none";
  if (value && typeof value === "object") return Object.entries(value).map(([key, item]) => `${key}: ${item ?? "not declared"}`).join(", ");
  return value ?? "not declared";
}

function renderBiologicalGraphWorkbenchHtml(graph) {
  const payload = JSON.stringify(graph || {}).replace(/</g, "\\u003c");
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];
  const firstEdgeId = edges[0]?.id || null;
  const nodeCards = nodes.map((node) => (
    `<div class="node-card">
      <strong>${escapeHtml(node.label)}</strong>
      <span>${escapeHtml(node.kind)} - ${escapeHtml(node.status)}</span>
      <em>${escapeHtml(node.id)}</em>
    </div>`
  )).join("") || '<div class="empty-state">No local biological guardrail nodes were returned by the local service.</div>';
  const edgeButtons = edges.map((edge) => (
    `<button class="edge-button ${edge.id === firstEdgeId ? "active" : ""}" data-edge="${escapeHtml(edge.id)}">
      <span>${escapeHtml(edge.title || `${edge.source} -> ${edge.target}`)}</span>
      <strong>${escapeHtml(edge.status)}</strong>
    </button>`
  )).join("") || '<div class="empty-state">No local biological guardrail edges were returned by the local service.</div>';
  const policyItems = [
    "Selected biological edges seed EvaluationPlans.",
    "methods-graph is a guardrail substrate, not a truth oracle.",
    "Coverage gaps remain explicit work items.",
    "Evidence stays factual and provenance-linked."
  ].map((item) => `<li>${escapeHtml(item)}</li>`).join("");

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { margin: 0; font-family: var(--vscode-font-family); color: var(--vscode-foreground); background: var(--vscode-editor-background); }
    .shell { display: grid; grid-template-columns: minmax(260px, 340px) minmax(420px, 1fr) minmax(320px, 400px); height: 100vh; }
    aside, main { min-width: 0; min-height: 0; overflow: auto; }
    aside { border-right: 1px solid var(--vscode-panel-border); padding: 14px; }
    .right { border-left: 1px solid var(--vscode-panel-border); border-right: 0; }
    h1, h2, h3 { margin: 0; }
    h1 { font-size: 17px; }
    h2 { font-size: 12px; text-transform: uppercase; color: var(--vscode-descriptionForeground); margin: 18px 0 8px; }
    .summary { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-top: 12px; }
    .metric, .node-card, .dossier-section { border: 1px solid var(--vscode-panel-border); border-radius: 6px; padding: 10px; background: var(--vscode-sideBar-background); }
    .metric span, .node-card span, .node-card em, .muted { display: block; color: var(--vscode-descriptionForeground); font-size: 12px; font-style: normal; }
    .edge-button { width: 100%; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; text-align: left; align-items: center; border: 1px solid var(--vscode-panel-border); background: var(--vscode-button-secondaryBackground); color: var(--vscode-button-secondaryForeground); border-radius: 6px; padding: 9px; margin-bottom: 8px; cursor: pointer; }
    .edge-button.active { border-color: var(--vscode-focusBorder); background: var(--vscode-list-activeSelectionBackground); color: var(--vscode-list-activeSelectionForeground); }
    .edge-button strong, .status { font-size: 11px; text-transform: uppercase; letter-spacing: 0; }
    .canvas { padding: 18px; }
    .node-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; }
    .edge-lane { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
    .edge-chip { border: 1px solid var(--vscode-panel-border); border-radius: 999px; padding: 7px 10px; font-size: 12px; background: var(--vscode-editorWidget-background); }
    .dossier-section { margin-bottom: 10px; }
    .dossier-section h3 { font-size: 13px; margin-bottom: 6px; }
    .action-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
    .action-row button { border: 0; border-radius: 6px; background: var(--vscode-button-background); color: var(--vscode-button-foreground); padding: 8px 10px; cursor: pointer; }
    .action-row button:hover { background: var(--vscode-button-hoverBackground); }
    dl { margin: 0; }
    .fact-row { display: grid; grid-template-columns: 130px minmax(0, 1fr); gap: 8px; padding: 5px 0; border-bottom: 1px solid var(--vscode-panel-border); }
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
      <h1>Dogma Local Biological Edge Guardrails</h1>
      <div class="summary">
        <div class="metric"><strong>${escapeHtml(graph.status || "unknown")}</strong><span>status</span></div>
        <div class="metric"><strong>${escapeHtml(graph.summary?.nodes || 0)}</strong><span>nodes</span></div>
        <div class="metric"><strong>${escapeHtml(graph.summary?.edges || 0)}</strong><span>edges</span></div>
      </div>
      <h2>Local Biological Edges</h2>
      <div id="edgeButtons">${edgeButtons}</div>
      <h2>Policy</h2>
      <ul>${policyItems}</ul>
    </aside>
    <main class="canvas">
      <h2>Guardrail Nodes</h2>
      <div class="node-grid">${nodeCards}</div>
      <h2>Edge Map</h2>
      <div class="edge-lane">${edges.map((edge) => `<span class="edge-chip">${escapeHtml(edge.source)} ${escapeHtml(edge.relation)} ${escapeHtml(edge.target)}</span>`).join("") || '<span class="muted">No edges</span>'}</div>
    </main>
    <aside class="right">
      <h2>Selected Biological Edge</h2>
      <div id="dossier"></div>
    </aside>
  </div>
  <script>
    const vscode = typeof acquireVsCodeApi === "function" ? acquireVsCodeApi() : null;
    const graph = ${payload};
    const edges = graph.edges || [];
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
    function listText(value) {
      if (Array.isArray(value)) return value.length ? value.join(", ") : "none";
      if (value && typeof value === "object") return Object.entries(value).map(([key, item]) => key + ": " + (item ?? "not declared")).join(", ");
      return value ?? "not declared";
    }
    function renderEdge(id) {
      const edge = byId[id] || edges[0];
      if (!edge) {
        dossier.innerHTML = '<div class="empty-state">No selected biological edge.</div>';
        return;
      }
      document.querySelectorAll(".edge-button").forEach((button) => button.classList.toggle("active", button.dataset.edge === edge.id));
      const facts = edge.facts || {};
      const factRows = Object.entries(facts).map(([key, value]) => (
        '<div class="fact-row"><dt>' + escapeHtml(key) + '</dt><dd>' + escapeHtml(listText(value)) + '</dd></div>'
      )).join("");
      dossier.innerHTML = '<div class="dossier-section"><h3>' + escapeHtml(edge.title || edge.id) + ' <span class="status">' + escapeHtml(edge.status) + '</span></h3><p class="muted">' + escapeHtml(edge.question || "") + '</p><div class="action-row"><button data-action="generate-edge-plan" data-edge="' + escapeHtml(edge.id) + '">Generate Evaluation Plan</button></div></div>' +
        '<div class="dossier-section"><h3>Facts</h3><dl>' + factRows + '</dl></div>' +
        '<div class="dossier-section"><h3>Next Actions</h3><ol>' + (edge.next_actions || []).map((item) => '<li>' + escapeHtml(item) + '</li>').join("") + '</ol></div>';
      const planButton = dossier.querySelector('[data-action="generate-edge-plan"]');
      if (planButton) {
        planButton.addEventListener("click", () => {
          if (vscode) vscode.postMessage({ command: "generateEdgeEvaluationPlan", edgeId: edge.id, selectedEdge: edge.selected_edge || edge });
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
    renderEdge(${JSON.stringify(firstEdgeId)});
  </script>
</body>
</html>`;
}

module.exports = {
  renderBiologicalGraphWorkbenchHtml
};
