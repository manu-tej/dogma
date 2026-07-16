import { HelpCircle, Menu, Search } from "lucide-react";

import { Breadcrumbs } from "./Breadcrumbs";
import { ThemeToggle } from "./ThemeToggle";
import { Button } from "../components/ui/button";

interface TopBarProps {
  /** Open the ⌘K command palette. */
  onOpenPalette: () => void;
  /** Open the keyboard-shortcuts help. */
  onOpenHelp: () => void;
  /** When provided (mobile), shows a menu button that opens the nav drawer. */
  onOpenNav?: () => void;
}

/** The shell's top bar: breadcrumbs on the left, search + help + theme on the right. */
export function TopBar({ onOpenPalette, onOpenHelp, onOpenNav }: TopBarProps) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card/70 px-4 backdrop-blur-xl">
      {onOpenNav && (
        <Button variant="ghost" size="icon" aria-label="Open navigation" onClick={onOpenNav}>
          <Menu className="h-5 w-5" />
        </Button>
      )}
      <Breadcrumbs />
      <div className="flex-1" />
      <button
        type="button"
        onClick={onOpenPalette}
        aria-label="Open command palette"
        className="elev-sm flex items-center gap-2 rounded-lg border border-border bg-surface-1 px-3 py-1.5 text-sm text-muted-foreground transition-[transform,box-shadow,border-color] duration-150 ease-out hover:border-border-strong hover:text-foreground active:scale-[0.98]"
      >
        <Search className="h-4 w-4" />
        <span className="hidden sm:inline">Search…</span>
        <kbd className="ml-2 hidden rounded border border-border bg-surface-2 px-1.5 font-mono text-[10px] text-muted-foreground sm:inline">
          ⌘K
        </kbd>
      </button>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Keyboard shortcuts"
        title="Keyboard shortcuts (?)"
        onClick={onOpenHelp}
      >
        <HelpCircle className="h-4 w-4" />
      </Button>
      <ThemeToggle />
    </header>
  );
}
