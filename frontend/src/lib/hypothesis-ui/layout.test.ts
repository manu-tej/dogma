import { describe, expect, it } from "vitest";

import { demoGraph } from "./fixtures";
import { layoutGraph } from "./layout";
import { mergePositions } from "./layout";

describe("layoutGraph", () => {
  it("returns one RF node per graph node with numeric positions", () => {
    const { nodes } = layoutGraph(demoGraph);
    expect(nodes).toHaveLength(3);
    for (const n of nodes) {
      expect(typeof n.position.x).toBe("number");
      expect(typeof n.position.y).toBe("number");
      expect(n.type).toBe("entity");
      expect(n.data.node.id).toBe(n.id);
    }
  });

  it("returns one RF edge per graph edge carrying the source/target and data", () => {
    const { edges } = layoutGraph(demoGraph);
    expect(edges).toHaveLength(2);
    const e = edges.find((x) => x.id === "e-egfr-kras")!;
    expect(e.source).toBe("P00533");
    expect(e.target).toBe("P01116");
    expect(e.type).toBe("claim");
    expect(e.data!.edge.relation).toBe("up-regulates activity");
  });

  it("lays nodes out top-to-bottom (target above its downstream)", () => {
    const { nodes } = layoutGraph(demoGraph);
    const egfr = nodes.find((n) => n.id === "P00533")!;
    const resist = nodes.find((n) => n.id === "RESIST")!;
    expect(resist.position.y).toBeGreaterThan(egfr.position.y);
  });
});

describe("mergePositions", () => {
  it("uses the server position when present", () => {
    const graph = {
      ...demoGraph,
      nodes: demoGraph.nodes.map((n) =>
        n.id === "P00533" ? { ...n, position: { x: 5, y: 7 } } : n,
      ),
    };
    const { positions } = mergePositions(graph, new Map());
    expect(positions.get("P00533")).toEqual({ x: 5, y: 7 });
  });

  it("keeps the previous (live) position when the server has none", () => {
    const prev = new Map([["P00533", { x: 11, y: 22 }]]);
    const { positions } = mergePositions(demoGraph, prev);
    expect(positions.get("P00533")).toEqual({ x: 11, y: 22 });
  });

  it("falls back to dagre for a brand-new node and flags it", () => {
    const { positions, newlyPlaced } = mergePositions(demoGraph, new Map());
    for (const n of demoGraph.nodes) {
      expect(typeof positions.get(n.id)!.x).toBe("number");
    }
    expect(newlyPlaced.sort()).toEqual([...demoGraph.nodes].map((n) => n.id).sort());
  });

  it("preserves a manual position across a structural change (node added)", () => {
    const prev = new Map([["P00533", { x: 1, y: 1 }]]);
    const grown = {
      ...demoGraph,
      nodes: [...demoGraph.nodes, { ...demoGraph.nodes[0], id: "NEW" }],
    };
    const { positions, newlyPlaced } = mergePositions(grown, prev);
    expect(positions.get("P00533")).toEqual({ x: 1, y: 1 }); // manual kept
    expect(newlyPlaced).toContain("NEW");                     // only the new one is auto-placed
    expect(newlyPlaced).not.toContain("P00533");
  });
});
