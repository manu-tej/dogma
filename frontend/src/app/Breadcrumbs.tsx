import { Link, useLocation } from "react-router-dom";
import { ChevronRight } from "lucide-react";

import { findNavItem } from "./routes";

/**
 * A route-derived breadcrumb trail. Resolves the owning destination from
 * `routes`, then appends any trailing path segment (e.g. a graph id) as a leaf.
 */
export function Breadcrumbs() {
  const { pathname } = useLocation();
  const item = findNavItem(pathname);

  if (!item) {
    return <span className="text-sm font-medium text-foreground/90">dogma</span>;
  }

  // A trailing segment beyond the destination root (e.g. /canvas/<graphId>).
  const rest = pathname.slice(item.path.length).replace(/^\/+/, "");
  const leaf = rest.split("/").filter(Boolean)[0];

  return (
    <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-sm">
      <Link to={item.path} className="font-medium text-foreground/90 transition-colors hover:text-foreground">
        {item.label}
      </Link>
      {leaf && (
        <>
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground/70" />
          <span className="truncate font-mono text-xs text-muted-foreground" title={leaf}>
            {leaf}
          </span>
        </>
      )}
    </nav>
  );
}
