import { describe, expect, it } from "vitest";

import { demoGraph, demoGraphAfterApprove, demoProposal } from "../lib/hypothesis-ui/fixtures";
import { type HypothesisState, hypothesisReducer, initialHypothesisState } from "./hypothesisReducer";

describe("hypothesisReducer", () => {
  it("QUERY_START sets loading and clears prior graph", () => {
    const s = hypothesisReducer(
      { ...initialHypothesisState, graph: demoGraph },
      { type: "QUERY_START", query: "q" },
    );
    expect(s.status).toBe("loading");
    expect(s.query).toBe("q");
    expect(s.graph).toBeNull();
    expect(s.error).toBeNull();
  });

  it("START_OK simple records the kind and stays without a graph", () => {
    const s = hypothesisReducer(initialHypothesisState, {
      type: "START_OK", result: { kind: "simple", graph_id: null },
    });
    expect(s.startKind).toBe("simple");
    expect(s.status).toBe("ready");
    expect(s.graph).toBeNull();
  });

  it("GRAPH_OK stores the graph and becomes ready", () => {
    const s = hypothesisReducer(initialHypothesisState, { type: "GRAPH_OK", graph: demoGraph });
    expect(s.graph?.id).toBe("g-demo");
    expect(s.status).toBe("ready");
  });

  it("GRAPH_OK adopts the graph's query when state has none (seeding build / history load → Re-roll works)", () => {
    const s = hypothesisReducer(initialHypothesisState, { type: "GRAPH_OK", graph: demoGraph });
    expect(s.query).toBe(demoGraph.query);
    expect(s.query).not.toBe("");
  });

  it("GRAPH_OK preserves an existing query (the /start path already set it)", () => {
    const s = hypothesisReducer(
      { ...initialHypothesisState, query: "original query" },
      { type: "GRAPH_OK", graph: { ...demoGraph, query: "something else" } },
    );
    expect(s.query).toBe("original query");
  });

  it("SELECT_EDGE then PROPOSAL_OK populates the proposal", () => {
    let s = hypothesisReducer({ ...initialHypothesisState, graph: demoGraph },
      { type: "SELECT_EDGE", edgeId: "e-egfr-kras" });
    expect(s.selectedEdgeId).toBe("e-egfr-kras");
    expect(s.proposal).toBeNull();
    s = hypothesisReducer(s, { type: "PROPOSAL_OK", proposal: demoProposal });
    expect(s.proposal?.edge_id).toBe("e-egfr-kras");
  });

  it("APPROVE_START -> GRAPH_OK flips the edge and clears the proposal", () => {
    let s: HypothesisState = {
      ...initialHypothesisState, graph: demoGraph,
      selectedEdgeId: "e-egfr-kras", proposal: demoProposal, status: "ready" as const,
    };
    s = hypothesisReducer(s, { type: "APPROVE_START" });
    expect(s.status).toBe("running");
    s = hypothesisReducer(s, { type: "GRAPH_OK", graph: demoGraphAfterApprove });
    expect(s.graph?.edges.find((e) => e.id === "e-egfr-kras")?.state).toBe("supported");
    expect(s.proposal).toBeNull();
    expect(s.status).toBe("ready");
  });

  it("ERROR records the message and resets status to ready", () => {
    const s = hypothesisReducer({ ...initialHypothesisState, status: "running" },
      { type: "ERROR", message: "boom" });
    expect(s.error).toBe("boom");
    expect(s.status).toBe("ready");
  });

  it("GRAPH_OK clears a selected node that no longer exists (e.g. after a merge)", () => {
    const s = hypothesisReducer(
      { ...initialHypothesisState, graph: demoGraph, selectedNodeId: "P01116" },
      { type: "GRAPH_OK", graph: { ...demoGraph, nodes: demoGraph.nodes.filter((n) => n.id !== "P01116") } },
    );
    expect(s.selectedNodeId).toBeNull();
  });

  it("GRAPH_OK keeps a selected node that still exists", () => {
    const s = hypothesisReducer(
      { ...initialHypothesisState, graph: demoGraph, selectedNodeId: "P00533" },
      { type: "GRAPH_OK", graph: demoGraph },
    );
    expect(s.selectedNodeId).toBe("P00533");
  });

  it("GRAPH_OK clears a selected edge that no longer exists (e.g. after a split)", () => {
    const s = hypothesisReducer(
      { ...initialHypothesisState, graph: demoGraph, selectedEdgeId: "e-egfr-kras" },
      { type: "GRAPH_OK", graph: { ...demoGraph, edges: demoGraph.edges.filter((e) => e.id !== "e-egfr-kras") } },
    );
    expect(s.selectedEdgeId).toBeNull();
  });

  it("SELECT_NODE sets the node and clears edge selection; SELECT_EDGE clears node", () => {
    let s = hypothesisReducer({ ...initialHypothesisState, selectedEdgeId: "e1" },
      { type: "SELECT_NODE", nodeId: "n1" });
    expect(s.selectedNodeId).toBe("n1");
    expect(s.selectedEdgeId).toBeNull();
    s = hypothesisReducer(s, { type: "SELECT_EDGE", edgeId: "e2" });
    expect(s.selectedEdgeId).toBe("e2");
    expect(s.selectedNodeId).toBeNull();
  });

  it("RESET from any non-initial state returns initialHypothesisState (deep equal)", () => {
    const nonInitial: HypothesisState = {
      status: "ready",
      query: "some query",
      startKind: "investigative",
      graph: demoGraph,
      selectedEdgeId: "e-egfr-kras",
      selectedNodeId: "P00533",
      proposal: demoProposal,
      error: "some error",
    };
    const s = hypothesisReducer(nonInitial, { type: "RESET" });
    expect(s).toEqual(initialHypothesisState);
  });
});
