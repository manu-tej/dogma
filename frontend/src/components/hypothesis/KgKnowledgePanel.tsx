import type { KGEdgeProvenance } from "../../lib/hypothesis-client";
import { useEdgeKnowledge } from "../../hooks/useEdgeKnowledge";
import { Button } from "../ui/button";

interface KgKnowledgePanelProps {
  graphId: string;
  edgeId: string;
  suggestedBy: KGEdgeProvenance[];
}

/**
 * "What's known": the single panel for an edge's knowledge-graph context —
 * the provenance it was seeded with plus an on-demand lookup (relation + source
 * DBs) against the scientific KG. The lookup result *replaces* the empty state,
 * so a hit (or an explicit "no direct edge") never sits below a stale
 * "No sources" line.
 */
export function KgKnowledgePanel({ graphId, edgeId, suggestedBy }: KgKnowledgePanelProps) {
  const { knowledge, loading, lookup } = useEdgeKnowledge(graphId, edgeId);

  return (
    <div>
      <h4 className="mb-2 text-xs uppercase tracking-wide text-muted-foreground/70">What's known</h4>

      {/* Provenance attached when the edge was seeded, if any. */}
      {suggestedBy.length > 0 && (
        <ul className="mb-2 space-y-1">
          {suggestedBy.map((kg, i) => (
            <li key={`${kg.source}-${kg.reference}-${i}`} className="text-sm text-foreground/90">
              <span className="font-medium text-foreground">{kg.source}</span>{" "}
              <span className="font-mono text-muted-foreground/70">{kg.reference}</span>
              {kg.statement_count != null && (
                <span className="font-mono text-muted-foreground/70"> · {kg.statement_count} stmts</span>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* On-demand lookup result — replaces the empty state once run. */}
      {knowledge ? (
        knowledge.found ? (
          <div className="elev-sm rounded-lg border border-border bg-card p-2 text-xs">
            <p className="text-foreground/90">{knowledge.summary}</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {knowledge.sources.map((s) => (
                <span key={s} className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-foreground/90">{s}</span>
              ))}
            </div>
          </div>
        ) : (
          <p className="rounded-lg border border-border p-2 text-xs text-muted-foreground">{knowledge.summary}</p>
        )
      ) : (
        suggestedBy.length === 0 && (
          <p className="text-sm text-muted-foreground/70">Not looked up yet.</p>
        )
      )}

      <Button size="sm" variant="ghost" className={loading ? "signal-sweep mt-1 text-signal" : "mt-1 text-signal"} onClick={lookup} disabled={loading}>
        {loading
          ? "Checking knowledge graph…"
          : knowledge
            ? "Look up again"
            : "Look up in knowledge graph"}
      </Button>

      <p className="mt-1 text-xs text-muted-foreground/70">Display-only context — never moves the verdict.</p>
    </div>
  );
}
