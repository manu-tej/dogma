import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";

interface ShortcutsHelpProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const SHORTCUTS: { keys: string[]; label: string }[] = [
  { keys: ["⌘", "K"], label: "Open command palette / search" },
  { keys: ["⌘", "\\"], label: "Collapse or expand the sidebar" },
  { keys: ["⌘", "B"], label: "Toggle the canvas history rail" },
  { keys: ["?"], label: "Show this shortcuts help" },
  { keys: ["Esc"], label: "Close dialogs and panels" },
];

function Keys({ keys }: { keys: string[] }) {
  return (
    <span className="flex items-center gap-1">
      {keys.map((k) => (
        <kbd
          key={k}
          className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-foreground/90"
        >
          {k}
        </kbd>
      ))}
    </span>
  );
}

/** A small reference of the app's keyboard shortcuts. Opened with `?`. */
export function ShortcutsHelp({ open, onOpenChange }: ShortcutsHelpProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Keyboard shortcuts</DialogTitle>
          <DialogDescription>Move around dogma without leaving the keyboard.</DialogDescription>
        </DialogHeader>
        <ul className="mt-2 divide-y divide-border">
          {SHORTCUTS.map((s) => (
            <li key={s.label} className="flex items-center justify-between py-2.5">
              <span className="text-sm text-foreground/90">{s.label}</span>
              <Keys keys={s.keys} />
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
