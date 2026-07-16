export interface MethodGroundingPanelProps {
  verdict: "GROUNDED" | "PARTIALLY_GROUNDED" | "COVERAGE_GAP" | "NOT_EVALUABLE";
  summary: string;
}

const LABEL: Record<MethodGroundingPanelProps["verdict"], string> = {
  GROUNDED: "Methodological grounding",
  PARTIALLY_GROUNDED: "Partial methodological grounding",
  COVERAGE_GAP: "Coverage gap",
  NOT_EVALUABLE: "Not evaluable",
};

const VALID = new Set<MethodGroundingPanelProps["verdict"]>([
  "GROUNDED",
  "PARTIALLY_GROUNDED",
  "COVERAGE_GAP",
  "NOT_EVALUABLE",
]);

/** Methods-graph evaluation = whether a grounded method could measure this edge +
 *  what assumptions must hold. NOT biological confirmation — styled distinctly. */
export function MethodGroundingPanel({ verdict, summary }: MethodGroundingPanelProps) {
  const v = VALID.has(verdict) ? verdict : "NOT_EVALUABLE";
  return (
    <div className="elev rounded-lg border border-border bg-card p-3">
      <h4 className="mb-1 text-xs uppercase tracking-wide text-signal-2">{LABEL[v]}</h4>
      <p className="text-sm text-foreground/90">{summary}</p>
      <p className="mt-1 text-[11px] text-muted-foreground/70">
        Methods-graph grounding — does not confirm or refute the biology.
      </p>
    </div>
  );
}
