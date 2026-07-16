import { describe, it, expect } from "vitest";
import { buildDemoWorkflow, confirmStep, toggleExpand, tickWorkflow } from "./workflow";

describe("workflow model", () => {
  it("builds a DE workflow with a needs-you contrast gate and a fractal analysis step", () => {
    const wf = buildDemoWorkflow("e1", "KRAS");
    expect(wf.edgeId).toBe("e1");
    expect(wf.steps.map((s) => s.kind)).toEqual(["dataset", "contrast", "analysis", "readout", "record"]);
    expect(wf.steps.find((s) => s.kind === "contrast")!.status).toBe("needs_you");
    expect(wf.steps.find((s) => s.kind === "analysis")!.subSteps!.length).toBeGreaterThan(0);
    expect(wf.steps.find((s) => s.kind === "readout")!.title).toContain("KRAS");
    expect(JSON.stringify(wf)).toContain("SYNTHETIC DEMO");
    expect(JSON.stringify(wf)).toContain("not public data");
  });

  it("confirmStep resolves the gate and starts the next step", () => {
    const wf = buildDemoWorkflow("e1", "KRAS");
    const contrastId = wf.steps.find((s) => s.kind === "contrast")!.id;
    const after = confirmStep(wf, contrastId);
    expect(after.steps.find((s) => s.kind === "contrast")!.status).toBe("done");
    expect(after.steps.find((s) => s.kind === "analysis")!.status).toBe("running");
    expect(wf.steps.find((s) => s.kind === "contrast")!.status).toBe("needs_you"); // original untouched
  });

  it("toggleExpand flips a step's expanded flag", () => {
    const wf = buildDemoWorkflow("e1", "KRAS");
    const id = wf.steps.find((s) => s.kind === "analysis")!.id;
    const before = wf.steps.find((s) => s.id === id)!.expanded ?? false;
    expect(toggleExpand(wf, id).steps.find((s) => s.id === id)!.expanded).toBe(!before);
  });

  it("tickWorkflow advances the running sub-step, then completes the step and starts the next", () => {
    let wf = buildDemoWorkflow("e1", "KRAS");
    wf = confirmStep(wf, wf.steps.find((s) => s.kind === "contrast")!.id); // analysis now running
    const analysis = () => wf.steps.find((s) => s.kind === "analysis")!;
    const runningSub = () => analysis().subSteps!.find((s) => s.status === "running");
    expect(runningSub()).toBeTruthy();
    for (let i = 0; i < 20 && analysis().status !== "done"; i++) wf = tickWorkflow(wf);
    expect(analysis().status).toBe("done");
    expect(wf.steps.find((s) => s.kind === "readout")!.status).toBe("running");
  });
});
