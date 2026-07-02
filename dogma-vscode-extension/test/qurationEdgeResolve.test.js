"use strict";

const assert = require("assert");
const { renderQurationEdgeResolve } = require("../src/qurationEdgeResolve");

const record = {
  contract_version: "dogma-quration-edge-resolve.v1",
  resolved_at: "2026-06-20T02:40:00.000Z",
  status: "ready",
  graph_id: "graph-1",
  graph_url: "http://localhost:3000/canvas/graph-1",
  edge_id: "edge-1",
  query: "Does A alter B?",
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
      ideal_assay_class: "RNA-seq differential expression"
    },
    resolved_readout: {
      measured_entity: "B",
      measured_modality: "transcript",
      assay: "bulk RNA-seq",
      source: "geo",
      accession: "GSE000000",
      feature_present: true
    },
    directness: "direct",
    proxy_rationale: "",
    dataset: {
      source: "geo",
      accession: "GSE000000",
      title: "A perturbation RNA-seq"
    },
    alternatives: [{ accession: "GSE111111" }],
    method: {
      method_id: "m:deseq2",
      name: "DESeq2",
      score: 0.92,
      source: "structural",
      rationale: "RNA-seq differential expression"
    },
    assumptions: [
      {
        name: "replicates",
        status: "unchecked",
        checkable: "pre_run"
      }
    ],
    expected_direction: "unknown",
    not_evaluable: false,
    resolver_provenance: { resolver: "demo" }
  },
  dogma_preconditions: {
    confirmation: "explicit_modal_confirmation",
    patch_handoff: {
      present: true,
      artifact: ".dogma/quration-edge-patch-handoff.json",
      generated_at: "2026-06-20T02:30:00.000Z",
      patch_applied: false,
      proposal_id: "nextflow-sample-validation-1",
      guardrail_status: "blocked",
      coverage_gaps: ["methods_graph.audited_substrate_missing"]
    }
  },
  endpoints: {
    edge_resolve: "http://localhost:8000/hypothesis/graph-1/edges/edge-1/resolve"
  }
};

const markdown = renderQurationEdgeResolve(record);
assert(markdown.includes("# Dogma quration Edge Resolve"));
assert(markdown.includes("facts-only edge readout resolve"));
assert(markdown.includes("- Graph ID: graph-1"));
assert(markdown.includes("- Edge ID: edge-1"));
assert(markdown.includes("- Matching handoff: yes"));
assert(markdown.includes("- Local patch applied: false"));
assert(markdown.includes("- Dogma guardrail status: blocked"));
assert(markdown.includes("- Coverage gaps: methods_graph.audited_substrate_missing"));
assert(markdown.includes("- Source: A"));
assert(markdown.includes("- Target: B"));
assert(markdown.includes("- Directness: direct"));
assert(markdown.includes("GSE000000 (geo) - A perturbation RNA-seq"));
assert(markdown.includes("| replicates | unchecked | pre_run |"));
assert(markdown.includes("not a biological support/refute verdict"));

const empty = renderQurationEdgeResolve({});
assert(empty.includes("- Matching handoff: no"));
assert(empty.includes("- Dataset: not resolved"));

console.log("quration edge resolve renderer tests passed");
