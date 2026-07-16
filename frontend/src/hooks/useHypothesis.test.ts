import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { demoEvidence, demoGraph, demoProposal } from "../lib/hypothesis-ui/fixtures";

// Mock the client singleton and the toaster the hook depends on.
const client = {
  start: vi.fn(),
  getGraph: vi.fn(),
  nextProposal: vi.fn(),
  approve: vi.fn(),
};
vi.mock("../services/hypothesisService", () => ({
  get hypothesisClient() {
    return client;
  },
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

import { useHypothesis } from "./useHypothesis";

afterEach(() => vi.clearAllMocks());

async function startedHook() {
  client.start.mockResolvedValue({ kind: "investigative", graph_id: demoGraph.id });
  client.getGraph.mockResolvedValue(demoGraph);
  const hook = renderHook(() => useHypothesis());
  await act(async () => {
    await hook.result.current.runQuery("does EGFR drive resistance?");
  });
  await waitFor(() => expect(hook.result.current.state.graph?.id).toBe(demoGraph.id));
  return hook;
}

describe("useHypothesis", () => {
  it("runQuery loads the graph for an investigative result", async () => {
    const { result } = await startedHook();
    expect(result.current.state.status).toBe("ready");
    expect(result.current.state.graph?.edges).toHaveLength(2);
  });

  it("attaches the proposal only when it targets the selected edge", async () => {
    const { result } = await startedHook();
    client.nextProposal.mockResolvedValue(demoProposal); // proposal is for e-egfr-kras

    await act(async () => {
      await result.current.selectEdge("e-egfr-kras");
    });
    expect(result.current.state.proposal?.edge_id).toBe("e-egfr-kras");

    await act(async () => {
      await result.current.selectEdge("e-kras-resist"); // proposal is for a different edge
    });
    expect(result.current.state.proposal).toBeNull();
  });

  it("approve returns the recorded evidence entry and refreshes the graph on success", async () => {
    const { result } = await startedHook();
    client.approve.mockResolvedValue(demoEvidence);
    client.getGraph.mockResolvedValue(demoGraph);

    let entry: typeof demoEvidence | null | undefined;
    await act(async () => {
      entry = await result.current.approve(demoProposal);
    });
    expect(entry).toEqual(demoEvidence);
    expect(client.approve).toHaveBeenCalledWith(demoGraph.id, demoProposal);
  });

  it("approve returns null when the run fails (no phantom success)", async () => {
    const { result } = await startedHook();
    client.approve.mockRejectedValue(new Error("pipeline broke"));

    let entry: typeof demoEvidence | null | undefined;
    await act(async () => {
      entry = await result.current.approve(demoProposal);
    });
    expect(entry).toBeNull();
    expect(result.current.state.error).toBe("pipeline broke");
  });
});
