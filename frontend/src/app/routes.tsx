import {
  Home,
  Network,
  MessageSquare,
  Database,
  FlaskConical,
  Workflow,
  Microscope,
  Settings,
  type LucideIcon,
} from "lucide-react";

/**
 * A navigable destination in the app shell. This is the single source of truth
 * consumed by the NavRail, the command palette, and the breadcrumb trail — add a
 * destination here and it shows up everywhere.
 */
export interface NavItem {
  path: string;
  label: string;
  /** One-line description for the command palette + page headers. */
  description: string;
  icon: LucideIcon;
  /** Match the route exactly (used for the index route). */
  end?: boolean;
}

/** Primary destinations shown in the left nav rail. */
export const NAV_ITEMS: NavItem[] = [
  { path: "/", label: "Home", description: "Dashboard, recent work, and a place to start a new investigation.", icon: Home, end: true },
  { path: "/canvas", label: "Canvas", description: "Author and test a causal hypothesis on an interactive graph.", icon: Network },
  { path: "/chat", label: "Chat", description: "Conversational dataset discovery across public repositories.", icon: MessageSquare },
  { path: "/datasets", label: "Datasets", description: "Search GEO, single-cell, and proteomics (PRIDE) repositories.", icon: Database },
  { path: "/methods", label: "Methods", description: "Browse the analysis-method registry and recommendations.", icon: FlaskConical },
  { path: "/pipelines", label: "Pipelines", description: "Browse, launch, and monitor Nextflow pipeline runs.", icon: Workflow },
  { path: "/interpretation", label: "Interpretation", description: "Interpret differential-expression and analysis results.", icon: Microscope },
];

/** Settings lives apart from the primary destinations (rail footer + top bar). */
export const SETTINGS_ITEM: NavItem = {
  path: "/settings",
  label: "Settings",
  description: "Appearance, search preferences, and provider status.",
  icon: Settings,
};

/** Every reachable destination, for the command palette. */
export const ALL_DESTINATIONS: NavItem[] = [...NAV_ITEMS, SETTINGS_ITEM];

/**
 * Resolve the nav item that owns a pathname. Prefers the longest matching path
 * so `/canvas/:graphId` resolves to the Canvas destination.
 */
export function findNavItem(pathname: string): NavItem | undefined {
  return ALL_DESTINATIONS.filter((item) =>
    item.end ? pathname === item.path : pathname === item.path || pathname.startsWith(`${item.path}/`),
  ).sort((a, b) => b.path.length - a.path.length)[0];
}
