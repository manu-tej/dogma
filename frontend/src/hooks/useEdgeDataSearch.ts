import { useCallback, useState } from "react";
import { toast } from "sonner";

import type { DatasetCandidate, GraphEdit } from "../lib/hypothesis-client";
import { hypothesisClient } from "../services/hypothesisService";

/** Per-edge dataset discovery: search GEO+PRIDE, then attach a pick as a SetTest. */
export function useEdgeDataSearch(graphId: string, edgeId: string, onAttached: () => void) {
  const [candidates, setCandidates] = useState<DatasetCandidate[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [attaching, setAttaching] = useState<string | null>(null);

  const fail = useCallback((err: unknown) => {
    toast.error(err instanceof Error ? err.message : String(err));
  }, []);

  const find = useCallback(async () => {
    setLoading(true);
    try {
      setCandidates(await hypothesisClient.findData(graphId, edgeId));
    } catch (err) {
      fail(err);
    } finally {
      setLoading(false);
    }
  }, [graphId, edgeId, fail]);

  const attach = useCallback(async (candidate: DatasetCandidate) => {
    setAttaching(candidate.accession);
    try {
      const edit: GraphEdit = {
        op: "set_test",
        edge_id: edgeId,
        pipeline: candidate.suggested_pipeline ?? null,
        data_accession: candidate.accession,
      };
      await hypothesisClient.applyEdit(graphId, edit);
      setCandidates(null);
      onAttached();
    } catch (err) {
      fail(err);
    } finally {
      setAttaching(null);
    }
  }, [graphId, edgeId, onAttached, fail]);

  const clear = useCallback(() => setCandidates(null), []);

  return { candidates, loading, attaching, find, attach, clear };
}
