import { useCallback, useReducer } from "react";
import { toast } from "sonner";

import type { EvidenceEntry, ProposedTest } from "../lib/hypothesis-client";
import { hypothesisClient } from "../services/hypothesisService";
import {
  hypothesisReducer,
  initialHypothesisState,
} from "./hypothesisReducer";

export function useHypothesis() {
  const [state, dispatch] = useReducer(hypothesisReducer, initialHypothesisState);

  const fail = useCallback((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err);
    toast.error(message);
    dispatch({ type: "ERROR", message });
  }, []);

  const runQuery = useCallback(async (query: string) => {
    const trimmed = query.trim();
    if (!trimmed) return;
    dispatch({ type: "QUERY_START", query: trimmed });
    try {
      const result = await hypothesisClient.start(trimmed);
      dispatch({ type: "START_OK", result });
      if (result.kind === "investigative" && result.graph_id) {
        const graph = await hypothesisClient.getGraph(result.graph_id);
        dispatch({ type: "GRAPH_OK", graph });
      } else if (result.kind === "investigative") {
        // Type-valid but unusable: investigative without a graph would hang on "loading".
        fail(new Error("Server returned an investigative result without a graph id."));
      }
    } catch (err) {
      fail(err);
    }
  }, [fail]);

  const selectNode = useCallback((nodeId: string | null) => {
    dispatch({ type: "SELECT_NODE", nodeId });
  }, []);

  const selectEdge = useCallback(async (edgeId: string | null) => {
    dispatch({ type: "SELECT_EDGE", edgeId });
    if (!edgeId || !state.graph) return;
    try {
      const proposal = await hypothesisClient.nextProposal(state.graph.id);
      // Only attach the proposal if it targets the edge the user opened.
      dispatch({
        type: "PROPOSAL_OK",
        proposal: proposal && proposal.edge_id === edgeId ? proposal : null,
      });
    } catch (err) {
      fail(err);
    }
  }, [state.graph, fail]);

  /** Returns the recorded EvidenceEntry on success (graph refreshed), null on failure. */
  const approve = useCallback(async (proposed: ProposedTest): Promise<EvidenceEntry | null> => {
    if (!state.graph) return null;
    const graphId = state.graph.id;
    dispatch({ type: "APPROVE_START" });
    try {
      const entry = await hypothesisClient.approve(graphId, proposed);
      const graph = await hypothesisClient.getGraph(graphId);
      dispatch({ type: "GRAPH_OK", graph });
      toast.success(`Evidence recorded for ${proposed.edge_id}`);
      return entry;
    } catch (err) {
      fail(err);
      return null;
    }
  }, [state.graph, fail]);

  const skip = useCallback(() => {
    dispatch({ type: "PROPOSAL_OK", proposal: null });
  }, []);

  const loadGraph = useCallback(async (graphId: string) => {
    try {
      const graph = await hypothesisClient.getGraph(graphId);
      dispatch({ type: "GRAPH_OK", graph });
    } catch (err) {
      fail(err);
    }
  }, [fail]);

  const reset = useCallback(() => dispatch({ type: "RESET" }), []);

  return { state, runQuery, selectEdge, selectNode, approve, skip, loadGraph, reset };
}
