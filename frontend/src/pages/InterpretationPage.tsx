import { useMemo, useState } from "react";
import { Microscope, Loader2, Sparkles } from "lucide-react";

import { PageHeader } from "../components/PageHeader";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import {
  interpretDEG,
  parseGeneTable,
  splitByDirection,
  type DEGInterpretation,
} from "../services/interpretationService";

const EXAMPLE = `# gene\tlog2FC\tpValue
ESR1\t2.4\t0.0001
GREB1\t1.9\t0.0008
MKI67\t-1.7\t0.002
CCNB1\t-2.1\t0.0005
EGFR\t1.2\t0.01`;

const CONFIDENCE_COLOR: Record<string, string> = {
  high: "bg-surface-2 text-positive border-border-strong",
  medium: "bg-surface-2 text-foreground/90 border-border-strong",
  low: "bg-surface-2 text-muted-foreground border-border",
};

export function InterpretationPage() {
  const [conditionA, setConditionA] = useState("treated");
  const [conditionB, setConditionB] = useState("control");
  const [organism, setOrganism] = useState("human");
  const [geneText, setGeneText] = useState("");
  const [context, setContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<DEGInterpretation | null>(null);

  const { up, down } = useMemo(() => splitByDirection(parseGeneTable(geneText)), [geneText]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (up.length === 0) {
      setError("Add at least one upregulated gene (positive log2 fold change).");
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const r = await interpretDEG({
        upregulatedGenes: up,
        downregulatedGenes: down,
        conditionA,
        conditionB,
        organism,
        additionalContext: context || undefined,
      });
      setResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Interpretation"
        description="Turn differential-expression results into grounded, cited biological claims."
      />
      <div className="min-h-0 flex-1 overflow-y-auto p-6">
        <div className="mx-auto grid max-w-5xl gap-6 lg:grid-cols-2">
          {/* Input */}
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm">
                <span className="mb-1 block text-muted-foreground">Condition A</span>
                <Input value={conditionA} onChange={(e) => setConditionA(e.target.value)} />
              </label>
              <label className="text-sm">
                <span className="mb-1 block text-muted-foreground">Condition B</span>
                <Input value={conditionB} onChange={(e) => setConditionB(e.target.value)} />
              </label>
            </div>
            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">Organism</span>
              <Input value={organism} onChange={(e) => setOrganism(e.target.value)} />
            </label>
            <label className="block text-sm">
              <div className="mb-1 flex items-center justify-between">
                <span className="text-muted-foreground">
                  Genes <span className="text-muted-foreground/70">(SYMBOL · log2FC · pValue per line)</span>
                </span>
                <button
                  type="button"
                  className="text-xs text-signal transition-colors hover:text-signal/80 active:scale-[0.98]"
                  onClick={() => setGeneText(EXAMPLE)}
                >
                  Load example
                </button>
              </div>
              <Textarea
                value={geneText}
                onChange={(e) => setGeneText(e.target.value)}
                rows={8}
                placeholder={"ESR1\t2.4\t0.0001\nMKI67\t-1.7\t0.002"}
                className="font-mono text-xs"
              />
            </label>
            <p className="text-xs text-muted-foreground/70">
              Parsed: <span className="font-mono text-positive">{up.length} up</span> ·{" "}
              <span className="font-mono text-destructive">{down.length} down</span>
            </p>
            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">Additional context (optional)</span>
              <Textarea value={context} onChange={(e) => setContext(e.target.value)} rows={2} />
            </label>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" disabled={loading} className="glow-signal w-full">
              {loading ? (
                <>
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> Interpreting…
                </>
              ) : (
                <>
                  <Sparkles className="mr-1.5 h-4 w-4" /> Interpret results
                </>
              )}
            </Button>
          </form>

          {/* Output */}
          <div className="min-w-0">
            {!result && !loading && (
              <div className="elev flex h-full flex-col rounded-xl border border-border bg-card p-6">
                <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
                  <div className="grid place-items-center rounded-xl bg-surface-2 p-3 text-signal/80">
                    <Microscope className="h-7 w-7" />
                  </div>
                  <h3 className="text-sm font-semibold text-foreground">Grounded claims appear here</h3>
                  <p className="max-w-xs text-xs leading-relaxed text-muted-foreground">
                    Paste a DEG gene table and Interpret — dogma returns claims, open questions, and
                    limitations, each grounded in tool lookups (NCBI Gene, Reactome, PubMed, STRING).
                  </p>
                </div>
                {/* faint preview of where claim rows will render */}
                <div className="mt-4 space-y-2 opacity-40" aria-hidden>
                  {[0, 1, 2].map((i) => (
                    <div key={i} className="h-10 rounded-lg border border-border bg-surface-1" />
                  ))}
                </div>
              </div>
            )}
            {loading && (
              <div className="space-y-2">
                {[0, 1, 2, 3].map((i) => (
                  <div key={i} className="signal-sweep h-16 w-full rounded-lg border border-border bg-card" />
                ))}
              </div>
            )}
            {result && <InterpretationResult result={result} />}
          </div>
        </div>
      </div>
    </div>
  );
}

function InterpretationResult({ result }: { result: DEGInterpretation }) {
  return (
    <div className="stagger space-y-4">
      <section className="elev animate-in fade-in slide-in-from-bottom-2 rounded-xl border border-border bg-card p-4">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground">Summary</h2>
          <Badge variant="outline" className="font-mono">confidence {(result.confidenceScore * 100).toFixed(0)}%</Badge>
        </div>
        <p className="text-sm leading-relaxed text-foreground/90">{result.summary}</p>
      </section>

      {result.claims.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold text-foreground">Claims</h2>
          <ul className="stagger space-y-2">
            {result.claims.map((c, i) => (
              <li
                key={i}
                className="elev animate-in fade-in slide-in-from-bottom-2 rounded-lg border border-border bg-card p-3 transition-[transform,box-shadow,border-color] duration-150 ease-out hover:-translate-y-0.5 hover:border-border-strong"
                style={{ animationDelay: `${Math.min(i, 4) * 40}ms` }}
              >
                <div className="mb-1 flex items-center gap-2">
                  <span
                    className={`rounded-full border px-2 py-0.5 text-[11px] capitalize ${
                      CONFIDENCE_COLOR[c.confidence] ?? CONFIDENCE_COLOR.low
                    }`}
                  >
                    {c.confidence}
                  </span>
                  <span className="text-xs text-muted-foreground/70">{c.claimType}</span>
                  {c.evidenceCount > 0 && (
                    <span className="ml-auto font-mono text-xs text-muted-foreground/70">{c.evidenceCount} sources</span>
                  )}
                </div>
                <p className="text-sm text-foreground/90">{c.statement}</p>
                {(c.genesMentioned.length > 0 || c.pathwaysMentioned.length > 0) && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {c.genesMentioned.map((g) => (
                      <Badge key={g} variant="secondary" className="text-[10px]">{g}</Badge>
                    ))}
                    {c.pathwaysMentioned.map((p) => (
                      <Badge key={p} variant="outline" className="text-[10px]">{p}</Badge>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {result.openQuestions.length > 0 && (
        <ListSection title="Open questions" items={result.openQuestions} />
      )}
      {result.limitations.length > 0 && (
        <ListSection title="Limitations" items={result.limitations} />
      )}
      {result.recommendations.length > 0 && (
        <ListSection title="Recommendations" items={result.recommendations} />
      )}

      <p className="font-mono text-xs text-muted-foreground/70">
        {result.modelUsed} · {result.tokenUsage.totalTokens.toLocaleString()} tokens · $
        {result.costUsd.toFixed(4)} · {(result.processingTimeMs / 1000).toFixed(1)}s ·{" "}
        {result.toolCalls.length} tool calls
      </p>
    </div>
  );
}

function ListSection({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="elev animate-in fade-in slide-in-from-bottom-2 rounded-xl border border-border bg-card p-4">
      <h2 className="mb-2 text-sm font-semibold text-foreground">{title}</h2>
      <ul className="list-disc space-y-1 pl-4 text-sm text-foreground/90">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </section>
  );
}
