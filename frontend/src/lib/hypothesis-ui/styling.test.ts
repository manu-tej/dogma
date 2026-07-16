import { describe, expect, it } from "vitest";

import {
  edgeRenderFlags, edgeStateStyle, edgeValidationStyle, nodeTypeStyle, resolveEdgeStatus,
} from "./styling";

describe("edgeStateStyle", () => {
  it("gives every state a distinct color and a label", () => {
    const states = ["untested", "contested", "supported", "refuted"] as const;
    const colors = states.map((s) => edgeStateStyle(s).color);
    expect(new Set(colors).size).toBe(4);
    expect(edgeStateStyle("supported").label).toBe("supported");
    expect(edgeStateStyle("untested").dashed).toBe(true);
    expect(edgeStateStyle("supported").dashed).toBe(false);
  });
});

describe("edgeRenderFlags", () => {
  it("dims and dashes only genuinely-untested pending edges", () => {
    // A resolved edge is solid even if the backend left pending=true (demo seam).
    expect(edgeRenderFlags("supported", true)).toEqual({ dashed: false, dimmed: false });
    expect(edgeRenderFlags("refuted", true)).toEqual({ dashed: false, dimmed: false });
    // A still-untested candidate edge is dashed; dimmed only while pending.
    expect(edgeRenderFlags("untested", true)).toEqual({ dashed: true, dimmed: true });
    expect(edgeRenderFlags("untested", false)).toEqual({ dashed: true, dimmed: false });
  });
});

describe("edgeValidationStyle", () => {
  it("renders unvalidated edges as weak", () => {
    const s = edgeValidationStyle("unvalidated");
    expect(s.weak).toBe(true);
    expect(s.dashed).toBe(true);
    expect(s.badge).toBeNull();
  });

  it("renders a direct KG link as solid + non-weak, labelled as a link (not causal truth)", () => {
    const s = edgeValidationStyle("kg_supported_direct");
    expect(s.weak).toBe(false);
    expect(s.dashed).toBe(false);
    expect(s.badge).toBe("KG link");
    expect(s.label).toBe("direct KG link");  // must not imply the causal relation is proven
  });

  it("renders contradicted edges in red and non-weak (never hidden)", () => {
    const s = edgeValidationStyle("contradicted");
    // red hue, harmonized to the Northern Blot oklch palette
    expect(s.color).toBe("oklch(0.68 0.18 25)");
    expect(s.weak).toBe(false);
  });

  it("renders unsupported edges as weak but still visible", () => {
    const s = edgeValidationStyle("unsupported");
    expect(s.weak).toBe(true);
    expect(s.badge).toBe("unsupported");
  });

  it("gives every status a distinct color", () => {
    const statuses = [
      "unvalidated", "entity_grounded_relation_unchecked",
      "kg_supported_direct", "kg_supported_indirect", "literature_supported",
      "dataset_supported", "contradicted", "unsupported", "ambiguous", "rejected",
    ] as const;
    const colors = statuses.map((s) => edgeValidationStyle(s).color.toLowerCase());
    // colors should be reasonably distinct (allow a couple of shared slates).
    expect(new Set(colors).size).toBeGreaterThanOrEqual(8);
    statuses.forEach((st) => expect(edgeValidationStyle(st).label).toBeTruthy());
  });
});

describe("resolveEdgeStatus", () => {
  it("prefers display_status over validation_status", () => {
    expect(resolveEdgeStatus({ display_status: "rejected", validation_status: "kg_supported_direct" }))
      .toBe("rejected");
  });

  it("falls back to validation_status when no display_status", () => {
    expect(resolveEdgeStatus({ validation_status: "literature_supported" }))
      .toBe("literature_supported");
  });

  it("falls back to unvalidated for old graphs missing both fields", () => {
    expect(resolveEdgeStatus({})).toBe("unvalidated");
    expect(resolveEdgeStatus({ display_status: null })).toBe("unvalidated");
  });
});

describe("nodeTypeStyle", () => {
  it("maps known types and falls back for unknown", () => {
    expect(nodeTypeStyle("target").icon).toBe("Crosshair");
    expect(nodeTypeStyle("phenotype").color).toBeTruthy();
    expect(nodeTypeStyle("other").icon).toBe("Circle");
  });
});
