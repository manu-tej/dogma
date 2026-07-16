import { Check, ChevronRight, Loader2 } from "lucide-react";
import type { GraphEdge } from "../../lib/hypothesis-client";
import type { EvaluationPlan } from "../../lib/hypothesis-client/types";
import type { StepStatus, WorkflowStep, WorkflowSubStep } from "../../lib/hypothesis-ui/workflow";
import { useEvaluationWorkflow } from "../../hooks/useEvaluationWorkflow";
import { cn } from "../ui/utils";

interface Props {
  edge: GraphEdge | null;
  targetLabel: string;
  sourceLabel?: string;
  getPlan: (edgeId: string) => Promise<EvaluationPlan>;
  onResolve: (edgeId: string) => Promise<EvaluationPlan>;
}

// Circled glyphs for the step index (matches the ①②③ spine in the mockup).
const GLYPHS = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨"];

const STATE_DOT: Record<StepStatus, string> = {
  done: "border-emerald-800 bg-emerald-950",
  running: "border-signal/60 bg-surface-2 shadow-[0_0_0_4px_color-mix(in_oklab,var(--signal)_20%,transparent)]",
  needs_you: "border-amber-800 bg-amber-950",
  queued: "border-border-strong bg-surface-1",
  failed: "border-red-800 bg-red-950",
};

const STATE_LABEL: Record<StepStatus, string> = {
  done: "done ✓",
  running: "running ⟳",
  needs_you: "needs you",
  queued: "queued",
  failed: "failed",
};

// Status pill — bordered, tinted (matches .st.done/.run/.you/.wait in the mockup).
const STATE_PILL: Record<StepStatus, string> = {
  done: "border-emerald-800 bg-emerald-950 text-emerald-300",
  running: "border-signal/40 bg-surface-2 text-signal",
  needs_you: "border-amber-800 bg-amber-950 text-amber-300",
  queued: "border-border-strong bg-surface-1 text-muted-foreground",
  failed: "border-red-800 bg-red-950 text-red-300",
};

function StepDot({ status }: { status: StepStatus }) {
  return (
    <span className={cn("flex h-[15px] w-[15px] items-center justify-center rounded-full border-2", STATE_DOT[status])}>
      {status === "done" && <Check className="h-2 w-2 text-emerald-300" />}
      {status === "running" && <Loader2 className="h-2 w-2 animate-spin text-signal" />}
    </span>
  );
}

export function EvaluationWorkflowPanel({ edge, targetLabel, getPlan, onResolve }: Props) {
  if (!edge) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-center text-sm text-muted-foreground">
        Select an edge to open its evaluation workflow.
      </div>
    );
  }
  return (
    <WorkflowBody
      edgeId={edge.id}
      targetLabel={targetLabel}
      getPlan={getPlan}
      onResolve={onResolve}
    />
  );
}

function WorkflowBody({
  edgeId,
  targetLabel,
  getPlan,
  onResolve,
}: {
  edgeId: string;
  targetLabel: string;
  getPlan: (edgeId: string) => Promise<EvaluationPlan>;
  onResolve: (edgeId: string) => Promise<EvaluationPlan>;
}) {
  const { workflow, status, resolve } = useEvaluationWorkflow(edgeId, getPlan, onResolve);

  // Initial load: no plan yet
  if (status === "loading" && !workflow) {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading evaluation plan…
      </div>
    );
  }

  // Initial load failed: no plan to show
  if (status === "error" && !workflow) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-center text-sm text-destructive">
        Failed to load evaluation plan for this edge.
      </div>
    );
  }

  // Should not happen, but guard against null workflow with no error
  if (!workflow) {
    return (
      <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading evaluation plan…
      </div>
    );
  }

  const edgeName = workflow.sourceLabel
    ? `${workflow.sourceLabel} → ${workflow.targetLabel}`
    : workflow.targetLabel || targetLabel;

  const resolveButtonLabel =
    status === "resolving" ? null : status === "error" ? "Resolve failed — retry?" : "Resolve from public data";

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-baseline gap-2 border-b border-border px-4 py-3">
        <span className="text-sm font-semibold text-foreground">Evaluation workflow</span>
        <span className="font-mono text-[11px] text-muted-foreground">
          · {edgeName} · {workflow.steps.length} steps
        </span>
      </div>
      {status === "error" && (
        <div className="border-b border-red-900/60 bg-red-950/40 px-4 py-2 text-xs text-red-400">
          Resolution failed. The plan above is preserved — you can retry below.
        </div>
      )}
      <div className="flex-1 overflow-y-auto px-4 pb-6 pt-3.5">
        <ol className="relative ml-[9px] border-l-2 border-border pl-5">
          {workflow.steps.map((step) => (
            <li key={step.id} className="relative mb-3.5">
              <span className="absolute -left-[27.5px] top-3">
                <StepDot status={step.status} />
              </span>
              <StepCard step={step} />
            </li>
          ))}
        </ol>
      </div>
      <div className="shrink-0 border-t border-border px-4 py-3">
        <button
          onClick={resolve}
          disabled={status === "resolving"}
          className={cn(
            "w-full rounded-md px-3 py-2 text-xs font-semibold transition-[transform,box-shadow,background-color] duration-150 ease-out active:scale-[0.98]",
            status === "resolving"
              ? "cursor-not-allowed border border-border bg-surface-1 text-muted-foreground"
              : status === "error"
                ? "border border-red-700 bg-red-950 text-red-300 hover:bg-red-900"
                : "glow-signal bg-primary text-primary-foreground hover:brightness-110",
          )}
        >
          {status === "resolving" ? (
            <span className="flex items-center justify-center gap-1.5">
              <Loader2 className="h-3 w-3 animate-spin" />
              Resolving from public data…
            </span>
          ) : (
            resolveButtonLabel
          )}
        </button>
      </div>
    </div>
  );
}

function StepCard({ step }: { step: WorkflowStep }) {
  return (
    <div
      className={cn(
        "elev-sm rounded-xl border bg-gradient-to-b from-surface-2/60 to-surface-1 p-2.5 px-3",
        step.status === "running"
          ? "border-signal/50"
          : step.status === "needs_you"
            ? "border-amber-800"
            : step.kind === "record"
              ? "border-teal-900 from-teal-950/40 to-surface-1"
              : "border-border",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span
          className={cn(
            "text-[10.5px] uppercase tracking-wide",
            step.kind === "record" ? "text-teal-400" : "text-muted-foreground",
          )}
        >
          {GLYPHS[step.index - 1] ?? step.index} {step.label}
        </span>
        <span
          className={cn(
            "whitespace-nowrap rounded-full border px-2 py-0.5 text-[9px] font-semibold",
            STATE_PILL[step.status],
          )}
        >
          {STATE_LABEL[step.status]}
        </span>
      </div>

      <h4 className="mt-1 text-[13px] text-foreground">
        {step.title}
        {step.method && (
          <span className="text-[11px] font-normal text-muted-foreground">
            {" "}
            · <code className="rounded border border-border bg-background px-1 font-mono text-[10px] text-foreground/90">{step.method}</code>
          </span>
        )}
      </h4>
      {step.subtitle && <p className="text-[11px] text-muted-foreground">{step.subtitle}</p>}

      {step.chips && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {step.chips.map((c) => (
            <span key={c} className="rounded-full border border-border px-2 py-0.5 font-mono text-[9px] text-muted-foreground">
              {c}
            </span>
          ))}
        </div>
      )}

      {step.subSteps && <SubDag subSteps={step.subSteps} />}
    </div>
  );
}

// The fractal sub-DAG: a step's own workflow, rendered as a horizontal lane of
// mini-steps with chevrons between them, inside a dashed frame.
function SubDag({ subSteps }: { subSteps: WorkflowSubStep[] }) {
  return (
    <div className="mt-2.5 rounded-xl border border-dashed border-border-strong bg-background/60 p-2.5">
      <div className="mb-2 flex items-center justify-between text-[9.5px] uppercase tracking-wider text-muted-foreground">
        <span>↳ its own workflow</span>
        <span className="rounded border border-border-strong px-1.5 py-px text-[9px] text-muted-foreground">
          {subSteps.length} steps
        </span>
      </div>
      <div className="flex items-stretch gap-0 overflow-x-auto pb-0.5">
        {subSteps.map((ss, i) => (
          <div key={ss.id} className="flex items-stretch">
            <div
              className={cn(
                "min-w-[98px] rounded-lg border bg-surface-1 p-2",
                ss.status === "done"
                  ? "border-emerald-800"
                  : ss.status === "running"
                    ? "border-signal/50 shadow-[0_0_0_1px_color-mix(in_oklab,var(--signal)_30%,transparent)]"
                    : "border-border",
              )}
            >
              <div className="text-[10.5px] font-semibold text-foreground/90">{ss.title}</div>
              {ss.detail && <div className="font-mono text-[9px] text-muted-foreground">{ss.detail}</div>}
              <div
                className={cn(
                  "mt-1.5 text-[8.5px]",
                  ss.status === "done"
                    ? "text-emerald-300"
                    : ss.status === "running"
                      ? "text-signal"
                      : "text-muted-foreground",
                )}
              >
                {ss.status === "done" ? "● done" : ss.status === "running" ? "● running" : "○ queued"}
              </div>
            </div>
            {i < subSteps.length - 1 && (
              <div className="flex items-center px-1 text-muted-foreground/70">
                <ChevronRight className="h-3 w-3" />
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
