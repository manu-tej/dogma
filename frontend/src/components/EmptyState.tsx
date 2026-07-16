import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  /** Optional call-to-action (button/link). */
  action?: ReactNode;
  className?: string;
}

/** A centered placeholder for empty / not-yet-built / no-results states. */
export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={`flex h-full flex-col items-center justify-center gap-3 px-6 py-16 text-center ${className ?? ""}`}
    >
      {Icon && (
        <div className="elev rounded-xl border border-border bg-card p-3 text-muted-foreground">
          <Icon className="h-7 w-7" />
        </div>
      )}
      <h2 className="text-lg font-semibold text-foreground">{title}</h2>
      {description && <p className="max-w-md text-sm text-muted-foreground">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
