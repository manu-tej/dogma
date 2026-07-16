import { describe, it, expect, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useEvaluationWorkflow } from "./useEvaluationWorkflow";
import type { EvaluationPlan } from "../lib/hypothesis-client/types";

function makePlan(edgeId: string): EvaluationPlan {
  return {
    edge_id: edgeId,
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
}

describe("useEvaluationWorkflow", () => {
  it("fetches the plan on mount and sets status to ready", async () => {
    const getPlan = vi.fn().mockResolvedValue(makePlan("e1"));
    const resolvePlan = vi.fn().mockResolvedValue(makePlan("e1"));

    const { result } = renderHook(() => useEvaluationWorkflow("e1", getPlan, resolvePlan));

    expect(result.current.status).toBe("loading");
    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.workflow).not.toBeNull();
    expect(result.current.workflow!.edgeId).toBe("e1");
  });

  it("refetches when the edge id changes", async () => {
    const getPlan = vi.fn().mockImplementation((id: string) => Promise.resolve(makePlan(id)));
    const resolvePlan = vi.fn().mockResolvedValue(makePlan("e1"));

    const { result, rerender } = renderHook(
      ({ id }) => useEvaluationWorkflow(id, getPlan, resolvePlan),
      { initialProps: { id: "e1" } },
    );

    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.workflow!.edgeId).toBe("e1");

    rerender({ id: "e2" });
    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.workflow!.edgeId).toBe("e2");
  });

  it("sets status to error when getPlan rejects", async () => {
    const getPlan = vi.fn().mockRejectedValue(new Error("network error"));
    const resolvePlan = vi.fn();

    const { result } = renderHook(() => useEvaluationWorkflow("e1", getPlan, resolvePlan));

    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.workflow).toBeNull();
  });
});
