import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { demoGraph, demoEvidence } from "../../lib/hypothesis-ui/fixtures";
import { EdgePanels } from "./EdgePanels";

const mockPlan = {
  edge_id: demoGraph.edges[0].id,
  claim: { source_symbol: "EGFR", target_symbol: "KRAS", relation: "activates" },
  ideal_readout: { claimed_entity: "KRAS", modality: "transcript", ideal_assay_class: "RNA-seq" },
  resolved_readout: null,
  directness: null,
  proxy_rationale: "",
  dataset: null,
  alternatives: [],
  method: null,
  assumptions: [],
  expected_direction: "unknown",
  not_evaluable: false,
  resolver_provenance: {},
};

vi.mock("../../services/hypothesisService", () => ({
  get hypothesisClient() {
    return {
      edgeChat: vi.fn(),
      applyEdit: vi.fn(),
      getEvaluationPlan: vi.fn().mockResolvedValue(mockPlan),
      resolveReadout: vi.fn().mockResolvedValue(mockPlan),
    };
  },
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

describe("EdgePanels", () => {
  function renderPanels() {
    return render(
      <EdgePanels
        edge={demoGraph.edges[0]}
        sourceLabel="EGFR"
        targetLabel="KRAS"
        evidence={[demoEvidence]}
        proposal={null}
        running={false}
        onApprove={vi.fn()}
        onSkip={vi.fn()}
        graphId="g1"
        onGraphChanged={vi.fn()}
      />,
    );
  }

  it("opens on the evaluation workflow by default", async () => {
    renderPanels();
    // After the plan loads, the Ideal readout step shows the assay class
    await waitFor(() => expect(screen.getByText(/RNA-seq/i)).toBeInTheDocument());
    expect(screen.queryByText(/1 analysis/)).not.toBeInTheDocument(); // dossier not mounted yet
  });

  it("reveals the dossier when the Dossier tab is selected", () => {
    renderPanels();
    fireEvent.click(screen.getByRole("button", { name: "Dossier" }));
    expect(screen.getByText(/1 analysis/)).toBeInTheDocument(); // dossier facts line
  });
});
