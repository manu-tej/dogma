import { useEffect, useRef } from "react";

import { QueryBar } from "./QueryBar";
import { ClarifyingQuestionCard } from "./ClarifyingQuestionCard";
import { SeedSkeletonPreview } from "./SeedSkeletonPreview";
import { SeedingProgress } from "./SeedingProgress";
import { useSeeding } from "../../hooks/useSeeding";

interface SeedingFlowProps {
  initialQuery?: string;
  onBuilt: (graphId: string) => void;
}

export function SeedingFlow({ initialQuery, onBuilt }: SeedingFlowProps) {
  const { state, runQuery, answer, dropNode, build, skipAndBuild } = useSeeding(onBuilt);
  const busy = state.status === "seeding" || state.status === "building";

  // A query carried over from the chat auto-starts seeding (once).
  const seeded = useRef(false);
  useEffect(() => {
    if (!seeded.current && initialQuery?.trim()) {
      seeded.current = true;
      runQuery(initialQuery);
    }
  }, [initialQuery, runQuery]);

  const hasSkeleton =
    !!state.skeleton && (state.status === "proposing" || state.status === "building");
  // Hero only before any questions/skeleton exist (idle, or the very first seed call).
  const showHero =
    !hasSkeleton && state.questions.length === 0 &&
    (state.status === "idle" || state.status === "seeding");

  if (showHero) {
    // Actively seeding (no skeleton, no questions yet) — show progress panel.
    if (state.status === "seeding") {
      return (
        <div className="flex h-full flex-col items-center justify-center px-4 pb-[10vh]">
          <div className="w-full max-w-md">
            <SeedingProgress />
          </div>
        </div>
      );
    }

    // Idle — show the normal hero with QueryBar.
    return (
      <div className="flex h-full flex-col items-center justify-center px-4 pb-[10vh]">
        <div className="w-full max-w-2xl text-center">
          <h2 className="mb-2 text-2xl font-semibold text-foreground">What do you want to investigate?</h2>
          <p className="mb-6 text-sm text-muted-foreground">
            Pose a causal question — I'll ask a couple of things, then sketch a graph you can test.
          </p>
          <QueryBar loading={busy} onSubmit={runQuery} initialValue={initialQuery} size="lg" />
          <p className="mt-3 text-xs text-muted-foreground/70">↳ builds an interactive causal canvas</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 overflow-y-auto px-4 py-8">
      {hasSkeleton ? (
        <SeedSkeletonPreview
          skeleton={state.skeleton!}
          building={state.status === "building"}
          onBuild={build}
          onDropNode={dropNode}
          onSkip={skipAndBuild}
        />
      ) : (
        <>
          {busy && <p className="signal-sweep text-sm text-signal">Thinking…</p>}
          {state.questions.map((q) => (
            <div key={q.id} className="w-full max-w-2xl">
              <ClarifyingQuestionCard question={q} onAnswer={answer} />
            </div>
          ))}
        </>
      )}
    </div>
  );
}
