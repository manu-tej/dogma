/**
 * Clicking an edge's label must select that edge.
 *
 * React Flow draws edge labels through `EdgeLabelRenderer`, which portals into a
 * DOM node outside the flow pane. That layer is not part of React Flow's event
 * system, so `onEdgeClick` never fires for a label — only for the thin SVG path.
 *
 * The labels carried `pointer-events-none`, React Flow's own default advice, and
 * the result was worse than an inert label: the click fell through to the pane,
 * hit `onPaneClick`, and *deselected*. The most obvious thing to click on an
 * edge cleared the selection instead of opening it.
 *
 * These target `ClaimEdgeLabel` rather than the whole canvas on purpose. React
 * Flow renders no edges in jsdom without measured node dimensions — the existing
 * `CausalCanvas.test.tsx` only ever asserts on the toolbar for that reason — so
 * a canvas-level test here would find no labels and prove nothing.
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ClaimEdgeLabel } from "./ClaimEdgeLabel";

function renderLabel(onSelect = vi.fn(), onPaneClick = vi.fn()) {
  render(
    // The pane handler sits above the label exactly as it does in CausalCanvas,
    // so a click that keeps propagating reaches it — which is the real defect.
    <div onClick={onPaneClick}>
      <ClaimEdgeLabel
        relation="drives"
        selected={false}
        onSelect={onSelect}
        borderColor="red"
        color="red"
      />
    </div>,
  );
  return { onSelect, onPaneClick };
}

describe("ClaimEdgeLabel", () => {
  it("is a control, not decoration", () => {
    renderLabel();
    expect(screen.getByRole("button", { name: /select claim: drives/i })).toBeTruthy();
  });

  it("selects its edge when clicked", () => {
    const { onSelect } = renderLabel();
    fireEvent.click(screen.getByRole("button", { name: /select claim/i }));
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("does not let the click reach the pane", () => {
    // Without stopPropagation the pane handler runs and clears the selection, so
    // the edge flickers selected then deselects — indistinguishable from a dead
    // label, which is how this was reported.
    const { onSelect, onPaneClick } = renderLabel();
    fireEvent.click(screen.getByRole("button", { name: /select claim/i }));
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onPaneClick).not.toHaveBeenCalled();
  });

  it("accepts pointer events", () => {
    // The literal defect: `pointer-events-none` made the element unhittable.
    renderLabel();
    const button = screen.getByRole("button", { name: /select claim/i });
    expect(button.className).toContain("pointer-events-auto");
    expect(button.className).not.toContain("pointer-events-none");
  });

  it("is keyboard reachable", () => {
    // A styled div was neither focusable nor announced. A button is both.
    const { onSelect } = renderLabel();
    const button = screen.getByRole("button", { name: /select claim/i });
    button.focus();
    expect(document.activeElement).toBe(button);
    fireEvent.keyDown(button, { key: "Enter" });
    fireEvent.click(button); // Enter on a native button dispatches click
    expect(onSelect).toHaveBeenCalled();
  });

  it("reports selection state to assistive tech", () => {
    render(
      <ClaimEdgeLabel
        relation="drives"
        selected
        onSelect={vi.fn()}
        borderColor="red"
        color="red"
      />,
    );
    expect(
      screen.getByRole("button", { name: /select claim/i }).getAttribute("aria-pressed"),
    ).toBe("true");
  });

  it("still shows the relation and any badges", () => {
    render(
      <ClaimEdgeLabel
        relation="drives"
        selected={false}
        onSelect={vi.fn()}
        borderColor="red"
        color="red"
      >
        <span>· kg</span>
      </ClaimEdgeLabel>,
    );
    const button = screen.getByRole("button", { name: /select claim/i });
    expect(button.textContent).toContain("drives");
    expect(button.textContent).toContain("kg");
  });
});
