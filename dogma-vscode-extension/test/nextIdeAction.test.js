"use strict";

const assert = require("assert");
const { deriveNextIdeAction } = require("../src/nextIdeAction");

function readyArtifacts(overrides = {}) {
  return {
    ideReadiness: {
      contract_version: "dogma-ide-readiness.v1",
      status: "ready",
      gates: [
        { id: "local_service", state: "ready", detail: "ok" },
        { id: "workspace_trust", state: "ready", detail: "trusted" },
        { id: "llm_provider", state: "ready", detail: "claude available" },
        { id: "methods_graph", state: "ready", detail: "grounded" },
        { id: "quration", state: "ready", detail: "ready" }
      ]
    },
    qurationStatus: { contract_version: "dogma-quration-status.v1", status: "ready" },
    qurationGraph: { contract_version: "dogma-quration-graph.v1", graph_id: "graph-1" },
    qurationEdgeSelection: {
      contract_version: "dogma-quration-edge-selection.v1",
      selected_edge: { id: "edge-1" }
    },
    qurationEdgeWorkPackage: {
      contract_version: "dogma-quration-edge-work-package.v1",
      edge_id: "edge-1",
      selected_edge: { id: "edge-1" }
    },
    ...overrides
  };
}

assert.strictEqual(deriveNextIdeAction({}).command, "dogma.prepareIdeSession");

assert.strictEqual(
  deriveNextIdeAction(readyArtifacts({
    ideReadiness: {
      contract_version: "dogma-ide-readiness.v1",
      gates: [{ id: "workspace_trust", state: "blocked", detail: "untrusted" }]
    }
  })).command,
  "dogma.trustWorkspaceForLocalOperations"
);

assert.strictEqual(
  deriveNextIdeAction(readyArtifacts({
    trustPolicy: { trusted: true, allow_local_operations: true },
    ideReadiness: {
      contract_version: "dogma-ide-readiness.v1",
      gates: [{ id: "workspace_trust", state: "blocked", detail: "stale readiness" }]
    }
  })).command,
  "dogma.checkIdeReadiness"
);

assert.strictEqual(
  deriveNextIdeAction(readyArtifacts({
    ideReadiness: {
      contract_version: "dogma-ide-readiness.v1",
      gates: [
        { id: "local_service", state: "ready" },
        { id: "workspace_trust", state: "ready" },
        { id: "llm_provider", state: "warning", detail: "login required" }
      ]
    }
  })).command,
  "dogma.checkLlmProvider"
);

assert.strictEqual(
  deriveNextIdeAction(readyArtifacts({
    llmProviderStatus: { status: "ready", provider: "claude_subscription" },
    ideReadiness: {
      contract_version: "dogma-ide-readiness.v1",
      gates: [
        { id: "local_service", state: "ready" },
        { id: "workspace_trust", state: "ready" },
        { id: "llm_provider", state: "warning", detail: "stale provider status" }
      ]
    }
  })).command,
  "dogma.checkIdeReadiness"
);

assert.strictEqual(
  deriveNextIdeAction(readyArtifacts({
    ideReadiness: {
      contract_version: "dogma-ide-readiness.v1",
      gates: [
        { id: "local_service", state: "ready" },
        { id: "workspace_trust", state: "ready" },
        { id: "llm_provider", state: "ready" },
        { id: "methods_graph", state: "warning", detail: "coverage gap" }
      ]
    }
  })).command,
  "dogma.generateMethodsGraphPreflight"
);

assert.strictEqual(
  deriveNextIdeAction(readyArtifacts({ qurationGraph: null })).command,
  "dogma.pullQurationGraphContext"
);

assert.strictEqual(
  deriveNextIdeAction(readyArtifacts({ qurationEdgeSelection: null, qurationEdgeWorkPackage: null })).command,
  "dogma.selectQurationEdge"
);

assert.strictEqual(
  deriveNextIdeAction(readyArtifacts({ qurationEdgeWorkPackage: null })).command,
  "dogma.generateQurationEdgeWorkPackage"
);

assert.strictEqual(
  deriveNextIdeAction(readyArtifacts()).command,
  "dogma.suggestFromQurationEdgeWorkPackage"
);

assert.strictEqual(
  deriveNextIdeAction(readyArtifacts({
    qurationEdgeAgentSuggestion: {
      contract_version: "dogma-quration-edge-agent-suggestion.v1",
      edge_id: "edge-1",
      suggestion: { patch_preview_count: 2 }
    }
  })).command,
  "dogma.generateQurationEdgePatchHandoff"
);

assert.strictEqual(
  deriveNextIdeAction(readyArtifacts({
    qurationEdgeAgentSuggestion: {
      contract_version: "dogma-quration-edge-agent-suggestion.v1",
      edge_id: "edge-1",
      suggestion: { patch_preview_count: 0 }
    }
  })).command,
  "dogma.openAgentWorkbench"
);

assert.strictEqual(
  deriveNextIdeAction(readyArtifacts({
    qurationEdgeAgentSuggestion: {
      contract_version: "dogma-quration-edge-agent-suggestion.v1",
      edge_id: "edge-1",
      suggestion: { patch_preview_count: 2 }
    },
    qurationEdgePatchHandoff: {
      contract_version: "dogma-quration-edge-patch-handoff.v1",
      selected_edge: { id: "edge-1" }
    }
  })).command,
  "dogma.openCurrentQurationGraph"
);

console.log("next IDE action tests passed");
