import { useEffect, useState } from "react";
import { PanelLeftClose, Plus, RefreshCw, Trash2 } from "lucide-react";

import type { GraphSummary, HypothesisEvent } from "../../lib/hypothesis-client";
import { useHistory } from "../../hooks/useHistory";
import { formatTimestamp } from "../../lib/format-time";
import { cn } from "../ui/utils";

interface HistorySidebarProps {
  onOpenGraph: (graphId: string) => void;
  /** Collapse the sidebar (wired to the parent's resizable panel). */
  onCollapse: () => void;
  /** Id of the graph currently on the canvas, highlighted in the list. */
  currentGraphId?: string | null;
  /** Reset the canvas back to the empty seeding hero. */
  onNewCanvas?: () => void;
}

type Tab = "all" | "failed";

function statusBadge(status: string): { className: string; label: string } {
  if (status === "error")
    return { className: "bg-destructive/15 text-destructive", label: "failed" };
  return { className: "bg-positive/15 text-positive", label: "active" };
}

function eventStatusBadge(status: string): string {
  if (status === "error") return "bg-destructive/15 text-destructive";
  if (status === "not_found") return "bg-amber-500/15 text-amber-400";
  return "bg-positive/15 text-positive";
}

function GraphRow({
  graph,
  active,
  onOpen,
  onDelete,
}: {
  graph: GraphSummary;
  active: boolean;
  onOpen: () => void;
  onDelete: () => void;
}) {
  const badge = statusBadge(graph.status);
  return (
    <div
      className={cn(
        "elev-sm group flex items-stretch rounded-md border transition-[transform,box-shadow,border-color] duration-150 ease-out",
        active
          ? "trace-band border-border-strong bg-accent pl-1"
          : "border-border bg-card hover:-translate-y-0.5 hover:border-border-strong",
      )}
    >
      <button
        type="button"
        onClick={onOpen}
        aria-current={active || undefined}
        className="min-w-0 flex-1 p-2 text-left"
      >
        <div className="flex items-start gap-2">
          <span className="flex-1 truncate text-sm text-foreground/90">{graph.query}</span>
          <span className={`rounded px-1.5 py-0.5 text-xs ${badge.className}`}>{badge.label}</span>
        </div>
        <div className="mt-1 flex items-center gap-2 font-mono text-xs text-muted-foreground">
          <span title={graph.created_at}>{formatTimestamp(graph.created_at)}</span>
          <span className="text-muted-foreground/70">·</span>
          <span>
            {graph.n_nodes} nodes / {graph.n_edges} edges
          </span>
        </div>
      </button>
      <button
        type="button"
        onClick={onDelete}
        aria-label={`Delete graph: ${graph.query}`}
        title="Delete this graph"
        className="flex items-center px-2 text-muted-foreground/70 opacity-0 transition hover:text-destructive group-hover:opacity-100"
      >
        <Trash2 className="size-4" />
      </button>
    </div>
  );
}

function FailedRow({
  event,
  onOpen,
}: {
  event: HypothesisEvent;
  onOpen: (graphId: string) => void;
}) {
  const clickable = event.graph_id != null;
  const inner = (
    <>
      <div className="flex items-start gap-2">
        <span className="font-mono text-sm font-semibold text-foreground">{event.op}</span>
        <span className={`rounded px-1.5 py-0.5 text-xs ${eventStatusBadge(event.status)}`}>
          {event.status}
        </span>
        <span className="ml-auto font-mono text-xs text-muted-foreground/70" title={event.ts}>{formatTimestamp(event.ts)}</span>
      </div>
      <div className="mt-1 truncate text-xs text-muted-foreground">{event.query ?? "—"}</div>
      {event.error != null && (
        <div className="mt-0.5 truncate text-xs text-destructive">{event.error}</div>
      )}
      {!clickable && <div className="mt-0.5 text-xs text-muted-foreground/70">no graph</div>}
    </>
  );

  if (!clickable) {
    return <div className="elev-sm rounded-md border border-border bg-card p-2">{inner}</div>;
  }
  return (
    <button
      type="button"
      onClick={() => onOpen(event.graph_id!)}
      className="elev-sm block w-full rounded-md border border-border bg-card p-2 text-left transition-[transform,box-shadow,border-color] duration-150 ease-out hover:-translate-y-0.5 hover:border-border-strong"
    >
      {inner}
    </button>
  );
}

/**
 * In-flow History panel: past hypothesis graphs + the recent-failures feed.
 * Designed to live inside a collapsible resizable panel — it fills its host and
 * never positions itself, so the parent owns the (seamless) collapse animation.
 */
export function HistorySidebar({ onOpenGraph, onCollapse, currentGraphId, onNewCanvas }: HistorySidebarProps) {
  const { graphs, failed, loading, refresh, loadFailed, remove, clearAll } = useHistory();
  const [tab, setTab] = useState<Tab>("all");

  // Keep the active feed fresh when the tab changes.
  useEffect(() => {
    if (tab === "all") void refresh();
    else void loadFailed();
  }, [tab, refresh, loadFailed]);

  const reload = () => (tab === "all" ? void refresh() : void loadFailed());

  const handleDelete = (graphId: string) => {
    void remove(graphId);
    if (graphId === currentGraphId) onNewCanvas?.(); // deleting the open graph clears the canvas
  };
  const handleClearAll = () => {
    if (graphs.length === 0) return;
    if (window.confirm(`Delete all ${graphs.length} saved graph(s)? This cannot be undone.`)) {
      void clearAll();
      onNewCanvas?.();
    }
  };

  return (
    <aside className="flex h-full min-w-0 flex-col border-r border-border bg-background">
      <div className="flex items-center justify-between border-b border-border p-3">
        <h3 className="truncate text-sm font-semibold text-foreground">History</h3>
        <div className="flex items-center gap-1">
          {tab === "all" && graphs.length > 0 && (
            <button
              type="button"
              onClick={handleClearAll}
              className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-destructive"
              aria-label="Clear all history"
              title="Clear all saved graphs"
            >
              <Trash2 className="size-4" />
            </button>
          )}
          <button
            type="button"
            onClick={reload}
            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground/90"
            aria-label="Refresh history"
          >
            <RefreshCw className={cn("size-4", loading && "animate-spin")} />
          </button>
          <button
            type="button"
            onClick={onCollapse}
            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground/90"
            aria-label="Collapse history"
            title="Collapse history (⌘B)"
          >
            <PanelLeftClose className="size-4" />
          </button>
        </div>
      </div>

      {onNewCanvas && (
        <div className="border-b border-border p-2">
          <button
            type="button"
            onClick={onNewCanvas}
            className="flex w-full items-center justify-center gap-1.5 rounded-md border border-signal/40 bg-signal/10 px-3 py-1.5 text-xs font-medium text-signal transition-[transform,box-shadow,background-color,border-color] duration-150 ease-out hover:border-signal/60 hover:bg-signal/15 active:scale-[0.98]"
            aria-label="New canvas"
          >
            <Plus className="size-3.5" />
            New canvas
          </button>
        </div>
      )}

      <div className="flex gap-1 border-b border-border p-2">
        <button
          type="button"
          onClick={() => setTab("all")}
          className={`rounded px-2 py-1 text-xs ${
            tab === "all" ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground/90"
          }`}
        >
          All
        </button>
        <button
          type="button"
          onClick={() => setTab("failed")}
          className={`rounded px-2 py-1 text-xs ${
            tab === "failed" ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground/90"
          }`}
        >
          Failed
        </button>
      </div>

      <div className="flex-1 space-y-2 overflow-auto p-2">
        {loading && <p className="p-1 text-sm text-muted-foreground">Loading…</p>}
        {tab === "all" &&
          !loading &&
          (graphs.length === 0 ? (
            <p className="p-1 text-sm text-muted-foreground">No graphs yet.</p>
          ) : (
            graphs.map((g) => (
              <GraphRow
                key={g.id}
                graph={g}
                active={g.id === currentGraphId}
                onOpen={() => onOpenGraph(g.id)}
                onDelete={() => handleDelete(g.id)}
              />
            ))
          ))}
        {tab === "failed" &&
          !loading &&
          (failed.length === 0 ? (
            <p className="p-1 text-sm text-muted-foreground">No failures.</p>
          ) : (
            failed.map((ev, i) => <FailedRow key={i} event={ev} onOpen={onOpenGraph} />)
          ))}
      </div>
    </aside>
  );
}
