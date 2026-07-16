import dagre from "@dagrejs/dagre";
import { type Edge, type Node, Position } from "@xyflow/react";

import type { CausalGraph, GraphEdge, GraphNode } from "../hypothesis-client";

export type EntityNodeData = { node: GraphNode; selected?: boolean };
export type ClaimEdgeData = { edge: GraphEdge };
export type EntityRFNode = Node<EntityNodeData, "entity">;
export type ClaimRFEdge = Edge<ClaimEdgeData, "claim">;

export type XY = { x: number; y: number };

const NODE_W = 180;
const NODE_H = 64;

/** Auto-layout positions (top-left corner) for every node, via dagre. */
export function dagrePositions(graph: CausalGraph): Map<string, XY> {
  const g = new dagre.graphlib.Graph({ multigraph: true });
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 60, ranksep: 90 });
  for (const node of graph.nodes) g.setNode(node.id, { width: NODE_W, height: NODE_H });
  for (const edge of graph.edges) g.setEdge(edge.source_id, edge.target_id, {}, edge.id);
  dagre.layout(g);
  const out = new Map<string, XY>();
  for (const node of graph.nodes) {
    const pos = g.node(node.id);
    out.set(node.id, { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 });
  }
  return out;
}

/**
 * Resolve each node's position: server `position` wins, else the previous live
 * position, else a dagre fallback. `newlyPlaced` lists nodes that fell back to
 * dagre AND were not previously known — i.e. brand-new nodes the caller should
 * persist once so their auto-placement becomes durable.
 */
export function mergePositions(
  graph: CausalGraph,
  prev: Map<string, XY>,
): { positions: Map<string, XY>; newlyPlaced: string[] } {
  let dagreCache: Map<string, XY> | null = null;
  const dagreFor = (id: string): XY => {
    if (dagreCache === null) dagreCache = dagrePositions(graph);
    return dagreCache.get(id)!;
  };
  const positions = new Map<string, XY>();
  const newlyPlaced: string[] = [];
  for (const node of graph.nodes) {
    if (node.position != null) {
      positions.set(node.id, { x: node.position.x, y: node.position.y });
    } else if (prev.has(node.id)) {
      positions.set(node.id, prev.get(node.id)!);
    } else {
      positions.set(node.id, dagreFor(node.id));
      newlyPlaced.push(node.id);
    }
  }
  return { positions, newlyPlaced };
}

/** Build React Flow nodes from the graph + a resolved position map. */
export function toRFNodes(
  graph: CausalGraph,
  positions: Map<string, XY>,
  selectedNodeId: string | null,
): EntityRFNode[] {
  return graph.nodes.map((node) => ({
    id: node.id,
    type: "entity",
    position: positions.get(node.id) ?? { x: 0, y: 0 },
    sourcePosition: Position.Bottom,
    targetPosition: Position.Top,
    selected: node.id === selectedNodeId,
    data: { node, selected: node.id === selectedNodeId },
  }));
}

/** Build React Flow edges from the graph. */
export function toRFEdges(graph: CausalGraph, selectedEdgeId: string | null): ClaimRFEdge[] {
  return graph.edges.map((edge) => ({
    id: edge.id,
    source: edge.source_id,
    target: edge.target_id,
    type: "claim",
    selected: edge.id === selectedEdgeId,
    data: { edge },
  }));
}

/** Back-compat: full auto-layout (used by Re-tidy and the existing test). */
export function layoutGraph(graph: CausalGraph): {
  nodes: EntityRFNode[];
  edges: ClaimRFEdge[];
} {
  const positions = dagrePositions(graph);
  return { nodes: toRFNodes(graph, positions, null), edges: toRFEdges(graph, null) };
}
