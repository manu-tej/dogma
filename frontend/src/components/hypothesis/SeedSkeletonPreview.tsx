import { X } from "lucide-react";

import type { SeedSkeleton } from "../../lib/hypothesis-client";
import { Button } from "../ui/button";

interface SeedSkeletonPreviewProps {
  skeleton: SeedSkeleton;
  building: boolean;
  onBuild: () => void;
  onDropNode: (nodeId: string) => void;
  onSkip: () => void;
}

export function SeedSkeletonPreview({
  skeleton, building, onBuild, onDropNode, onSkip,
}: SeedSkeletonPreviewProps) {
  const labelOf = (id: string) =>
    skeleton.nodes.find((n) => n.id === id)?.label ?? id;

  return (
    <div className="mx-auto w-full max-w-2xl">
      <h3 className="text-xs uppercase tracking-wide text-muted-foreground/70">Proposed skeleton</h3>
      <p className="mb-3 text-sm text-muted-foreground">{skeleton.rationale}</p>

      <div className="mb-3 flex flex-wrap gap-2">
        {skeleton.nodes.map((n) => (
          <span key={n.id}
            className="flex items-center gap-1 rounded-full border border-border bg-surface-2 px-3 py-1 text-sm text-foreground/90">
            {n.label}
            <button type="button" aria-label={`remove ${n.label}`}
              onClick={() => onDropNode(n.id)} className="text-muted-foreground/70 hover:text-destructive">
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
      </div>

      <ul className="mb-4 space-y-1 text-sm text-muted-foreground">
        {skeleton.edges.map((e) => (
          <li key={e.id}>
            {labelOf(e.source_id)} <span className="text-muted-foreground/70">{e.relation}</span> {labelOf(e.target_id)}
          </li>
        ))}
      </ul>

      <div className="flex gap-2">
        <Button onClick={onBuild} disabled={building || skeleton.nodes.length === 0}>
          {building ? "Building…" : "Build the graph"}
        </Button>
        <Button variant="ghost" onClick={onSkip} disabled={building}
          className="text-muted-foreground">
          Skip &amp; build anyway
        </Button>
      </div>
    </div>
  );
}
