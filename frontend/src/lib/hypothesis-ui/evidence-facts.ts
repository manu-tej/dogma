import type { EvidenceEntry } from "../hypothesis-client/types";

/**
 * Plain facts about an edge's evidence ledger — never a verdict or a grade
 * (north-star §2.2). The edge's "state" IS its ledger; this is a legible summary
 * of it, not a quality score.
 */
export interface EvidenceFacts {
  nRecords: number;
  nConsistent: number; // direction "supports" = consistent with the claimed direction
  nInconsistent: number; // direction "refutes" = inconsistent with the claimed direction
  nInconclusive: number;
  hasMethodsGrounding: boolean;
}

const isMethodsGraph = (e: EvidenceEntry) =>
  e.provenance?.kind === "pipeline_run" && e.provenance.data_accession === "methods-graph";

export function evidenceFacts(entries: EvidenceEntry[]): EvidenceFacts {
  return {
    nRecords: entries.length,
    nConsistent: entries.filter((e) => e.direction === "supports").length,
    nInconsistent: entries.filter((e) => e.direction === "refutes").length,
    nInconclusive: entries.filter((e) => e.direction === "inconclusive").length,
    hasMethodsGrounding: entries.some(isMethodsGraph),
  };
}

/**
 * A plain-facts line — never a verdict. e.g. "3 analyses · 1 inconsistent · 1 inconclusive".
 * (Richer facts like "1 with a violated assumption" arrive once assumption outcomes are
 * recorded — a later north-star slice.)
 */
export function factsSummaryLine(f: EvidenceFacts): string {
  if (f.nRecords === 0) return "No analyses recorded";
  const parts = [`${f.nRecords} analys${f.nRecords === 1 ? "is" : "es"}`];
  if (f.nInconsistent) parts.push(`${f.nInconsistent} inconsistent`);
  if (f.nInconclusive) parts.push(`${f.nInconclusive} inconclusive`);
  if (f.hasMethodsGrounding) parts.push("methods-graph grounding");
  return parts.join(" · ");
}
