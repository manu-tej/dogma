import { useCallback, useState } from "react";
import { toast } from "sonner";

import type { GroundingProposal } from "../lib/hypothesis-client";
import { hypothesisClient } from "../services/hypothesisService";

/** On-demand ontology grounding for a node: look up a term, review, apply. */
export function useNodeGrounding(graphId: string, nodeId: string, onApplied: () => void) {
  const [proposal, setProposal] = useState<GroundingProposal | null>(null);
  const [notFound, setNotFound] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);

  const fail = useCallback((err: unknown) => {
    toast.error(err instanceof Error ? err.message : String(err));
  }, []);

  const ground = useCallback(async () => {
    setLoading(true);
    setNotFound(null);
    try {
      const result = await hypothesisClient.groundNode(graphId, nodeId);
      if (result.found) {
        setProposal(result);
      } else {
        // Surface the miss inline — a toast is too easy to miss, so the click
        // looks like it did nothing.
        setProposal(null);
        setNotFound(result.summary);
      }
    } catch (err) {
      fail(err);
    } finally {
      setLoading(false);
    }
  }, [graphId, nodeId, fail]);

  const accept = useCallback(async () => {
    if (!proposal?.proposed_edit) return;
    setApplying(true);
    try {
      await hypothesisClient.applyEdit(graphId, proposal.proposed_edit);
      setProposal(null);
      onApplied();
    } catch (err) {
      fail(err);
    } finally {
      setApplying(false);
    }
  }, [graphId, proposal, onApplied, fail]);

  const resolveIsoform = useCallback(
    async (resolvedTo: string | null) => {
      setApplying(true);
      try {
        await hypothesisClient.applyEdit(graphId, {
          op: "resolve_isoform",
          node_id: nodeId,
          resolved_to: resolvedTo,
        });
        onApplied();
      } catch (err) {
        fail(err);
      } finally {
        setApplying(false);
      }
    },
    [graphId, nodeId, onApplied, fail],
  );

  const reject = useCallback(() => setProposal(null), []);

  return { proposal, notFound, loading, applying, ground, accept, reject, resolveIsoform };
}
