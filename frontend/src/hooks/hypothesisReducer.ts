import type {
  CausalGraph, ProposedTest, QueryKind, StartResult,
} from "../lib/hypothesis-client";

export type HypothesisStatus = "idle" | "loading" | "ready" | "running" | "error";

export interface HypothesisState {
  status: HypothesisStatus;
  query: string;
  startKind: QueryKind | null;
  graph: CausalGraph | null;
  selectedEdgeId: string | null;
  selectedNodeId: string | null;
  proposal: ProposedTest | null;
  error: string | null;
}

export const initialHypothesisState: HypothesisState = {
  status: "idle",
  query: "",
  startKind: null,
  graph: null,
  selectedEdgeId: null,
  selectedNodeId: null,
  proposal: null,
  error: null,
};

export type HypothesisAction =
  | { type: "QUERY_START"; query: string }
  | { type: "START_OK"; result: StartResult }
  | { type: "GRAPH_OK"; graph: CausalGraph }
  | { type: "SELECT_EDGE"; edgeId: string | null }
  | { type: "SELECT_NODE"; nodeId: string | null }
  | { type: "PROPOSAL_OK"; proposal: ProposedTest | null }
  | { type: "APPROVE_START" }
  | { type: "ERROR"; message: string }
  | { type: "RESET" };

export function hypothesisReducer(
  state: HypothesisState,
  action: HypothesisAction,
): HypothesisState {
  switch (action.type) {
    case "QUERY_START":
      return {
        ...initialHypothesisState,
        status: "loading",
        query: action.query,
      };
    case "START_OK":
      // Investigative flows fetch the graph next (GRAPH_OK); simple is terminal here.
      return {
        ...state,
        startKind: action.result.kind,
        status: action.result.kind === "simple" ? "ready" : state.status,
      };
    case "GRAPH_OK": {
      // A merge/split can delete the selected element; drop a selection the new graph no longer contains.
      const nodeStillPresent = action.graph.nodes.some((n) => n.id === state.selectedNodeId);
      const edgeStillPresent = action.graph.edges.some((e) => e.id === state.selectedEdgeId);
      return {
        ...state,
        // Adopt the graph's own query when we don't already have one (loadGraph from a
        // seeding build or a history click never set it), so Re-roll can re-run /start.
        query: state.query || action.graph.query,
        graph: action.graph,
        status: "ready",
        proposal: null,
        selectedNodeId: nodeStillPresent ? state.selectedNodeId : null,
        selectedEdgeId: edgeStillPresent ? state.selectedEdgeId : null,
      };
    }
    case "SELECT_EDGE":
      return { ...state, selectedEdgeId: action.edgeId, selectedNodeId: null, proposal: null };
    case "SELECT_NODE":
      return { ...state, selectedNodeId: action.nodeId, selectedEdgeId: null, proposal: null };
    case "PROPOSAL_OK":
      return { ...state, proposal: action.proposal };
    case "APPROVE_START":
      return { ...state, status: "running", error: null };
    case "ERROR":
      return { ...state, status: "ready", error: action.message };
    case "RESET":
      return initialHypothesisState;
    default:
      return state;
  }
}
