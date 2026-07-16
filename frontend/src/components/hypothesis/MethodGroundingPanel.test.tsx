import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MethodGroundingPanel } from "./MethodGroundingPanel";

describe("MethodGroundingPanel", () => {
  it("renders the methodological verdict and summary", () => {
    render(<MethodGroundingPanel verdict="GROUNDED" summary="Methodologically grounded via salmon: 1 statistical method(s), 1 assumption(s)." />);
    expect(screen.getAllByText(/methodological/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/salmon/i)).toBeTruthy();
  });

  it("renders a coverage-gap state distinctly", () => {
    render(<MethodGroundingPanel verdict="COVERAGE_GAP" summary="No grounded method yet (coverage gap)." />);
    expect(screen.getByRole("heading", { name: /coverage gap/i })).toBeTruthy();
    expect(screen.getByText(/coverage gap/i, { selector: "p" })).toBeTruthy();
  });

  it("renders partial methodological grounding label", () => {
    render(<MethodGroundingPanel verdict="PARTIALLY_GROUNDED" summary="Partially grounded via method X." />);
    expect(screen.getByRole("heading", { name: /partial methodological grounding/i })).toBeTruthy();
  });

  it("renders not evaluable label", () => {
    render(<MethodGroundingPanel verdict="NOT_EVALUABLE" summary="Cannot be evaluated." />);
    expect(screen.getByRole("heading", { name: /not evaluable/i })).toBeTruthy();
  });
});
