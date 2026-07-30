import { Suspense, useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { CommandPalette } from "./CommandPalette";
import { NavRail } from "./NavRail";
import { RouteError } from "./RouteError";
import { ShortcutsHelp } from "./ShortcutsHelp";
import { TopBar } from "./TopBar";
import { LoadingSpinner } from "../components/LoadingSpinner";
import { Sheet, SheetContent, SheetTitle } from "../components/ui/sheet";
import { useIsMobile } from "../components/ui/use-mobile";

/** True when the keystroke target is a text field, so global hotkeys don't fire mid-typing. */
function isTypingTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || el.isContentEditable;
}

/**
 * The persistent application shell: left NavRail + TopBar + routed content.
 * On desktop the NavRail is persistent; on mobile (<768px) it becomes a slide-over
 * drawer opened from the top bar. Owns the ⌘K palette and `?` help state.
 */
export function AppShell() {
  const { pathname } = useLocation();
  const isMobile = useIsMobile();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // Close the mobile drawer whenever the route changes.
  useEffect(() => setMobileNavOpen(false), [pathname]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      } else if (e.key === "?" && !isTypingTarget(e.target)) {
        e.preventDefault();
        setHelpOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="relative flex h-screen w-screen overflow-hidden bg-background text-foreground">
      {/* atmosphere: a fixed top-center phosphor radial over a faint vertical gradient
          so the app reads as a lit instrument, not a dead-flat void */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 z-0"
        style={{
          background:
            "radial-gradient(110% 55% at 50% -8%, color-mix(in oklab, var(--signal) 5%, transparent), transparent 60%), linear-gradient(to bottom, color-mix(in oklab, var(--signal) 1.5%, var(--background)), var(--background))",
        }}
      />

      {/* Stands in for the hidden macOS title bar: the one region of the window
          you can drag. Its height is `--titlebar-inset`, which is 0px on the web
          and on any platform whose window keeps native chrome, so this is inert
          everywhere else. It deliberately covers only the padding that NavRail
          and TopBar reserve above their content — because nothing interactive
          lives there, no control needs a drag opt-out, and a control added later
          cannot silently become unclickable. Below the skip link's z-50 so that
          still takes clicks ahead of it. */}
      <div
        aria-hidden
        data-testid="titlebar-drag-region"
        className="titlebar-drag fixed inset-x-0 top-0 z-20 h-[var(--titlebar-inset)]"
      />

      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-1.5 focus:text-sm focus:text-primary-foreground"
      >
        Skip to content
      </a>

      {!isMobile && <NavRail />}

      {isMobile && (
        <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
          <SheetContent side="left" className="w-64 border-border bg-sidebar p-0">
            <SheetTitle className="sr-only">Navigation</SheetTitle>
            <NavRail onNavigate={() => setMobileNavOpen(false)} />
          </SheetContent>
        </Sheet>
      )}

      <div className="relative z-10 flex min-w-0 flex-1 flex-col">
        <TopBar
          onOpenPalette={() => setPaletteOpen(true)}
          onOpenHelp={() => setHelpOpen(true)}
          onOpenNav={isMobile ? () => setMobileNavOpen(true) : undefined}
        />
        <main id="main-content" className="min-h-0 flex-1 overflow-hidden">
          <RouteError resetKey={pathname}>
            <Suspense
              fallback={
                <div className="flex h-full items-center justify-center">
                  <LoadingSpinner size="lg" variant="primary" text="Loading…" />
                </div>
              }
            >
              {/* keyed by route → a quick cross-fade on every navigation */}
              <div key={pathname} className="h-full animate-in fade-in duration-200 ease-out">
                <Outlet />
              </div>
            </Suspense>
          </RouteError>
        </main>
      </div>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
      <ShortcutsHelp open={helpOpen} onOpenChange={setHelpOpen} />
    </div>
  );
}
