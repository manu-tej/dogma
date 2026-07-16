import { useEffect, useState } from "react";
import { toast } from "sonner";

import type { HypothesisEvent } from "../../lib/hypothesis-client";
import { hypothesisClient } from "../../services/hypothesisService";

interface ActivityPanelProps {
  graphId: string;
}

const STATUS_PILL: Record<string, string> = {
  ok: "bg-surface-2 text-positive",
  not_found: "bg-surface-2 text-signal-2",
  error: "bg-destructive/15 text-destructive",
};

function statusPill(status: string): string {
  return STATUS_PILL[status] ?? "bg-surface-2 text-muted-foreground";
}

/** Vertical event trail for a single graph, with expandable raw input/output. */
export function ActivityPanel({ graphId }: ActivityPanelProps) {
  const [events, setEvents] = useState<HypothesisEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  useEffect(() => {
    let active = true;
    setLoading(true);
    (async () => {
      try {
        const evs = await hypothesisClient.graphEvents(graphId);
        if (active) setEvents(evs);
      } catch (err) {
        if (active) toast.error(err instanceof Error ? err.message : String(err));
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [graphId]);

  const toggle = (i: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  if (loading) return <p className="p-3 text-sm text-muted-foreground/70">Loading activity…</p>;
  if (events.length === 0)
    return <p className="p-3 text-sm text-muted-foreground/70">No activity recorded for this graph.</p>;

  return (
    <ul className="stagger space-y-2 p-3">
      {events.map((ev, i) => {
        const hasRaw = ev.raw_input != null || ev.raw_output != null || ev.error != null;
        const isOpen = expanded.has(i);
        return (
          <li
            key={i}
            className="elev-sm animate-in fade-in slide-in-from-bottom-2 rounded-lg border border-border bg-card p-2"
            style={{ animationDelay: `${Math.min(i, 4) * 40}ms` }}
          >
            <div className="flex items-center gap-2 text-sm">
              <span className="font-semibold text-foreground">{ev.op}</span>
              <span className={`rounded px-1.5 py-0.5 font-mono text-xs ${statusPill(ev.status)}`}>
                {ev.status}
              </span>
              {ev.latency_ms != null && (
                <span className="font-mono text-xs text-muted-foreground/70">{ev.latency_ms} ms</span>
              )}
              <span className="ml-auto font-mono text-xs text-muted-foreground/70">{ev.ts}</span>
            </div>
            {ev.detail && Object.keys(ev.detail).length > 0 && (
              <pre className="mt-1 max-h-32 overflow-auto rounded bg-background p-1.5 font-mono text-xs text-muted-foreground">
                {JSON.stringify(ev.detail)}
              </pre>
            )}
            {hasRaw && (
              <button
                type="button"
                onClick={() => toggle(i)}
                className="mt-1 text-xs text-muted-foreground/70 hover:text-foreground/90"
              >
                {isOpen ? "▾" : "▸"} raw
              </button>
            )}
            {hasRaw && isOpen && (
              <div className="mt-1 space-y-1">
                {ev.raw_input != null && (
                  <pre className="max-h-64 overflow-auto rounded bg-background p-1.5 font-mono text-xs text-muted-foreground">
                    {ev.raw_input}
                  </pre>
                )}
                {ev.raw_output != null && (
                  <pre className="max-h-64 overflow-auto rounded bg-background p-1.5 font-mono text-xs text-foreground/90">
                    {ev.raw_output}
                  </pre>
                )}
                {ev.error != null && (
                  <pre className="max-h-64 overflow-auto rounded bg-background p-1.5 font-mono text-xs text-destructive">
                    {ev.error}
                  </pre>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
