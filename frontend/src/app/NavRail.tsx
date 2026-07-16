import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";

import { cn } from "../components/ui/utils";
import { Brand } from "./Brand";
import { prefetchRoute } from "./pageLoaders";
import { NAV_ITEMS, SETTINGS_ITEM, type NavItem } from "./routes";

const COLLAPSED_KEY = "dogma:navCollapsed";

function NavRow({
  item,
  collapsed,
  onNavigate,
}: {
  item: NavItem;
  collapsed: boolean;
  onNavigate?: () => void;
}) {
  const { path, label, icon: Icon, end } = item;
  return (
    <NavLink
      to={path}
      end={end}
      onClick={onNavigate}
      onMouseEnter={() => prefetchRoute(path)}
      onFocus={() => prefetchRoute(path)}
      title={collapsed ? label : undefined}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
          collapsed && "justify-center px-0",
          isActive
            ? "trace-band bg-accent text-foreground [&_svg]:text-signal"
            : "text-muted-foreground hover:bg-accent hover:text-foreground",
        )
      }
    >
      <Icon className="h-[18px] w-[18px] shrink-0" />
      {!collapsed && <span className="truncate">{label}</span>}
    </NavLink>
  );
}

/**
 * The persistent left navigation. Source of truth is `routes.NAV_ITEMS`.
 * Collapses to an icon rail (button or ⌘\ / Ctrl+\), persisted to localStorage.
 * `onNavigate` fires when a link is clicked (used to close the mobile drawer).
 */
export function NavRail({ onNavigate }: { onNavigate?: () => void }) {
  const [collapsed, setCollapsed] = useState(
    () => typeof localStorage !== "undefined" && localStorage.getItem(COLLAPSED_KEY) === "true",
  );

  useEffect(() => {
    localStorage.setItem(COLLAPSED_KEY, String(collapsed));
  }, [collapsed]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "\\" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setCollapsed((c) => !c);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <nav
      aria-label="Primary"
      data-collapsed={collapsed}
      className={cn(
        "relative z-10 flex h-full shrink-0 flex-col border-r border-border bg-sidebar transition-[width] duration-200",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <div className={cn("flex h-14 items-center px-3", collapsed && "justify-center px-0")}>
        <NavLink to="/" end aria-label="dogma home">
          <Brand collapsed={collapsed} />
        </NavLink>
      </div>

      <div className="flex-1 space-y-1 overflow-y-auto px-2 py-2">
        {NAV_ITEMS.map((item) => (
          <NavRow key={item.path} item={item} collapsed={collapsed} onNavigate={onNavigate} />
        ))}
      </div>

      <div className="space-y-1 border-t border-border px-2 py-2">
        <NavRow item={SETTINGS_ITEM} collapsed={collapsed} onNavigate={onNavigate} />
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={`${collapsed ? "Expand" : "Collapse"} sidebar (⌘\\)`}
          className={cn(
            "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground active:scale-[0.98]",
            collapsed && "justify-center px-0",
          )}
        >
          {collapsed ? (
            <PanelLeftOpen className="h-[18px] w-[18px] shrink-0" />
          ) : (
            <>
              <PanelLeftClose className="h-[18px] w-[18px] shrink-0" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </nav>
  );
}
