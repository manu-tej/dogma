import { useEdgeDataSearch } from "../../hooks/useEdgeDataSearch";
import { Button } from "../ui/button";
import type { DatasetCandidate } from "../../lib/hypothesis-client";

interface FindDatasetsProps {
  graphId: string;
  edgeId: string;
  onAttached: () => void;
}

function isSyntheticDemo(candidate: DatasetCandidate): boolean {
  return (
    candidate.accession === "GSE-DEMO" ||
    Boolean(candidate.match_reasons?.some((reason) => reason.includes("synthetic demo")))
  );
}

/** "Find datasets" for an edge: search GEO, attach a pick as its proposed test. */
export function FindDatasets({ graphId, edgeId, onAttached }: FindDatasetsProps) {
  const { candidates, loading, attaching, find, attach } =
    useEdgeDataSearch(graphId, edgeId, onAttached);

  return (
    <div>
      <h4 className="mb-2 text-xs uppercase tracking-wide text-muted-foreground/70">Datasets</h4>
      <Button size="sm" variant="ghost" className={loading ? "signal-sweep text-signal" : "text-signal"} onClick={find} disabled={loading}>
        {loading ? "Searching GEO…" : "Find datasets"}
      </Button>

      {candidates && candidates.length === 0 && (
        <p className="mt-2 text-xs text-muted-foreground/70">No datasets found for this edge.</p>
      )}

      {candidates && candidates.length > 0 && (
        <ul className="stagger mt-2 space-y-2">
          {candidates.map((c, i) => (
            <li
              key={`${c.source}:${c.accession}`}
              className="elev-sm animate-in fade-in slide-in-from-bottom-2 rounded-lg border border-border bg-card p-2"
              style={{ animationDelay: `${Math.min(i, 4) * 40}ms` }}
            >
              <div className="flex items-center gap-2">
                <span className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase text-foreground/90">
                  {isSyntheticDemo(c) ? "synthetic demo" : c.source}
                </span>
                <span className="font-mono text-sm text-foreground">{c.accession}</span>
              </div>
              <p className="mt-1 text-xs text-foreground/90">{c.title}</p>
              {isSyntheticDemo(c) && (
                <p className="mt-1 text-xs font-semibold text-amber-400">
                  Offline placeholder — not a live public-dataset result.
                </p>
              )}
              <p className="mt-1 font-mono text-[11px] text-muted-foreground/70">
                {[c.organism, c.n_samples != null ? `n=${c.n_samples}` : null, c.suggested_pipeline]
                  .filter(Boolean).join(" · ")}
              </p>
              <Button size="sm" className="mt-2" onClick={() => attach(c)} disabled={attaching === c.accession}>
                {attaching === c.accession
                  ? "Attaching…"
                  : isSyntheticDemo(c)
                    ? "Attach synthetic demo"
                    : "Attach as test"}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
