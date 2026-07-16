import { useEffect, useState } from "react";

const STAGES = [
  "Parsing your question",
  "Proposing entities & edges",
  "Grounding to ontologies",
];

/** Seconds elapsed before advancing to the next stage hint. */
const STAGE_INTERVAL_SECONDS = 10;

interface SeedingProgressProps {
  /**
   * Epoch ms when seeding started. Defaults to `Date.now()` captured at mount.
   * Inject a fixed value in tests to keep elapsed calculations deterministic.
   */
  startedAt?: number;
}

export function SeedingProgress({ startedAt }: SeedingProgressProps) {
  // Capture mount time once — never read Date.now() at module top-level.
  const [mountedAt] = useState<number>(() => startedAt ?? Date.now());
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    // Recompute elapsed whenever startedAt changes (e.g. fresh mount).
    const origin = startedAt ?? mountedAt;

    const id = setInterval(() => {
      setElapsed(Math.round((Date.now() - origin) / 1000));
    }, 1000);

    return () => clearInterval(id);
  }, [startedAt, mountedAt]);

  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const timerLabel = `${minutes}:${String(seconds).padStart(2, "0")}`;

  const stageIndex = Math.min(
    Math.floor(elapsed / STAGE_INTERVAL_SECONDS),
    STAGES.length - 1,
  );
  const currentStage = STAGES[stageIndex];

  return (
    <div className="flex flex-col items-center gap-5 text-center">
      {/* Spinning indicator */}
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-surface-2">
        <svg
          className="h-6 w-6 animate-spin text-signal"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      </div>

      {/* Heading */}
      <h3 className="text-lg font-semibold text-foreground">
        Sketching a causal graph&hellip;
      </h3>

      {/* Elapsed timer */}
      <p className="font-mono text-3xl font-bold tabular-nums text-signal">
        {timerLabel}
      </p>

      {/* Staged checklist */}
      <ol className="flex flex-col gap-1.5 text-sm">
        {STAGES.map((stage, i) => {
          const done = i < stageIndex;
          const active = i === stageIndex;
          return (
            <li
              key={stage}
              className={[
                "flex items-center gap-2 transition-colors",
                done ? "text-muted-foreground/70 line-through" : "",
                active ? "font-medium text-signal" : "",
                !done && !active ? "text-muted-foreground/70" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              {done ? (
                <span className="text-positive" aria-hidden="true">
                  ✓
                </span>
              ) : active ? (
                <span className="text-signal" aria-hidden="true">
                  →
                </span>
              ) : (
                <span className="text-muted-foreground/70" aria-hidden="true">
                  ·
                </span>
              )}
              {stage}
            </li>
          );
        })}
      </ol>

      {/* Disclaimer */}
      <p className="text-xs text-muted-foreground/70">Large models take ~30s.</p>
    </div>
  );
}
