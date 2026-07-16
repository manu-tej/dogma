import type { EvaluationPlan } from "../hypothesis-client/types";

export type StepStatus = "done" | "running" | "needs_you" | "queued" | "failed";

export interface WorkflowSubStep {
  id: string;
  title: string;
  detail?: string;
  status: StepStatus;
}

export type StepKind = "dataset" | "contrast" | "analysis" | "readout" | "record";

export interface WorkflowStep {
  id: string;
  index: number; // 1-based, for the ①②… glyphs
  kind: StepKind;
  label: string; // the step's name, e.g. "Dataset", "Diff. expression"
  title: string;
  subtitle?: string; // one-line description under the title
  method?: string; // e.g. "DESeq2 · nf-core/differentialabundance"
  status: StepStatus;
  chips?: string[];
  subSteps?: WorkflowSubStep[]; // fractal sub-DAG
  expanded?: boolean;
  needsConfirm?: boolean; // the contrast gate
}

export interface EvaluationWorkflow {
  edgeId: string;
  taskClass: string; // "Differential expression"
  sourceLabel: string;
  targetLabel: string;
  steps: WorkflowStep[];
}

// ---- pure helpers (immutable) ------------------------------------------------

function mapSteps(wf: EvaluationWorkflow, fn: (s: WorkflowStep) => WorkflowStep): EvaluationWorkflow {
  return { ...wf, steps: wf.steps.map(fn) };
}

// Start the first queued step. When a step that owns sub-steps starts, its first
// sub-step starts running too (so the fractal sub-DAG streams).
function startNextQueued(steps: WorkflowStep[]): WorkflowStep[] {
  const idx = steps.findIndex((s) => s.status === "queued");
  if (idx === -1) return steps;
  return steps.map((s, i) => {
    if (i !== idx) return s;
    const started: WorkflowStep = { ...s, status: "running" };
    if (started.subSteps && started.subSteps.length > 0) {
      started.subSteps = started.subSteps.map((ss, j) =>
        j === 0 ? { ...ss, status: "running" as StepStatus } : ss,
      );
    }
    return started;
  });
}

export function confirmStep(wf: EvaluationWorkflow, stepId: string): EvaluationWorkflow {
  let steps = wf.steps.map((s) =>
    s.id === stepId ? { ...s, status: "done" as StepStatus, needsConfirm: false } : s,
  );
  steps = startNextQueued(steps);
  return { ...wf, steps };
}

export function toggleExpand(wf: EvaluationWorkflow, stepId: string): EvaluationWorkflow {
  return mapSteps(wf, (s) => (s.id === stepId ? { ...s, expanded: !(s.expanded ?? false) } : s));
}

// One mock "job tick": advance the running step's sub-steps; when all sub-steps are
// done (or there are none), complete the step and start the next queued one. A gate
// step (needs_you) blocks — tick does nothing until it is confirmed.
export function tickWorkflow(wf: EvaluationWorkflow): EvaluationWorkflow {
  const running = wf.steps.find((s) => s.status === "running");
  if (!running) return wf;

  if (running.subSteps && running.subSteps.length > 0) {
    const subs = running.subSteps;
    const runningSub = subs.findIndex((s) => s.status === "running");
    if (runningSub !== -1) {
      const next = subs.map((s, i) => {
        if (i === runningSub) return { ...s, status: "done" as StepStatus };
        if (i === runningSub + 1) return { ...s, status: "running" as StepStatus };
        return s;
      });
      const allDone = next.every((s) => s.status === "done");
      let steps = wf.steps.map((s) =>
        s.id === running.id
          ? { ...s, subSteps: next, status: allDone ? ("done" as StepStatus) : s.status }
          : s,
      );
      if (allDone) steps = startNextQueued(steps);
      return { ...wf, steps };
    }
  }

  // no sub-steps: complete the step, start the next
  let steps = wf.steps.map((s) => (s.id === running.id ? { ...s, status: "done" as StepStatus } : s));
  steps = startNextQueued(steps);
  return { ...wf, steps };
}

// ---- plan-driven builder -----------------------------------------------------

export function buildWorkflowFromPlan(plan: EvaluationPlan): EvaluationWorkflow {
  const edgeName = `${plan.claim.source_symbol} → ${plan.claim.target_symbol}`;
  if (plan.not_evaluable) {
    return {
      edgeId: plan.edge_id, taskClass: "Not evaluable",
      sourceLabel: plan.claim.source_symbol, targetLabel: plan.claim.target_symbol,
      steps: [{
        id: `${plan.edge_id}-na`, index: 1, kind: "record", label: "Not evaluable",
        title: "Not empirically evaluable",
        subtitle: "definitional / no measurable readout for this claim", status: "done",
      }],
    };
  }
  const isSyntheticDemo =
    plan.resolver_provenance?.model === "demo" || plan.dataset?.accession === "GSE-DEMO";
  const directnessChips = plan.directness
    ? [plan.directness, ...(plan.proxy_rationale ? [plan.proxy_rationale] : [])]
    : ["unresolved"];
  if (isSyntheticDemo) directnessChips.unshift("synthetic demo · not public data");
  const assumptionChips = plan.assumptions.map(
    (a) => `${a.name}${a.threshold ? ` ≥ ${Object.values(a.threshold)[0]}` : ""}`);
  return {
    edgeId: plan.edge_id, taskClass: plan.ideal_readout.ideal_assay_class,
    sourceLabel: plan.claim.source_symbol, targetLabel: plan.claim.target_symbol,
    steps: [
      { id: `${plan.edge_id}-readout-ideal`, index: 1, kind: "readout", label: "Ideal readout",
        title: plan.ideal_readout.claimed_entity,
        subtitle: `${plan.ideal_readout.modality} · ${plan.ideal_readout.ideal_assay_class}`,
        status: "done" },
      { id: `${plan.edge_id}-resolve`, index: 2, kind: "dataset", label: "Resolved readout",
        title: plan.dataset ? `${plan.dataset.source.toUpperCase()} ${plan.dataset.accession}`
                            : "no dataset yet",
        subtitle: plan.resolved_readout
          ? `measures ${plan.resolved_readout.measured_entity}` : "click Resolve to search public data",
        status: plan.resolved_readout ? "done" : "queued", chips: directnessChips },
      { id: `${plan.edge_id}-ground`, index: 3, kind: "contrast", label: "Grounded method",
        title: plan.method?.name ?? "no grounded method",
        method: plan.method?.method_id, status: plan.method ? "done" : "queued",
        chips: assumptionChips.length ? assumptionChips : ["coverage gap"] },
      { id: `${plan.edge_id}-execute`, index: 4, kind: "analysis", label: "Execute",
        title: "execution pending", subtitle: "real pipeline run lands in slice 2", status: "queued" },
      { id: `${plan.edge_id}-record`, index: 5, kind: "record", label: "Evidence record",
        title: `→ attaches to ${edgeName}`,
        subtitle: "typed record · facts + directness · no verdict", status: "queued" },
    ],
  };
}

// ---- demo builder ------------------------------------------------------------

export function buildDemoWorkflow(
  edgeId: string,
  targetLabel: string,
  sourceLabel = "",
): EvaluationWorkflow {
  const edgeName = sourceLabel ? `${sourceLabel} → ${targetLabel}` : targetLabel;
  return {
    edgeId,
    taskClass: "Differential expression",
    sourceLabel,
    targetLabel,
    steps: [
      {
        id: `${edgeId}-dataset`,
        index: 1,
        kind: "dataset",
        label: "Dataset",
        title: "SYNTHETIC DEMO",
        subtitle: "offline placeholder · no public accession or sample count",
        status: "done",
        chips: ["synthetic", "not public data"],
      },
      {
        id: `${edgeId}-contrast`,
        index: 2,
        kind: "contrast",
        label: "Contrast",
        title: "synthetic case vs control",
        subtitle: "demo-only contrast; no sample metadata was inspected",
        status: "needs_you",
        needsConfirm: true,
        chips: ["placeholder contrast"],
      },
      {
        id: `${edgeId}-analysis`,
        index: 3,
        kind: "analysis",
        label: "Diff. expression",
        title: "DESeq2",
        method: "nf-core/differentialabundance",
        status: "queued",
        expanded: true,
        subSteps: [
          { id: `${edgeId}-an-1`, title: "Size factors", detail: "median-of-ratios", status: "queued" },
          { id: `${edgeId}-an-2`, title: "Dispersion", detail: "gene-wise", status: "queued" },
          { id: `${edgeId}-an-3`, title: "NB GLM", detail: "Wald test", status: "queued" },
          { id: `${edgeId}-an-4`, title: "LFC shrink", detail: "apeglm", status: "queued" },
          { id: `${edgeId}-an-5`, title: "Results", detail: "log2FC, padj", status: "queued" },
        ],
      },
      {
        id: `${edgeId}-readout`,
        index: 4,
        kind: "readout",
        label: "Readout",
        title: `${targetLabel} change`,
        subtitle: "target gene's log2FC + adj. p under the contrast",
        status: "queued",
        chips: ["log2FC", "adj. p"],
      },
      {
        id: `${edgeId}-record`,
        index: 5,
        kind: "record",
        label: "Evidence record",
        title: `→ attaches to ${edgeName}`,
        subtitle: "typed DE record · facts + caveats · no verdict",
        status: "queued",
      },
    ],
  };
}
