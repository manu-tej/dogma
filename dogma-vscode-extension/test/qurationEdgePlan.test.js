"use strict";

const assert = require("assert");
const { renderQurationEdgePlan } = require("../src/qurationEdgePlan");

const record = {
  contract_version: "dogma-quration-edge-plan.v1",
  fetched_at: "2026-06-19T23:58:00.000Z",
  graph_id: "graph-1",
  graph_url: "http://localhost:3000/canvas/graph-1",
  edge_id: "edge-1",
  query: "Does A alter B?",
  endpoints: {
    edge_plan: "http://localhost:8000/hypothesis/graph-1/edges/edge-1/plan"
  },
  plan: {
    edge_id: "edge-1",
    claim: {
      source_symbol: "A",
      relation: "changes",
      target_symbol: "B"
    },
    ideal_readout: {
      claimed_entity: "B",
      modality: "transcript",
      ideal_assay_class: "RNA-seq"
    },
    resolved_readout: null,
    directness: null,
    proxy_rationale: "",
    dataset: null,
    alternatives: [{ accession: "GSE1", source: "geo", title: "A perturbation" }],
    method: null,
    assumptions: [
      {
        name: "matched context",
        status: "unchecked",
        checkable: "Cell type and perturbation match the claim"
      }
    ],
    expected_direction: "unknown",
    not_evaluable: false,
    resolver_provenance: { mode: "demo" }
  }
};

const markdown = renderQurationEdgePlan(record);
assert(markdown.includes("# quration Edge Plan"));
assert(markdown.includes("quration's canonical graph API"));
assert(markdown.includes("- Graph ID: graph-1"));
assert(markdown.includes("- Edge ID: edge-1"));
assert(markdown.includes("- Source: A"));
assert(markdown.includes("- Target: B"));
assert(markdown.includes("- Claimed entity: B"));
assert(markdown.includes("- Alternatives: 1"));
assert(markdown.includes("| matched context | unchecked | Cell type and perturbation match the claim |"));
assert(markdown.includes("Fetching this plan is side-effect-free"));

const emptyMarkdown = renderQurationEdgePlan({ plan: {} });
assert(emptyMarkdown.includes("- Dataset: not resolved"));
assert(emptyMarkdown.includes("| none | unchecked | not declared |"));

console.log("quration edge plan renderer tests passed");
