import "@xyflow/react/dist/style.css";

import {
  Background, Controls, type Connection, type Edge, MiniMap, type Node,
  ReactFlow, ReactFlowProvider,
} from "@xyflow/react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import type { CausalGraph } from "../../lib/hypothesis-client";
import { useCanvasLayout } from "../../hooks/useCanvasLayout";
import { hypothesisClient } from "../../services/hypothesisService";
import { nodeTypeStyle } from "../../lib/hypothesis-ui/styling";
import type { EntityNodeData } from "../../lib/hypothesis-ui/layout";
import { Button } from "../ui/button";
import { ClaimEdge } from "./ClaimEdge";
import { EdgeSelectionContext } from "./edgeSelection";
import { EntityNode } from "./EntityNode";

const nodeTypes = { entity: EntityNode };
const edgeTypes = { claim: ClaimEdge };
const SNAP: [number, number] = [16, 16];

// Color a minimap dot by node type so it reads against the dark canvas and matches
// the on-canvas accent colors.
const miniMapNodeColor = (n: Node): string =>
  nodeTypeStyle((n.data as EntityNodeData).node.type).color;

interface CausalCanvasProps {
  graph: CausalGraph;
  graphId: string;
  selectedEdgeId: string | null;
  selectedNodeId: string | null;
  onSelectEdge: (edgeId: string | null) => void;
  onSelectNode: (nodeId: string | null) => void;
  /** Refetch the graph after a structural edit (connect/delete). */
  onGraphChanged: () => void;
  /** The investigation question, shown as the canvas header crumb. */
  title?: string;
}

function CausalCanvasInner({
  graph, graphId, selectedEdgeId, selectedNodeId,
  onSelectEdge, onSelectNode, onGraphChanged, title,
}: CausalCanvasProps) {
  const { nodes, edges, onNodesChange, onEdgesChange, retidy, nudge } =
    useCanvasLayout(graph, selectedNodeId, selectedEdgeId);
  const [snap, setSnap] = useState(true);

  const handleEdgeClick = useCallback(
    (_e: React.MouseEvent, edge: Edge) => onSelectEdge(edge.id), [onSelectEdge]);
  const handleNodeClick = useCallback(
    (_e: React.MouseEvent, node: Node) => onSelectNode(node.id), [onSelectNode]);
  const handlePaneClick = useCallback(() => {
    onSelectEdge(null); onSelectNode(null);
  }, [onSelectEdge, onSelectNode]);

  // Drag-to-connect -> user edge (relation "linked"), then refetch + select it.
  const onConnect = useCallback(async (c: Connection) => {
    if (!c.source || !c.target) return;
    try {
      await hypothesisClient.applyEdit(graphId, {
        op: "connect_nodes", source_id: c.source, target_id: c.target,
        relation: "linked", suggested_by: [], proposal_source: "user", pending: false,
      });
      onGraphChanged();
    } catch {
      toast.error("Couldn't create the link");
    }
  }, [graphId, onGraphChanged]);

  const onNodesDelete = useCallback(async (deleted: Node[]) => {
    // Confirm ONCE for the whole batch: a multi-select delete is all-or-nothing, so
    // cancelling can't leave some nodes already gone.
    const anyHasEdges = deleted.some((n) =>
      graph.edges.some((e) => e.source_id === n.id || e.target_id === n.id));
    if (anyHasEdges) {
      const what = deleted.length === 1
        ? `"${(deleted[0].data as { node?: { label?: string } } | undefined)?.node?.label ?? deleted[0].id}"`
        : `${deleted.length} nodes`;
      const its = deleted.length === 1 ? "its" : "their";
      if (!confirm(`Delete ${what} and ${its} connections?`)) {
        onGraphChanged(); // resync — restore the optimistically-removed node(s)
        return;
      }
    }
    for (const n of deleted) {
      try {
        await hypothesisClient.applyEdit(graphId, { op: "remove_node", node_id: n.id });
      } catch { toast.error("Couldn't delete node"); }
    }
    onGraphChanged();
  }, [graph.edges, graphId, onGraphChanged]);

  const onEdgesDelete = useCallback(async (deleted: Edge[]) => {
    for (const e of deleted) {
      try {
        await hypothesisClient.applyEdit(graphId, { op: "remove_edge", edge_id: e.id });
      } catch { toast.error("Couldn't delete edge"); }
    }
    onGraphChanged();
  }, [graphId, onGraphChanged]);

  // Arrow keys nudge the selection (Shift = grid step).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const step = e.shiftKey ? SNAP[0] : 1;
      const map: Record<string, [number, number]> = {
        ArrowLeft: [-step, 0], ArrowRight: [step, 0],
        ArrowUp: [0, -step], ArrowDown: [0, step],
      };
      const d = map[e.key];
      if (d && nodes.some((n) => n.selected)) { e.preventDefault(); nudge(d[0], d[1]); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [nodes, nudge]);

  const handleRetidy = useCallback(() => {
    if (confirm("Re-tidy the layout? This overwrites your manual placement.")) retidy();
  }, [retidy]);

  return (
    <div className="relative h-full w-full bg-background">
      <div className="pointer-events-none absolute left-3 top-3 z-10 max-w-[55%] truncate text-[10.5px] uppercase tracking-wider text-muted-foreground/70">
        Causal graph{title ? <span className="text-muted-foreground"> · {title}</span> : null}
      </div>
      <div className="absolute right-3 top-3 z-10 flex gap-2">
        <Button size="sm" variant="ghost" onClick={() => setSnap((s) => !s)}>
          {snap ? "Snap: on" : "Snap: off"}
        </Button>
        <Button size="sm" variant="ghost" onClick={handleRetidy}>Re-tidy</Button>
      </div>
      {/*
        Edge labels live in React Flow's `EdgeLabelRenderer` layer, outside its
        event system, so `onEdgeClick` never fires for them. The provider hands
        `ClaimEdge` the same selection call the path uses, so clicking a label
        and clicking the line do the same thing.
      */}
      <EdgeSelectionContext.Provider value={onSelectEdge}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodesDelete={onNodesDelete}
        onEdgesDelete={onEdgesDelete}
        onEdgeClick={handleEdgeClick}
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
        nodesDraggable
        nodesConnectable
        elementsSelectable
        selectionOnDrag
        snapToGrid={snap}
        snapGrid={SNAP}
        deleteKeyCode={["Backspace", "Delete"]}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} size={1} color="oklch(0.26 0.008 264)" />
        <Controls showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          className="elev rounded-md border border-border"
          style={{ backgroundColor: "var(--surface-2)" }}
          maskColor="rgba(0,0,0,0.55)"
          nodeColor={miniMapNodeColor}
          nodeStrokeColor="var(--border)"
        />
      </ReactFlow>
      </EdgeSelectionContext.Provider>
    </div>
  );
}

export function CausalCanvas(props: CausalCanvasProps) {
  // Provider so useCanvasLayout's RF state hooks have context even in isolation/tests.
  return (
    <ReactFlowProvider>
      <CausalCanvasInner {...props} />
    </ReactFlowProvider>
  );
}
