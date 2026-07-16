import { useCallback, useEffect, useMemo, useRef } from "react";
import {
  type NodeChange, type EdgeChange,
  applyNodeChanges, applyEdgeChanges, useEdgesState, useNodesState,
} from "@xyflow/react";
import { toast } from "sonner";

import type { CausalGraph } from "../lib/hypothesis-client";
import {
  type ClaimRFEdge, type EntityRFNode, type XY,
  dagrePositions, mergePositions, toRFEdges, toRFNodes,
} from "../lib/hypothesis-ui/layout";
import { hypothesisClient } from "../services/hypothesisService";

const PERSIST_DEBOUNCE_MS = 400;

/** Stable signature of graph STRUCTURE (ids only) — changes here trigger a reconcile,
 * position-only changes do not. */
function structureSignature(graph: CausalGraph): string {
  const ns = graph.nodes.map((n) => n.id).sort().join(",");
  const es = graph.edges.map((e) => `${e.id}:${e.source_id}>${e.target_id}`).sort().join(",");
  return `${ns}|${es}`;
}

export function useCanvasLayout(
  graph: CausalGraph,
  selectedNodeId: string | null,
  selectedEdgeId: string | null,
) {
  const posRef = useRef<Map<string, XY>>(new Map());
  const [nodes, setNodes] = useNodesState<EntityRFNode>([]);
  const [edges, setEdges] = useEdgesState<ClaimRFEdge>([]);

  const persist = useCallback((positions: Record<string, XY>) => {
    hypothesisClient.saveLayout(graph.id, positions).catch(() => {
      toast.error("Couldn't save layout (will retry on next move)");
    });
  }, [graph.id]);

  // Reconcile when STRUCTURE changes (not on every position tick).
  const sig = structureSignature(graph);
  useEffect(() => {
    const { positions, newlyPlaced } = mergePositions(graph, posRef.current);
    posRef.current = positions;
    setNodes(toRFNodes(graph, positions, selectedNodeId));
    setEdges(toRFEdges(graph, selectedEdgeId));
    if (newlyPlaced.length > 0) {
      persist(Object.fromEntries(newlyPlaced.map((id) => [id, positions.get(id)!])));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig]);

  // Selection-only updates: never recompute positions.
  useEffect(() => {
    setNodes((ns) => ns.map((n) => ({
      ...n, selected: n.id === selectedNodeId,
      data: { ...n.data, selected: n.id === selectedNodeId },
    })));
  }, [selectedNodeId, setNodes]);
  useEffect(() => {
    setEdges((es) => es.map((e) => ({ ...e, selected: e.id === selectedEdgeId })));
  }, [selectedEdgeId, setEdges]);

  // Debounced position persistence.
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const schedulePersist = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      persist(Object.fromEntries(posRef.current));
    }, PERSIST_DEBOUNCE_MS);
  }, [persist]);
  // Cancel a queued persist when the graph changes (or on unmount) so a debounce
  // armed for the previous graph can't fire and write its positions to the new one.
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, [graph.id]);

  const onNodesChange = useCallback((changes: NodeChange<EntityRFNode>[]) => {
    setNodes((ns) => {
      const next = applyNodeChanges(changes, ns) as EntityRFNode[];
      for (const n of next) posRef.current.set(n.id, n.position);
      return next;
    });
    if (changes.some((c) => c.type === "position" && c.dragging === false)) {
      schedulePersist();
    }
  }, [setNodes, schedulePersist]);

  const onEdgesChange = useCallback((changes: EdgeChange<ClaimRFEdge>[]) => {
    setEdges((es) => applyEdgeChanges(changes, es) as ClaimRFEdge[]);
  }, [setEdges]);

  // Re-tidy: re-run dagre over everything, persist, and apply.
  const retidy = useCallback(() => {
    const positions = dagrePositions(graph);
    posRef.current = positions;
    setNodes(toRFNodes(graph, positions, selectedNodeId));
    persist(Object.fromEntries(positions));
  }, [graph, selectedNodeId, setNodes, persist]);

  // Nudge selected nodes by (dx,dy) and persist (debounced).
  const nudge = useCallback((dx: number, dy: number) => {
    setNodes((ns) => {
      const next = ns.map((n) =>
        n.selected ? { ...n, position: { x: n.position.x + dx, y: n.position.y + dy } } : n,
      );
      for (const n of next) posRef.current.set(n.id, n.position);
      return next;
    });
    schedulePersist();
  }, [setNodes, schedulePersist]);

  return useMemo(
    () => ({ nodes, edges, onNodesChange, onEdgesChange, retidy, nudge }),
    [nodes, edges, onNodesChange, onEdgesChange, retidy, nudge],
  );
}
