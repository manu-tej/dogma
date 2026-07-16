import { describe, expect, it } from "vitest";
import type { EvaluationPlan } from "../types";

describe("EvaluationPlan type", () => {
  it("accepts an unresolved plan", () => {
    const p: EvaluationPlan = {
      edge_id: "e1",
      claim: { source_symbol: "AKT", target_symbol: "pAKT", relation: "phosphorylates" },
      ideal_readout: { claimed_entity: "pAKT", modality: "phospho", ideal_assay_class: "phosphoproteomics" },
      resolved_readout: null, directness: null, proxy_rationale: "",
      dataset: null, alternatives: [], method: null, assumptions: [],
      expected_direction: "unknown", not_evaluable: false, resolver_provenance: {},
    };
    expect(p.ideal_readout.modality).toBe("phospho");
  });
});
