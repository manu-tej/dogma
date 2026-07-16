import { useCallback, useState } from "react";
import { toast } from "sonner";

import type { EdgeKnowledge } from "../lib/hypothesis-client";
import { hypothesisClient } from "../services/hypothesisService";

/** On-demand "what's known" lookup for an edge against the knowledge graph. */
export function useEdgeKnowledge(graphId: string, edgeId: string) {
  const [knowledge, setKnowledge] = useState<EdgeKnowledge | null>(null);
  const [loading, setLoading] = useState(false);

  const lookup = useCallback(async () => {
    setLoading(true);
    try {
      setKnowledge(await hypothesisClient.edgeKnown(graphId, edgeId));
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [graphId, edgeId]);

  return { knowledge, loading, lookup };
}
