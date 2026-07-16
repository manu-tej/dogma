import { useCallback, useState } from "react";
import { toast } from "sonner";

import type { KGNeighbor } from "../lib/hypothesis-client";
import { hypothesisClient } from "../services/hypothesisService";

/** Fetch a node's real KG neighbors and add one as a connected node. */
export function useNodeExpand(graphId: string, nodeId: string, onApplied: () => void) {
  const [neighbors, setNeighbors] = useState<KGNeighbor[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);

  const fail = useCallback((err: unknown) => {
    toast.error(err instanceof Error ? err.message : String(err));
  }, []);

  const expand = useCallback(async () => {
    setLoading(true);
    try {
      setNeighbors(await hypothesisClient.expandNode(graphId, nodeId));
    } catch (err) {
      fail(err);
    } finally {
      setLoading(false);
    }
  }, [graphId, nodeId, fail]);

  const add = useCallback(async (n: KGNeighbor) => {
    setAdding(n.id);
    const suggested_by = n.sources.map((s) => ({
      kind: "kg_edge" as const, source: s, reference: n.relation,
    }));
    try {
      // Already in the graph -> add a provenance edge to it; otherwise add a new node.
      await hypothesisClient.applyEdit(graphId, n.existing_node_id
        ? { op: "connect_nodes", source_id: nodeId, target_id: n.existing_node_id,
            relation: n.relation, suggested_by }
        : { op: "add_connected_node", anchor_node_id: nodeId, new_label: n.symbol,
            new_type: "target", relation: n.relation, direction: "to", suggested_by });
      setNeighbors((prev) => prev?.filter((x) => x.id !== n.id) ?? null);
      onApplied();
    } catch (err) {
      fail(err);
    } finally {
      setAdding(null);
    }
  }, [graphId, nodeId, onApplied, fail]);

  return { neighbors, loading, adding, expand, add };
}
