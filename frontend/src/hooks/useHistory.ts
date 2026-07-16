import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import type { GraphSummary, HypothesisEvent } from "../lib/hypothesis-client";
import { hypothesisClient } from "../services/hypothesisService";

/** Loads the persisted graph history and the recent-failures feed for the History drawer. */
export function useHistory() {
  const [graphs, setGraphs] = useState<GraphSummary[]>([]);
  const [failed, setFailed] = useState<HypothesisEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fail = useCallback((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err);
    setError(message);
    toast.error(message);
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setGraphs(await hypothesisClient.listGraphs());
    } catch (err) {
      fail(err);
    } finally {
      setLoading(false);
    }
  }, [fail]);

  const loadFailed = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setFailed(await hypothesisClient.failedEvents());
    } catch (err) {
      fail(err);
    } finally {
      setLoading(false);
    }
  }, [fail]);

  const remove = useCallback(async (graphId: string) => {
    try {
      await hypothesisClient.deleteGraph(graphId);
      setGraphs((gs) => gs.filter((g) => g.id !== graphId));
    } catch (err) {
      fail(err);
    }
  }, [fail]);

  const clearAll = useCallback(async () => {
    try {
      await hypothesisClient.clearGraphs();
      setGraphs([]);
      setFailed([]);
    } catch (err) {
      fail(err);
    }
  }, [fail]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { graphs, failed, loading, error, refresh, loadFailed, remove, clearAll };
}
