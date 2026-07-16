import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { demoGraph } from "../../lib/hypothesis-ui/fixtures";

vi.stubGlobal("confirm", () => true);

const client = {
  saveLayout: vi.fn().mockResolvedValue(undefined),
  applyEdit: vi.fn().mockResolvedValue(undefined),
};
vi.mock("../../services/hypothesisService", () => ({
  get hypothesisClient() {
    return client;
  },
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

import { CausalCanvas } from "./CausalCanvas";

// @xyflow/react needs these in jsdom.
beforeAll(() => {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
  if (!globalThis.DOMMatrixReadOnly) {
    (globalThis as Record<string, unknown>).DOMMatrixReadOnly = class {
      m22 = 1;
      constructor() {}
    };
  }
});

afterEach(() => vi.clearAllMocks());

function renderCanvas() {
  return render(
    <CausalCanvas
      graph={demoGraph}
      graphId={demoGraph.id}
      selectedEdgeId={null}
      selectedNodeId={null}
      onSelectEdge={vi.fn()}
      onSelectNode={vi.fn()}
      onGraphChanged={vi.fn()}
    />,
  );
}

// NOTE: We assert the deterministic surface (toolbar + client calls), NOT React
// Flow's rendered nodes — xyflow renders into a zero-size viewport under jsdom.
describe("CausalCanvas", () => {
  it("renders the canvas toolbar (Re-tidy + Snap toggle)", () => {
    renderCanvas();
    expect(screen.getByRole("button", { name: /re-tidy/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /snap:/i })).toBeInTheDocument();
  });

  it("re-tidy persists positions via saveLayout", async () => {
    client.saveLayout.mockResolvedValue(demoGraph);
    renderCanvas();
    fireEvent.click(screen.getByRole("button", { name: /re-tidy/i }));
    await waitFor(() => expect(client.saveLayout).toHaveBeenCalledWith(
      demoGraph.id, expect.any(Object),
    ));
  });

  it("toggles snap-to-grid", () => {
    renderCanvas();
    const btn = screen.getByRole("button", { name: /snap:/i });
    expect(btn).toHaveTextContent(/snap: on/i);
    fireEvent.click(btn);
    expect(btn).toHaveTextContent(/snap: off/i);
  });
});
