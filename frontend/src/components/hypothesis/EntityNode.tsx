import { Handle, type NodeProps, Position } from "@xyflow/react";
import * as Icons from "lucide-react";

import type { EntityRFNode } from "../../lib/hypothesis-ui/layout";
import { nodeTypeStyle } from "../../lib/hypothesis-ui/styling";

export function EntityNode({ data, selected: rfSelected }: NodeProps<EntityRFNode>) {
  const { node } = data;
  // Prefer the data-driven flag (passed through verbatim by React Flow); fall back
  // to RF's own selected prop. Inline box-shadow can't be overridden/clipped.
  const selected = data.selected ?? rfSelected;
  const style = nodeTypeStyle(node.type);
  const Icon = (Icons[style.icon as keyof typeof Icons] ?? Icons.Circle) as Icons.LucideIcon;

  return (
    <div
      className="elev-sm relative flex w-[190px] items-center gap-2.5 rounded-lg border border-border bg-surface-1 py-2 pl-4 pr-3 transition-shadow"
      style={{
        borderColor: selected ? "var(--signal)" : undefined,
        boxShadow: selected
          ? "0 0 0 1.5px var(--signal), 0 0 18px color-mix(in oklab, var(--signal) 55%, transparent)"
          : undefined,
      }}
    >
      {/* node-type accent rail */}
      <span
        aria-hidden
        className="absolute inset-y-0 left-0 w-1 rounded-l-lg"
        style={{ backgroundColor: style.color }}
      />
      <Handle type="target" position={Position.Top} className="!bg-muted-foreground" />
      <Icon className="h-5 w-5 shrink-0" style={{ color: style.color }} />
      <div className="min-w-0">
        <div className="truncate text-sm font-medium text-foreground">{node.label}</div>
        <div className="font-mono text-[11px] uppercase tracking-wide text-muted-foreground">{node.type}</div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-muted-foreground" />
    </div>
  );
}
