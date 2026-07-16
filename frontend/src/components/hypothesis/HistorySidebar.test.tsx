import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { GraphSummary } from "../../lib/hypothesis-client";

const client = {
  listGraphs: vi.fn(),
  failedEvents: vi.fn(),
  deleteGraph: vi.fn(),
  clearGraphs: vi.fn(),
};
vi.mock("../../services/hypothesisService", () => ({
  get hypothesisClient() {
    return client;
  },
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

import { HistorySidebar } from "./HistorySidebar";

const graph: GraphSummary = {
  id: "g1",
  query: "does EGFR drive resistance?",
  status: "active",
  created_at: "2026-06-08T00:00:00Z",
  updated_at: "2026-06-08T00:00:00Z",
  n_nodes: 3,
  n_edges: 2,
};

afterEach(() => vi.clearAllMocks());

describe("HistorySidebar", () => {
  it("lists graphs and opens one on click", async () => {
    client.listGraphs.mockResolvedValue([graph]);
    const onOpenGraph = vi.fn();
    render(
      <HistorySidebar onOpenGraph={onOpenGraph} onCollapse={vi.fn()} currentGraphId={null} />,
    );

    const row = await screen.findByText("does EGFR drive resistance?");
    fireEvent.click(row);
    expect(onOpenGraph).toHaveBeenCalledWith("g1");
  });

  it("highlights the graph currently on the canvas", async () => {
    client.listGraphs.mockResolvedValue([graph]);
    render(
      <HistorySidebar onOpenGraph={vi.fn()} onCollapse={vi.fn()} currentGraphId="g1" />,
    );

    const row = (await screen.findByText("does EGFR drive resistance?")).closest("button")!;
    expect(row).toHaveAttribute("aria-current", "true");
  });

  it("collapses via the collapse control", async () => {
    client.listGraphs.mockResolvedValue([graph]);
    const onCollapse = vi.fn();
    render(
      <HistorySidebar onOpenGraph={vi.fn()} onCollapse={onCollapse} currentGraphId={null} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Collapse history" }));
    expect(onCollapse).toHaveBeenCalled();
  });

  it("renders the 'New canvas' button when onNewCanvas is provided", async () => {
    client.listGraphs.mockResolvedValue([graph]);
    render(
      <HistorySidebar
        onOpenGraph={vi.fn()}
        onCollapse={vi.fn()}
        currentGraphId={null}
        onNewCanvas={vi.fn()}
      />,
    );

    expect(await screen.findByRole("button", { name: /new canvas/i })).toBeInTheDocument();
  });

  it("calls onNewCanvas when the 'New canvas' button is clicked", async () => {
    client.listGraphs.mockResolvedValue([graph]);
    const onNewCanvas = vi.fn();
    render(
      <HistorySidebar
        onOpenGraph={vi.fn()}
        onCollapse={vi.fn()}
        currentGraphId={null}
        onNewCanvas={onNewCanvas}
      />,
    );

    const btn = await screen.findByRole("button", { name: /new canvas/i });
    fireEvent.click(btn);
    expect(onNewCanvas).toHaveBeenCalledOnce();
  });

  it("does not render the 'New canvas' button when onNewCanvas is not provided", async () => {
    client.listGraphs.mockResolvedValue([graph]);
    render(
      <HistorySidebar onOpenGraph={vi.fn()} onCollapse={vi.fn()} currentGraphId={null} />,
    );

    // Wait for the list to load so we know the component rendered fully
    await screen.findByText("does EGFR drive resistance?");
    expect(screen.queryByRole("button", { name: /new canvas/i })).toBeNull();
  });

  it("loads the failed feed when the Failed tab is selected", async () => {
    client.listGraphs.mockResolvedValue([graph]);
    client.failedEvents.mockResolvedValue([
      {
        ts: "2026-06-08T00:00:00Z",
        trace_id: null,
        graph_id: null,
        query: "broken seed",
        op: "seed",
        status: "error",
        latency_ms: null,
        detail: null,
        raw_input: null,
        raw_output: null,
        error: "seed failed",
      },
    ]);
    render(
      <HistorySidebar onOpenGraph={vi.fn()} onCollapse={vi.fn()} currentGraphId={null} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Failed" }));
    await waitFor(() => expect(client.failedEvents).toHaveBeenCalled());
    expect(await screen.findByText("seed failed")).toBeInTheDocument();
    expect(screen.getByText("no graph")).toBeInTheDocument();
  });

  it("deletes a graph via its trash button and drops it from the list", async () => {
    client.listGraphs.mockResolvedValue([graph]);
    client.deleteGraph.mockResolvedValue({ deleted: true });
    render(
      <HistorySidebar onOpenGraph={vi.fn()} onCollapse={vi.fn()} currentGraphId={null} />,
    );
    await screen.findByText("does EGFR drive resistance?");
    fireEvent.click(screen.getByRole("button", { name: /delete graph/i }));
    await waitFor(() => expect(client.deleteGraph).toHaveBeenCalledWith("g1"));
    await waitFor(() => expect(screen.queryByText("does EGFR drive resistance?")).toBeNull());
  });

  it("clears all graphs via the header button (after confirm)", async () => {
    client.listGraphs.mockResolvedValue([graph]);
    client.clearGraphs.mockResolvedValue({ deleted: 1 });
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(
      <HistorySidebar onOpenGraph={vi.fn()} onCollapse={vi.fn()} currentGraphId={null} />,
    );
    await screen.findByText("does EGFR drive resistance?");
    fireEvent.click(screen.getByRole("button", { name: /clear all history/i }));
    expect(confirmSpy).toHaveBeenCalled();
    await waitFor(() => expect(client.clearGraphs).toHaveBeenCalled());
    confirmSpy.mockRestore();
  });
});
