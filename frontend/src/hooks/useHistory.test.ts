import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { GraphSummary, HypothesisEvent } from "../lib/hypothesis-client";

const client = {
  listGraphs: vi.fn(),
  failedEvents: vi.fn(),
};
vi.mock("../services/hypothesisService", () => ({
  get hypothesisClient() {
    return client;
  },
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

import { useHistory } from "./useHistory";

const graph: GraphSummary = {
  id: "g1",
  query: "does EGFR drive resistance?",
  status: "active",
  created_at: "2026-06-08T00:00:00Z",
  updated_at: "2026-06-08T00:00:00Z",
  n_nodes: 3,
  n_edges: 2,
};

const failedEvent: HypothesisEvent = {
  ts: "2026-06-08T00:00:00Z",
  trace_id: null,
  graph_id: null,
  query: "broken seed",
  op: "seed",
  status: "error",
  latency_ms: 12,
  detail: null,
  raw_input: null,
  raw_output: null,
  error: "seed failed",
};

afterEach(() => vi.clearAllMocks());

describe("useHistory", () => {
  it("auto-loads graphs on mount", async () => {
    client.listGraphs.mockResolvedValue([graph]);
    const { result } = renderHook(() => useHistory());
    await waitFor(() => expect(result.current.graphs).toHaveLength(1));
    expect(result.current.graphs[0].id).toBe("g1");
    expect(client.listGraphs).toHaveBeenCalledTimes(1);
  });

  it("loadFailed populates the failures feed", async () => {
    client.listGraphs.mockResolvedValue([]);
    client.failedEvents.mockResolvedValue([failedEvent]);
    const { result } = renderHook(() => useHistory());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.loadFailed();
    });
    expect(result.current.failed).toHaveLength(1);
    expect(result.current.failed[0].op).toBe("seed");
  });

  it("records an error message when refresh fails", async () => {
    client.listGraphs.mockRejectedValue(new Error("api down"));
    const { result } = renderHook(() => useHistory());
    await waitFor(() => expect(result.current.error).toBe("api down"));
  });
});
