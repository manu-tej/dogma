import { useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { MessageSquare, Network } from "lucide-react";

import { QueryBar } from "../components/hypothesis/QueryBar";
import { Skeleton } from "../components/ui/skeleton";
import { useConversations } from "../hooks/useConversations";
import { useHistory } from "../hooks/useHistory";
import { formatTimestamp } from "../lib/format-time";
import { NAV_ITEMS } from "../app/routes";

/** Destinations to feature as cards (everything except Home itself). */
const FEATURES = NAV_ITEMS.filter((item) => item.path !== "/");

export function HomePage() {
  const navigate = useNavigate();
  const { graphs, refresh, loading } = useHistory();
  const { conversations } = useConversations();

  useEffect(() => {
    refresh();
  }, [refresh]);

  const recentGraphs = [...graphs]
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .slice(0, 5);
  const recentChats = [...conversations]
    .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
    .slice(0, 5);

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-6 py-12">
        {/* Hero */}
        <section className="mb-12 text-center animate-in fade-in slide-in-from-bottom-2">
          <h1 className="mb-2 text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
            What do you want to investigate?
          </h1>
          <p className="mb-6 text-sm text-muted-foreground">
            Pose a causal question and dogma authors a testable mechanism — or jump into any tool below.
          </p>
          <div className="mx-auto max-w-2xl">
            <QueryBar
              loading={false}
              size="lg"
              onSubmit={(q) => navigate(`/canvas?q=${encodeURIComponent(q)}`)}
            />
          </div>
        </section>

        {/* Capability cards */}
        <section className="mb-12">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground/70">Tools</h2>
          <div className="stagger grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map(({ path, label, description, icon: Icon }, i) => (
              <Link
                key={path}
                to={path}
                className="elev group animate-in fade-in slide-in-from-bottom-2 rounded-xl border border-border bg-card p-4 transition-[transform,box-shadow,border-color] duration-150 ease-out hover:-translate-y-0.5 hover:border-border-strong"
                style={{ animationDelay: `${Math.min(i, 4) * 40}ms` }}
              >
                <div className="elev-sm mb-2 inline-flex rounded-lg bg-surface-2 p-2 text-signal">
                  <Icon className="h-5 w-5" />
                </div>
                <h3 className="text-sm font-semibold text-foreground">{label}</h3>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{description}</p>
              </Link>
            ))}
          </div>
        </section>

        {/* Recents */}
        <section className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div>
            <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground/70">
              <Network className="h-3.5 w-3.5" /> Recent canvases
            </h2>
            {loading && recentGraphs.length === 0 ? (
              <div className="space-y-1.5">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="shimmer h-12 w-full rounded-lg" />
                ))}
              </div>
            ) : recentGraphs.length === 0 ? (
              <p className="text-sm text-muted-foreground/70">No saved canvases yet.</p>
            ) : (
              <ul className="stagger space-y-1.5">
                {recentGraphs.map((g, i) => (
                  <li key={g.id}>
                    <Link
                      to={`/canvas/${g.id}`}
                      className="elev block animate-in fade-in slide-in-from-bottom-2 rounded-lg border border-border bg-card px-3 py-2 transition-[transform,box-shadow,border-color] duration-150 ease-out hover:-translate-y-0.5 hover:border-border-strong"
                      style={{ animationDelay: `${Math.min(i, 4) * 40}ms` }}
                    >
                      <div className="truncate text-sm text-foreground/90">{g.query || "Untitled canvas"}</div>
                      <div className="mt-0.5 font-mono text-xs text-muted-foreground/70">
                        {g.n_nodes} nodes · {g.n_edges} edges · {formatTimestamp(g.updated_at)}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h2 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground/70">
              <MessageSquare className="h-3.5 w-3.5" /> Recent chats
            </h2>
            {recentChats.length === 0 ? (
              <p className="text-sm text-muted-foreground/70">No conversations yet.</p>
            ) : (
              <ul className="stagger space-y-1.5">
                {recentChats.map((c, i) => (
                  <li key={c.id}>
                    <Link
                      to={`/chat/${c.id}`}
                      className="elev block animate-in fade-in slide-in-from-bottom-2 rounded-lg border border-border bg-card px-3 py-2 transition-[transform,box-shadow,border-color] duration-150 ease-out hover:-translate-y-0.5 hover:border-border-strong"
                      style={{ animationDelay: `${Math.min(i, 4) * 40}ms` }}
                    >
                      <div className="truncate text-sm text-foreground/90">{c.title}</div>
                      <div className="mt-0.5 font-mono text-xs text-muted-foreground/70">
                        {formatTimestamp(c.timestamp.toISOString())}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
