import type { CSSProperties, ReactNode } from "react";

/**
 * The clickable chip that sits on an edge.
 *
 * Split out from `ClaimEdge` because `EdgeLabelRenderer` portals into a DOM node
 * that only a mounted `<ReactFlow>` creates, and React Flow does not render
 * edges at all in jsdom without measured node dimensions. Testing the label
 * through the canvas therefore asserts nothing; testing it here asserts the part
 * that actually broke.
 *
 * A `<button>`, not a styled `<div>`: this is a control, and it needs to be
 * reachable by keyboard and announce itself. The label was previously inert
 * decoration with `pointer-events-none`.
 */
export function ClaimEdgeLabel({
  relation,
  selected,
  onSelect,
  style,
  borderColor,
  color,
  children,
}: {
  relation: string;
  selected: boolean;
  onSelect: () => void;
  style?: CSSProperties;
  borderColor: string;
  color: string;
  children?: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={`Select claim: ${relation}`}
      aria-pressed={selected}
      onClick={(event) => {
        // Without this the click continues to the flow pane, whose handler
        // clears the selection — so the edge would flicker selected and then
        // deselect, which looks exactly like a label that does nothing.
        event.stopPropagation();
        onSelect();
      }}
      className="nodrag nopan pointer-events-auto absolute cursor-pointer rounded-full border bg-surface-2/80 px-2 py-0.5 font-mono text-xs backdrop-blur transition-shadow hover:shadow-[0_0_6px_color-mix(in_oklab,var(--signal)_60%,transparent)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-signal"
      style={{ ...style, borderColor, color }}
    >
      {relation}
      {children}
    </button>
  );
}
