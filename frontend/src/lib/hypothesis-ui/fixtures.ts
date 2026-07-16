import type {
  CausalGraph, EvidenceEntry, ProposedTest,
} from "../hypothesis-client";

/** Mirrors the backend demo seam (EGFR -> KRAS -> drug resistance). */
export const demoGraph: CausalGraph = {
  id: "g-demo",
  query: "Does EGFR drive KRAS-mediated drug resistance?",
  nodes: [
    { id: "P00533", type: "target", label: "EGFR",
      grounding: { kind: "ontology_term", ontology: "UniProt", term_id: "P00533" } },
    { id: "P01116", type: "target", label: "KRAS",
      grounding: { kind: "ontology_term", ontology: "UniProt", term_id: "P01116" } },
    { id: "RESIST", type: "phenotype", label: "drug resistance", grounding: null },
  ],
  edges: [
    { id: "e-egfr-kras", source_id: "P00533", target_id: "P01116",
      relation: "up-regulates activity", state: "untested", confidence: 0,
      suggested_by: [{ kind: "kg_edge", source: "demo", reference: "e-egfr-kras" }],
      pending: true },
    { id: "e-kras-resist", source_id: "P01116", target_id: "RESIST",
      relation: "drives", state: "untested", confidence: 0,
      suggested_by: [{ kind: "kg_edge", source: "demo", reference: "e-kras-resist" }],
      pending: true },
  ],
};

export const demoProposal: ProposedTest = {
  edge_id: "e-egfr-kras",
  gap: "no experimental evidence yet for: up-regulates activity",
  pipeline: "nf-core/rnaseq",
  data_accession: "GSE-DEMO",
  est_time: "~30 min",
};

export const demoEvidence: EvidenceEntry = {
  edge_id: "e-egfr-kras",
  direction: "supports",
  weight: 1.0,
  magnitude: "log2FC=1.8, padj=1e-4",
  rationale: "demo: pipeline reported a significant effect",
  provenance: { kind: "pipeline_run", run_id: "demo-run-e-egfr-kras", data_accession: "GSE-DEMO" },
};

/** demoGraph after approving e-egfr-kras: edge flips to supported. */
export const demoGraphAfterApprove: CausalGraph = {
  ...demoGraph,
  edges: demoGraph.edges.map((e) =>
    e.id === "e-egfr-kras"
      ? { ...e, state: "supported", confidence: 0.81, pending: false }
      : e,
  ),
};
