import { createContext, useContext } from "react";

/**
 * Lets an edge's label select its edge.
 *
 * React Flow renders edge labels through `EdgeLabelRenderer`, into a DOM layer
 * outside the flow pane. That layer does not participate in React Flow's event
 * system, so `onEdgeClick` never fires for a label — only for the thin SVG path.
 *
 * Labels therefore carried `pointer-events-none`, which is React Flow's own
 * default advice, and the consequence was worse than "nothing happens": the
 * click fell through to the pane and hit `onPaneClick`, which *deselects*.
 * Clicking the most obvious target for an edge cleared the selection.
 *
 * A context rather than a callback threaded through `data`: `toRFEdges` is a
 * pure function with its own tests, and pushing a handler through it would make
 * layout depend on interaction. `ClaimEdge` is rendered inside the `ReactFlow`
 * subtree, so a provider above it is in scope.
 */
export const EdgeSelectionContext = createContext<((edgeId: string) => void) | null>(
  null,
);

export function useSelectEdge(): (edgeId: string) => void {
  const select = useContext(EdgeSelectionContext);
  // A no-op rather than a throw: an edge rendered outside the provider (a
  // storybook, a future embed) should still draw, just without label clicks.
  return select ?? (() => {});
}
