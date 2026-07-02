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

function jsonScriptPayload(value) {
  return JSON.stringify(value || {}).replace(/</g, "\\u003c");
}

function actionText(action) {
  const bits = [action.kind || "action", action.title || "Untitled action"];
  if (action.target_file) bits.push(action.target_file);
  if (action.proposal_id) bits.push(`proposal ${action.proposal_id}`);
  return bits.join(" - ");
}

function renderAgentWorkbenchHtml(state = {}) {
  const result = state.result || null;
  const suggestion = (result && result.suggestion) || {};
  const patchResult = state.patchProposals || {};
  const proposals = patchResult.proposals || [];
  const nextActions = Array.isArray(suggestion.next_actions) ? suggestion.next_actions : [];
  const risks = Array.isArray(suggestion.highest_risks) ? suggestion.highest_risks : [];
  const mustNot = Array.isArray(suggestion.must_not_do) ? suggestion.must_not_do : [];
  const latestInstruction = state.instruction || (result && result.instruction) || "Propose the next smallest safe edit for this bioinformatics workspace.";
  const payload = jsonScriptPayload({
    latestInstruction,
    useLlm: state.useLlm !== false
  });

  const actionItems = nextActions.length
    ? nextActions.map((action) => {
        const proposalButtons = action.proposal_id
          ? `<div class="row-actions">
              <button data-command="previewProposal" data-proposal="${escapeHtml(action.proposal_id)}">Open Diff</button>
              <button data-command="applyProposal" data-proposal="${escapeHtml(action.proposal_id)}">Apply</button>
            </div>`
          : "";
        return `<article class="item">
          <strong>${escapeHtml(actionText(action))}</strong>
          <p>${escapeHtml(action.rationale || "")}</p>
          ${proposalButtons}
        </article>`;
      }).join("")
    : `<div class="empty-state">No agent actions yet.</div>`;

  const proposalItems = proposals.length
    ? proposals.map((proposal) => `<article class="item">
        <strong>${escapeHtml(proposal.title || proposal.id)}</strong>
        <p>${escapeHtml(proposal.rationale || proposal.kind || "")}</p>
        <div class="meta">${escapeHtml(proposal.target_file || "")} ${proposal.id ? `- ${escapeHtml(proposal.id)}` : ""}</div>
        <div class="row-actions">
          <button data-command="previewProposal" data-proposal="${escapeHtml(proposal.id)}">Open Diff</button>
          <button data-command="applyProposal" data-proposal="${escapeHtml(proposal.id)}">Apply</button>
        </div>
      </article>`).join("")
    : `<div class="empty-state">No patch proposals available.</div>`;

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { margin: 0; color: var(--vscode-foreground); background: var(--vscode-editor-background); font-family: var(--vscode-font-family); }
    .shell { display: grid; grid-template-columns: minmax(300px, 380px) minmax(420px, 1fr); min-height: 100vh; }
    aside, main { min-width: 0; padding: 16px; }
    aside { border-right: 1px solid var(--vscode-panel-border); background: var(--vscode-sideBar-background); }
    h1, h2, h3, p { margin: 0; }
    h1 { font-size: 18px; }
    h2 { margin: 18px 0 8px; color: var(--vscode-descriptionForeground); font-size: 12px; text-transform: uppercase; letter-spacing: 0; }
    textarea { width: 100%; min-height: 118px; resize: vertical; box-sizing: border-box; border: 1px solid var(--vscode-input-border); border-radius: 6px; padding: 9px; color: var(--vscode-input-foreground); background: var(--vscode-input-background); font: inherit; }
    label { display: flex; align-items: center; gap: 8px; margin: 10px 0; color: var(--vscode-descriptionForeground); }
    button { border: 0; border-radius: 6px; padding: 8px 10px; color: var(--vscode-button-secondaryForeground); background: var(--vscode-button-secondaryBackground); cursor: pointer; }
    button.primary { width: 100%; color: var(--vscode-button-foreground); background: var(--vscode-button-background); font-weight: 600; }
    button:hover { background: var(--vscode-button-hoverBackground); color: var(--vscode-button-foreground); }
    .status { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 12px; }
    .metric, .item, .empty-state, .summary { border: 1px solid var(--vscode-panel-border); border-radius: 7px; background: var(--vscode-editorWidget-background); }
    .metric { padding: 9px; }
    .metric strong { display: block; font-size: 14px; }
    .metric span, .meta { display: block; color: var(--vscode-descriptionForeground); font-size: 12px; }
    .summary { padding: 12px; line-height: 1.45; }
    .item { padding: 11px; margin-bottom: 9px; }
    .item p { margin-top: 6px; color: var(--vscode-descriptionForeground); line-height: 1.35; }
    .row-actions { display: flex; gap: 8px; margin-top: 9px; flex-wrap: wrap; }
    ul { margin: 0; padding-left: 18px; }
    li { margin: 6px 0; }
    .empty-state { padding: 12px; color: var(--vscode-descriptionForeground); }
    .notice { margin-top: 10px; color: var(--vscode-descriptionForeground); font-size: 12px; line-height: 1.35; }
    @media (max-width: 920px) { .shell { grid-template-columns: 1fr; } aside { border-right: 0; border-bottom: 1px solid var(--vscode-panel-border); } }
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <h1>Dogma Agent</h1>
      <div class="status">
        <div class="metric"><strong>${escapeHtml(result?.status || "idle")}</strong><span>status</span></div>
        <div class="metric"><strong>${escapeHtml(result?.llm_executed ? "yes" : "no")}</strong><span>llm</span></div>
        <div class="metric"><strong>${escapeHtml(proposals.length)}</strong><span>patches</span></div>
      </div>

      <h2>Instruction</h2>
      <textarea id="instruction">${escapeHtml(latestInstruction)}</textarea>
      <label><input id="useLlm" type="checkbox" ${state.useLlm === false ? "" : "checked"}> local Claude</label>
      <button class="primary" id="runButton">Run Agent</button>
      <p class="notice">${escapeHtml(state.statusMessage || "Workspace context stays behind the Dogma local service boundary.")}</p>

      <h2>Patch Proposals</h2>
      <section>${proposalItems}</section>
    </aside>
    <main>
      <h2>Summary</h2>
      <section class="summary">${escapeHtml(suggestion.summary || result?.message || "No suggestion has run yet.")}</section>

      <h2>Next Actions</h2>
      <section>${actionItems}</section>

      <h2>Highest Risks</h2>
      <section class="summary">
        <ul>${risks.length ? risks.map((item) => `<li>${escapeHtml(item)}</li>`).join("") : "<li>No risks reported yet.</li>"}</ul>
      </section>

      <h2>Must Not Do Yet</h2>
      <section class="summary">
        <ul>${mustNot.length ? mustNot.map((item) => `<li>${escapeHtml(item)}</li>`).join("") : "<li>Do not bypass Dogma guardrails or apply patches without review.</li>"}</ul>
      </section>
    </main>
  </div>
  <script>
    const vscode = acquireVsCodeApi();
    const state = ${payload};
    document.getElementById("runButton").addEventListener("click", () => {
      vscode.postMessage({
        command: "runAgent",
        instruction: document.getElementById("instruction").value,
        useLlm: document.getElementById("useLlm").checked
      });
    });
    document.querySelectorAll("button[data-command]").forEach((button) => {
      button.addEventListener("click", () => {
        vscode.postMessage({ command: button.dataset.command, proposalId: button.dataset.proposal });
      });
    });
  </script>
</body>
</html>`;
}

module.exports = {
  renderAgentWorkbenchHtml
};
