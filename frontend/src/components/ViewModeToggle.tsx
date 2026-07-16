import { MessageSquare, Network } from "lucide-react";

export type AppView = "canvas" | "chat";

interface ViewModeToggleProps {
  active: AppView;
  onSelect: (view: AppView) => void;
}

const TABS: { id: AppView; label: string; Icon: typeof Network }[] = [
  { id: "canvas", label: "Canvas", Icon: Network },
  { id: "chat", label: "Chat", Icon: MessageSquare },
];

/** Segmented control switching the app's primary view. */
export function ViewModeToggle({ active, onSelect }: ViewModeToggleProps) {
  return (
    <div className="inline-flex items-center gap-1 rounded-lg border border-border bg-surface-1 p-1">
      {TABS.map(({ id, label, Icon }) => {
        const isActive = id === active;
        return (
          <button
            key={id}
            type="button"
            aria-pressed={isActive}
            onClick={() => onSelect(id)}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-[transform,box-shadow,border-color,background-color,color] duration-150 ease-out active:scale-[0.98] ${
              isActive
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-foreground/90"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        );
      })}
    </div>
  );
}
