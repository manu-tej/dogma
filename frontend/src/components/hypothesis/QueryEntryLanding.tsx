import { Card } from "../ui/card";
import { QueryBar } from "./QueryBar";

const EXAMPLES = [
  "How does AXL inhibition affect pAKT signalling in paclitaxel-resistant cancers?",
  "Does KRAS G12C inhibition reactivate MAPK via RTK feedback?",
  "How does TGF-β signalling promote EMT in pancreatic cancer?",
];

export function QueryEntryLanding({ onStart }: { onStart: (query: string) => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center bg-background px-4">
      <div className="w-full max-w-2xl space-y-7 text-center">
        <div className="text-xs uppercase tracking-wide text-signal">
          Agentic interface for computational biology
        </div>
        <h1 className="text-3xl font-semibold text-foreground">
          Ask a causal question.
          <br />
          Build the hypothesis, evaluate every edge.
        </h1>
        <p className="text-sm text-muted-foreground">
          The agent authors a causal graph from your question. Each edge is a claim you can
          evaluate — and each evaluation can become a full analysis workflow.
        </p>
        <div className="mx-auto w-full">
          <QueryBar loading={false} onSubmit={onStart} size="lg" />
        </div>
        <div>
          <p className="mb-2 text-[11px] uppercase tracking-wide text-muted-foreground/70">Example questions</p>
          <div className="stagger space-y-2">
            {EXAMPLES.map((q, i) => (
              <Card
                key={q}
                data-testid="example-query"
                className="elev animate-in fade-in slide-in-from-bottom-2 cursor-pointer border-border bg-card p-3 text-left text-sm text-foreground/90 transition-[transform,box-shadow,border-color] duration-150 ease-out hover:-translate-y-0.5 hover:border-border-strong"
                style={{ animationDelay: `${Math.min(i, 4) * 40}ms` }}
                onClick={() => onStart(q)}
              >
                {q}
              </Card>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
