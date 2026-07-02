"use strict";

function normalizeState(value) {
  return String(value || "").trim().toLowerCase();
}

function gateById(readiness = {}, id) {
  const gates = Array.isArray(readiness.gates) ? readiness.gates : [];
  return gates.find((gate) => gate.id === id) || null;
}

function gateNeedsAttention(gate) {
  const state = normalizeState(gate?.state);
  return state === "blocked" || state === "warning" || state === "unknown";
}

function graphFromArtifacts(artifacts = {}) {
  return artifacts.qurationGraph || artifacts.qurationEdgeSelection?.quration_graph || artifacts.qurationEdgeWorkPackage?.quration_graph || null;
}

function edgeFromArtifacts(artifacts = {}) {
  return artifacts.qurationEdgeSelection?.selected_edge || artifacts.qurationEdgeWorkPackage?.selected_edge || null;
}

function workPackageMatchesSelection(artifacts = {}) {
  const selectedEdgeId = String(artifacts.qurationEdgeSelection?.selected_edge?.id || "").trim();
  const packageEdgeId = String(artifacts.qurationEdgeWorkPackage?.edge_id || artifacts.qurationEdgeWorkPackage?.selected_edge?.id || "").trim();
  if (!selectedEdgeId || !packageEdgeId) return false;
  return selectedEdgeId === packageEdgeId;
}

function edgeArtifactMatchesSelection(artifacts = {}, artifact) {
  const selectedEdgeId = String(artifacts.qurationEdgeSelection?.selected_edge?.id || "").trim();
  const artifactEdgeId = String(artifact?.edge_id || artifact?.selected_edge?.id || "").trim();
  if (!selectedEdgeId || !artifactEdgeId) return false;
  return selectedEdgeId === artifactEdgeId;
}

function hasPatchPreviewSuggestion(artifact = {}) {
  return Number(artifact.suggestion?.patch_preview_count || 0) > 0;
}

function trustPolicyAllowsLocalOperations(policy = {}) {
  if (!policy || policy.trusted !== true) return false;
  if (policy.allow_local_operations === true) return true;
  return Array.isArray(policy.allowed_data_classes) && policy.allowed_data_classes.includes("human_data");
}

function llmProviderReady(status = {}) {
  const readyStatuses = new Set(["ready", "configured", "available", "ok", "llm_ready", "claude_ready"]);
  return readyStatuses.has(normalizeState(status.status)) && status.provider !== "none";
}

function deriveNextIdeAction(artifacts = {}) {
  const readiness = artifacts.ideReadiness || {};
  if (!readiness.contract_version) {
    return {
      command: "dogma.prepareIdeSession",
      label: "Prepare IDE Session",
      reason: "No IDE readiness artifact is available."
    };
  }

  const localService = gateById(readiness, "local_service");
  if (gateNeedsAttention(localService)) {
    return {
      command: "dogma.startLocalService",
      label: "Start Local Service",
      reason: localService.detail || "The local Dogma service is not ready."
    };
  }

  const workspaceTrust = gateById(readiness, "workspace_trust");
  if (normalizeState(workspaceTrust?.state) === "blocked") {
    if (trustPolicyAllowsLocalOperations(artifacts.trustPolicy)) {
      return {
        command: "dogma.checkIdeReadiness",
        label: "Refresh IDE Readiness",
        reason: "A trust policy is present, but the readiness artifact still shows workspace trust as blocked."
      };
    }
    return {
      command: "dogma.trustWorkspaceForLocalOperations",
      label: "Trust Workspace",
      reason: workspaceTrust.detail || "Workspace trust is blocking local operations."
    };
  }

  const llmProvider = gateById(readiness, "llm_provider");
  if (gateNeedsAttention(llmProvider)) {
    if (llmProviderReady(artifacts.llmProviderStatus)) {
      return {
        command: "dogma.checkIdeReadiness",
        label: "Refresh IDE Readiness",
        reason: "The Claude provider status is ready, but the readiness artifact still shows a provider warning."
      };
    }
    return {
      command: "dogma.checkLlmProvider",
      label: "Check LLM Provider",
      reason: llmProvider.detail || "The local Claude provider needs attention."
    };
  }

  const methodsGraph = gateById(readiness, "methods_graph");
  if (gateNeedsAttention(methodsGraph)) {
    return {
      command: "dogma.generateMethodsGraphPreflight",
      label: "Methods-Graph Preflight",
      reason: methodsGraph.detail || "Methods-graph guardrails need to be grounded before execution."
    };
  }

  const qurationGate = gateById(readiness, "quration");
  if (gateNeedsAttention(qurationGate) || artifacts.qurationStatus?.status !== "ready") {
    return {
      command: "dogma.checkQurationStatus",
      label: "Check quration Status",
      reason: qurationGate?.detail || "quration bridge status is not ready."
    };
  }

  const graph = graphFromArtifacts(artifacts);
  if (!graph?.graph_id && !graph?.id) {
    return {
      command: "dogma.pullQurationGraphContext",
      label: "Pull Graph Context",
      reason: "No current quration graph context is available in the workspace."
    };
  }

  const edge = edgeFromArtifacts(artifacts);
  if (!edge?.id) {
    return {
      command: "dogma.selectQurationEdge",
      label: "Select quration Edge",
      reason: "A quration graph is available, but no active edge is selected for IDE work."
    };
  }

  if (!workPackageMatchesSelection(artifacts)) {
    return {
      command: "dogma.generateQurationEdgeWorkPackage",
      label: "Edge Work Package",
      reason: "The selected quration edge does not yet have a matching Dogma work package."
    };
  }

  if (!edgeArtifactMatchesSelection(artifacts, artifacts.qurationEdgeAgentSuggestion)) {
    return {
      command: "dogma.suggestFromQurationEdgeWorkPackage",
      label: "Suggest From Edge Package",
      reason: "The selected quration edge has a work package but no matching Dogma agent suggestion."
    };
  }

  if (hasPatchPreviewSuggestion(artifacts.qurationEdgeAgentSuggestion) && !edgeArtifactMatchesSelection(artifacts, artifacts.qurationEdgePatchHandoff)) {
    return {
      command: "dogma.generateQurationEdgePatchHandoff",
      label: "Edge Patch Handoff",
      reason: "The edge agent suggestion includes patch preview proposals but no matching quration review handoff yet."
    };
  }

  if (edgeArtifactMatchesSelection(artifacts, artifacts.qurationEdgePatchHandoff)) {
    return {
      command: "dogma.openCurrentQurationGraph",
      label: "Open Current Graph",
      reason: "A quration edge patch handoff is ready for review in the canonical web graph UI."
    };
  }

  return {
    command: "dogma.openAgentWorkbench",
    label: "Open Agent Workbench",
    reason: "Readiness, quration graph context, selected edge, edge work package, and agent suggestion are available."
  };
}

module.exports = {
  deriveNextIdeAction
};
