/**
 * Client for the DEG (differential expression) interpretation endpoint
 * (POST /api/v1/interpretations/deg). Converts a list of genes + two conditions
 * into tool-grounded biological claims.
 */

const API_BASE = import.meta.env.VITE_GEO_API_URL || "http://localhost:8000";

export interface GeneItem {
  geneSymbol: string;
  log2FoldChange: number;
  pValue?: number;
  adjustedPValue?: number;
}

export interface DEGRequest {
  upregulatedGenes: GeneItem[];
  downregulatedGenes: GeneItem[];
  conditionA: string;
  conditionB: string;
  experimentType?: string;
  organism?: string;
  additionalContext?: string;
  maxToolIterations?: number;
}

export interface Claim {
  claimType: string;
  statement: string;
  confidence: string;
  genesMentioned: string[];
  pathwaysMentioned: string[];
  evidenceCount: number;
}

export interface ToolCall {
  toolName: string;
  status: string;
  latencyMs: number;
  cached: boolean;
}

export interface DEGInterpretation {
  id: string;
  summary: string;
  claims: Claim[];
  toolCalls: ToolCall[];
  openQuestions: string[];
  limitations: string[];
  recommendations: string[];
  confidenceScore: number;
  tokenUsage: { inputTokens: number; outputTokens: number; totalTokens: number };
  costUsd: number;
  processingTimeMs: number;
  modelUsed: string;
}

/**
 * Parse a pasted gene table into gene items. Accepts one gene per line, columns
 * separated by tab/comma/whitespace: `SYMBOL  log2FC  [pValue]`. Header lines and
 * rows without a numeric fold change are skipped.
 */
export function parseGeneTable(text: string): GeneItem[] {
  const items: GeneItem[] = [];
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const cols = line.split(/[\t,]+|\s{1,}/).filter(Boolean);
    if (cols.length < 2) continue;
    const log2FoldChange = Number(cols[1]);
    if (!Number.isFinite(log2FoldChange)) continue; // header or malformed row
    const item: GeneItem = { geneSymbol: cols[0], log2FoldChange };
    if (cols[2] !== undefined) {
      const p = Number(cols[2]);
      if (Number.isFinite(p)) item.pValue = p;
    }
    items.push(item);
  }
  return items;
}

/** Split parsed genes into up- and down-regulated by the sign of the fold change. */
export function splitByDirection(genes: GeneItem[]): { up: GeneItem[]; down: GeneItem[] } {
  const up: GeneItem[] = [];
  const down: GeneItem[] = [];
  for (const g of genes) {
    if (g.log2FoldChange > 0) up.push(g);
    else if (g.log2FoldChange < 0) down.push(g);
  }
  return { up, down };
}

export async function interpretDEG(req: DEGRequest): Promise<DEGInterpretation> {
  const res = await fetch(`${API_BASE}/api/v1/interpretations/deg`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      experimentType: "RNA-seq",
      organism: "human",
      maxToolIterations: 10,
      ...req,
    }),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`Interpretation failed (${res.status}). ${detail.slice(0, 300)}`);
  }
  return res.json();
}
