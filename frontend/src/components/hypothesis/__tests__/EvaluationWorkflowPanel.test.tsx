import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvaluationWorkflowPanel } from "../EvaluationWorkflowPanel";

const plan = {
  edge_id: "e1",
  claim: { source_symbol: "AKT", target_symbol: "pAKT", relation: "phosphorylates" },
  ideal_readout: { claimed_entity: "pAKT", modality: "phospho", ideal_assay_class: "phosphoproteomics" },
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

describe("EvaluationWorkflowPanel", () => {
  it("renders the edge-specific ideal readout from the fetched plan", async () => {
    render(
      <EvaluationWorkflowPanel
        edge={{ id: "e1" } as never}
        targetLabel="pAKT"
        getPlan={() => Promise.resolve(plan as never)}
        onResolve={() => Promise.resolve(plan as never)}
      />,
    );
    await waitFor(() => expect(screen.getByText(/phosphoproteomics/i)).toBeInTheDocument());
  });
});
