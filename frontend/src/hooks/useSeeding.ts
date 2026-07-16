import { useCallback, useEffect, useReducer, useRef } from "react";
import { toast } from "sonner";

import type { SeedAnswer } from "../lib/hypothesis-client";
import { hypothesisClient } from "../services/hypothesisService";
import { initialSeedingState, seedingReducer } from "./seedingReducer";

export function useSeeding(onBuilt: (graphId: string) => void) {
  const [state, dispatch] = useReducer(seedingReducer, initialSeedingState);
  const seedToken = useRef(0);

  const fail = useCallback((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err);
    toast.error(message);
    dispatch({ type: "ERROR", message });
  }, []);

  useEffect(() => {
    if (state.status !== "seeding") return;
    const token = ++seedToken.current;
    (async () => {
      try {
        const step = await hypothesisClient.seed(state.query, state.answers);
        if (token === seedToken.current) dispatch({ type: "STEP", step });
      } catch (err) {
        if (token === seedToken.current) fail(err);
      }
    })();
  }, [state.status, state.query, state.answers, fail]);

  const runQuery = useCallback((query: string) => {
    if (query.trim()) dispatch({ type: "QUERY_SUBMIT", query: query.trim() });
  }, []);

  const answer = useCallback((a: SeedAnswer) => dispatch({ type: "ANSWER", answer: a }), []);
  const dropNode = useCallback((nodeId: string) => dispatch({ type: "DROP_NODE", nodeId }), []);

  const build = useCallback(async () => {
    if (!state.skeleton) return;
    dispatch({ type: "BUILD_START" });
    try {
      const res = await hypothesisClient.build(state.query, state.skeleton);
      if (res.graph_id) onBuilt(res.graph_id);
      else fail(new Error("Build returned no graph id."));
    } catch (err) {
      fail(err);
    }
  }, [state.skeleton, state.query, onBuilt, fail]);

  const skipAndBuild = useCallback(async () => {
    dispatch({ type: "BUILD_START" });
    try {
      const res = await hypothesisClient.start(state.query || "investigate");
      if (res.graph_id) onBuilt(res.graph_id);
      else fail(new Error("Could not build a graph from that query."));
    } catch (err) {
      fail(err);
    }
  }, [state.query, onBuilt, fail]);

  return { state, runQuery, answer, dropNode, build, skipAndBuild };
}
