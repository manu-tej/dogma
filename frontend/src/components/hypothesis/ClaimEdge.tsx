import {
  BaseEdge, EdgeLabelRenderer, type EdgeProps, getSmoothStepPath,
} from "@xyflow/react";

import type { ClaimRFEdge } from "../../lib/hypothesis-ui/layout";
import { edgeValidationStyle, resolveEdgeStatus } from "../../lib/hypothesis-ui/styling";

export function ClaimEdge(props: EdgeProps<ClaimRFEdge>) {
  const { data, selected } = props;
  const edge = data!.edge;
  // Drive stroke colour/dash/opacity from the epistemic validation status, not
  // from EdgeState or node grounding — an LLM-proposed edge must read as weak
  // even if its entity nodes are grounded.
  const vstatus = resolveEdgeStatus(edge);
  const vstyle = edgeValidationStyle(vstatus);
  const [path, labelX, labelY] = getSmoothStepPath(props);

  return (
    <>
      <BaseEdge
        path={path}
        style={{
          stroke: selected ? "var(--signal)" : vstyle.color,  // phosphor signal when selected
          strokeWidth: selected ? 4 : 2,
          strokeDasharray: vstyle.dashed ? "6 4" : undefined,
          // selection always wins: full opacity + glow regardless of validation.
          opacity: selected ? 1 : vstyle.weak ? 0.45 : 1,
          filter: selected
            ? "drop-shadow(0 0 5px color-mix(in oklab, var(--signal) 70%, transparent))"
            : undefined,
        }}
      />
      <EdgeLabelRenderer>
        <div
          className="nodrag nopan pointer-events-none absolute rounded-full border bg-surface-2/80 px-2 py-0.5 font-mono text-xs backdrop-blur"
          style={{
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            borderColor: vstyle.color,
            color: vstyle.color,
          }}
        >
          {edge.relation}
          {vstyle.badge && (
            <span className="ml-1 opacity-80">· {vstyle.badge}</span>
          )}
          {edge.suggested_by.length > 0 && (
            <span className="ml-1 text-muted-foreground">· {edge.suggested_by.length}</span>
          )}
        </div>
        {selected && (
          <div
            className="nodrag nopan pointer-events-none absolute whitespace-nowrap rounded-full border border-signal/50 bg-surface-2/90 px-2 py-0.5 text-[10px] font-medium text-signal backdrop-blur"
            style={{ transform: `translate(-50%, 14px) translate(${labelX}px, ${labelY}px)` }}
          >
            ▸ evaluating
          </div>
        )}
      </EdgeLabelRenderer>
    </>
  );
}
