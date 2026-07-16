import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { demoEvidence, demoGraph, demoProposal } from "../../lib/hypothesis-ui/fixtures";
import { EdgeDossier } from "./EdgeDossier";

vi.mock("../../services/hypothesisService", () => ({
  get hypothesisClient() { return { edgeChat: vi.fn(), applyEdit: vi.fn() }; },
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

const edge = demoGraph.edges[0];
const sourceLabel = "EGFR";
const targetLabel = "KRAS";

describe("EdgeDossier", () => {
  it("shows an empty state when no edge is selected", () => {
    render(
      <EdgeDossier edge={null} sourceLabel="" targetLabel=""
        evidence={[]} proposal={null} running={false}
        onApprove={vi.fn()} onSkip={vi.fn()}
        graphId="g1" onGraphChanged={vi.fn()} />,
    );
    expect(screen.getByText(/select an edge/i)).toBeInTheDocument();
  });

  it("renders claim, at-a-glance facts, known sources, ledger, and the checkpoint", () => {
    render(
      <EdgeDossier edge={edge} sourceLabel={sourceLabel} targetLabel={targetLabel}
        evidence={[demoEvidence]} proposal={demoProposal} running={false}
        onApprove={vi.fn()} onSkip={vi.fn()}
        graphId="g1" onGraphChanged={vi.fn()} />,
    );
    expect(screen.getByText(/EGFR/)).toBeInTheDocument();
    expect(screen.getByText(/KRAS/)).toBeInTheDocument();
    // Facts line, not a verdict meter; ledger row reads as a factual observation.
    expect(screen.getByText(/1 analysis/)).toBeInTheDocument();
    expect(screen.getByText("demo")).toBeInTheDocument();
    expect(screen.getByText("consistent with claim")).toBeInTheDocument();
    expect(screen.getByText(/next checkpoint/i)).toBeInTheDocument();
  });

  it("omits the checkpoint when there is no proposal", () => {
    render(
      <EdgeDossier edge={edge} sourceLabel={sourceLabel} targetLabel={targetLabel}
        evidence={[]} proposal={null} running={false}
        onApprove={vi.fn()} onSkip={vi.fn()}
        graphId="g1" onGraphChanged={vi.fn()} />,
    );
    expect(screen.queryByText(/next checkpoint/i)).not.toBeInTheDocument();
    expect(screen.getByText(/not the current focus/i)).toBeInTheDocument();
  });
});
