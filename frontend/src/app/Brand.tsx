import { Dna } from "lucide-react";
import { cn } from "../components/ui/utils";

interface BrandProps {
  /** Hide the wordmark, showing only the mark (used in the collapsed rail). */
  collapsed?: boolean;
  className?: string;
}

/**
 * The dogma wordmark + DNA mark. One brand, shared with the VSCode extension
 * surface — keep the name "dogma" consistent across both.
 */
export function Brand({ collapsed = false, className }: BrandProps) {
  return (
    <div className={cn("flex items-center gap-2.5", className)} aria-label="dogma">
      <div className="glow-signal grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-surface-2 text-signal">
        <Dna className="h-5 w-5" />
      </div>
      {!collapsed && (
        <span className="text-base font-semibold tracking-tight text-foreground">
          <span className="text-signal">d</span>ogma
        </span>
      )}
    </div>
  );
}
