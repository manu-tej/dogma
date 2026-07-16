// frontend/src/lib/hypothesis-ui/__tests__/workflow-from-plan.test.ts
import { describe, expect, it } from "vitest";
import { buildWorkflowFromPlan } from "../workflow";
import type { EvaluationPlan } from "../../hypothesis-client/types";

const base: EvaluationPlan = {
  edge_id: "e1",
  claim: { source_symbol: "AKT", target_symbol: "pAKT", relation: "phosphorylates" },
  ideal_readout: { claimed_entity: "pAKT", modality: "phospho", ideal_assay_class: "phosphoproteomics" },
  resolved_readout: { measured_entity: "total AKT mRNA", measured_modality: "transcript",
    assay: "RNA-Seq", source: "geo", accession: "GSE1", feature_present: null },
  directness: "proxy_modality", proxy_rationale: "mRNA proxy for a phospho claim",
  dataset: { source: "geo", accession: "GSE1", title: "x" } as never,
  alternatives: [], method: { method_id: "m:deseq2", name: "DESeq2", score: 0, source: "structural", rationale: "" },
  assumptions: [{ name: "normality", checkable: "pre_run", threshold: null, via: [], status: "unchecked" }],
  expected_direction: "increase", not_evaluable: false, resolver_provenance: {},
};

describe("buildWorkflowFromPlan", () => {
  it("two different modalities yield different readout steps", () => {
    const phospho = buildWorkflowFromPlan(base);
    const transcript = buildWorkflowFromPlan({
      ...base, ideal_readout: { ...base.ideal_readout, modality: "transcript" } });
    const r1 = phospho.steps.find((s) => s.kind === "readout");
    const r2 = transcript.steps.find((s) => s.kind === "readout");
    expect(r1!.subtitle).not.toEqual(r2!.subtitle);
  });

  it("surfaces directness and keeps execution pending", () => {
    const wf = buildWorkflowFromPlan(base);
    const exec = wf.steps.find((s) => s.kind === "analysis");
    expect(exec!.status).toBe("queued");                 // execution pending in slice 1
    expect(JSON.stringify(wf)).toContain("proxy_modality");
  });

  it("not_evaluable produces a single honest step", () => {
    const wf = buildWorkflowFromPlan({ ...base, not_evaluable: true, directness: "not_evaluable" });
    expect(wf.steps.some((s) => /not.*evaluable/i.test(s.title))).toBe(true);
  });

  it("surfaces demo resolver provenance as synthetic", () => {
    const wf = buildWorkflowFromPlan({
      ...base,
      dataset: { ...base.dataset!, accession: "GSE-DEMO" },
      resolver_provenance: { model: "demo", is_live: false },
    });

    expect(JSON.stringify(wf)).toContain("synthetic demo · not public data");
  });
});
