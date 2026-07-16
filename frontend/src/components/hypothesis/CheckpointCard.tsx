import { Loader2 } from "lucide-react";
import { useState } from "react";

import type { ProposedTest } from "../../lib/hypothesis-client";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";

interface CheckpointCardProps {
  proposal: ProposedTest;
  running: boolean;
  onApprove: (proposed: ProposedTest) => void;
  onSkip: () => void;
}

export function CheckpointCard({ proposal, running, onApprove, onSkip }: CheckpointCardProps) {
  const [editing, setEditing] = useState(false);
  const [pipeline, setPipeline] = useState(proposal.pipeline);
  const [dataAccession, setDataAccession] = useState(proposal.data_accession);

  const handleApprove = () =>
    onApprove({ ...proposal, pipeline, data_accession: dataAccession });

  return (
    <div className="trace-band elev rounded-lg border border-border bg-card p-3">
      <h4 className="mb-1 text-xs uppercase tracking-wide text-signal">Next checkpoint</h4>
      <p className="mb-2 text-sm text-foreground/90">{proposal.gap}</p>

      {proposal.method && (
        <p className="mb-2">
          <span
            title={proposal.method.rationale}
            className="inline-block rounded-full border border-signal/40 bg-surface-2 px-2 py-0.5 text-xs text-signal"
          >
            recommended: {proposal.method.name} · <span className="font-mono">{proposal.method.score.toFixed(2)}</span>
          </span>
        </p>
      )}

      {proposal.method?.grounding && (
        <details className="mb-2">
          <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground/90">
            Method grounding · methods-graph
          </summary>
          <p className="mt-1 text-[11px] leading-tight text-muted-foreground/70">
            Knowledge-graph context for {proposal.method.name} — describes the method,
            not specific to this edge.
          </p>
          <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap rounded bg-surface-2 p-2 font-mono text-xs text-foreground/90">
            {proposal.method.grounding}
          </pre>
        </details>
      )}

      {editing ? (
        <div className="mb-3 space-y-2">
          <div className="space-y-1">
            <Label htmlFor="cp-pipeline">Pipeline</Label>
            <Input id="cp-pipeline" value={pipeline}
              onChange={(e) => setPipeline(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="cp-data">Data</Label>
            <Input id="cp-data" value={dataAccession}
              onChange={(e) => setDataAccession(e.target.value)} />
          </div>
        </div>
      ) : (
        <dl className="mb-3 space-y-1 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted-foreground/70">Pipeline</dt>
            <dd className="font-mono text-foreground/90">{pipeline}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground/70">Data</dt>
            <dd className="font-mono text-foreground/90">{dataAccession}</dd>
          </div>
          {proposal.est_time && (
            <div className="flex justify-between">
              <dt className="text-muted-foreground/70">Est. time</dt>
              <dd className="font-mono text-foreground/90">{proposal.est_time}</dd>
            </div>
          )}
        </dl>
      )}

      <div className="flex gap-2">
        <Button size="sm" onClick={handleApprove} disabled={running}>
          {running ? (
            <><Loader2 className="mr-1 h-4 w-4 animate-spin" />Executing…</>
          ) : (
            "Approve"
          )}
        </Button>
        <Button size="sm" variant="outline" disabled={running}
          onClick={() => setEditing((v) => !v)}>
          {editing ? "Done" : "Adjust"}
        </Button>
        <Button size="sm" variant="ghost" disabled={running} onClick={onSkip}>
          Skip
        </Button>
      </div>
    </div>
  );
}
