import { useParams, useSearchParams } from "react-router-dom";

import { HypothesisView } from "../components/hypothesis/HypothesisView";

/**
 * The causal-hypothesis canvas. `?q=` seeds a new investigation; `/canvas/:graphId`
 * deep-links a saved graph. Keyed by both so navigating between them remounts the
 * underlying hypothesis state cleanly.
 */
export function CanvasPage() {
  const { graphId } = useParams();
  const [params] = useSearchParams();
  const seed = params.get("q") ?? undefined;

  return (
    <div className="h-full bg-background">
      <HypothesisView key={graphId ?? seed ?? "new"} initialQuery={seed} initialGraphId={graphId} />
    </div>
  );
}
