import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  description?: string;
  /** Right-aligned actions (buttons, toggles). */
  actions?: ReactNode;
}

/** Consistent page header for the shell's content pages. */
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <div className="flex shrink-0 items-start justify-between gap-4 border-b border-border px-6 py-4">
      <div className="min-w-0">
        <h1 className="text-lg font-semibold text-foreground">{title}</h1>
        {description && <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="shrink-0">{actions}</div>}
    </div>
  );
}
