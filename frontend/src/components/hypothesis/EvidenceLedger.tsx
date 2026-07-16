import type { EvidenceEntry } from "../../lib/hypothesis-client";

interface EvidenceLedgerProps {
  entries: EvidenceEntry[];
}

// Each record states a factual observation relative to the claim — not a verdict.
const DIRECTION_LABEL: Record<EvidenceEntry["direction"], string> = {
  supports: "consistent with claim",
  refutes: "inconsistent with claim",
  inconclusive: "inconclusive",
};
const DIRECTION_COLOR: Record<EvidenceEntry["direction"], string> = {
  supports: "text-foreground/90",
  refutes: "text-amber-400", // an inconsistency is a fact worth surfacing, not a red "refuted"
  inconclusive: "text-muted-foreground",
};

export function EvidenceLedger({ entries }: EvidenceLedgerProps) {
  return (
    <div>
      <h4 className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">
        Evidence ledger (your pipeline runs)
      </h4>
      {entries.length === 0 ? (
        <p className="text-sm text-muted-foreground">No runs yet for this edge.</p>
      ) : (
        <ul className="space-y-2">
          {entries.map((e) => (
            <li key={e.provenance.run_id} className="elev-sm rounded-md border border-border bg-surface-1 p-2 text-sm">
              <div className="flex items-center justify-between">
                <span className={`font-medium ${DIRECTION_COLOR[e.direction]}`}>{DIRECTION_LABEL[e.direction]}</span>
                {e.magnitude && <span className="font-mono text-muted-foreground">{e.magnitude}</span>}
              </div>
              {e.rationale && <p className="text-muted-foreground">{e.rationale}</p>}
              <p className="mt-1 font-mono text-xs text-muted-foreground/70">
                run {e.provenance.run_id} · {e.provenance.data_accession}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
