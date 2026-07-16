import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SeedSkeletonPreview } from "./SeedSkeletonPreview";

const skeleton = {
  rationale: "because biology",
  nodes: [
    { id: "A", type: "target" as const, label: "EGFR" },
    { id: "B", type: "phenotype" as const, label: "resistance" },
  ],
  edges: [{ id: "A-B", source_id: "A", target_id: "B", relation: "drives",
            state: "untested" as const, confidence: 0, suggested_by: [], pending: true }],
};

describe("SeedSkeletonPreview", () => {
  it("renders nodes, the rationale, and builds", () => {
    const onBuild = vi.fn();
    render(<SeedSkeletonPreview skeleton={skeleton} onBuild={onBuild}
      onDropNode={vi.fn()} onSkip={vi.fn()} building={false} />);
    expect(screen.getByText("EGFR")).toBeInTheDocument();
    expect(screen.getByText(/because biology/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /build the graph/i }));
    expect(onBuild).toHaveBeenCalled();
  });

  it("drops a node and disables build when empty", () => {
    const onDropNode = vi.fn();
    const empty = { ...skeleton, nodes: [], edges: [] };
    const { rerender } = render(
      <SeedSkeletonPreview skeleton={skeleton} onBuild={vi.fn()}
        onDropNode={onDropNode} onSkip={vi.fn()} building={false} />);
    fireEvent.click(screen.getAllByRole("button", { name: /remove/i })[0]);
    expect(onDropNode).toHaveBeenCalledWith("A");
    rerender(<SeedSkeletonPreview skeleton={empty} onBuild={vi.fn()}
      onDropNode={onDropNode} onSkip={vi.fn()} building={false} />);
    expect(screen.getByRole("button", { name: /build the graph/i })).toBeDisabled();
  });
});
