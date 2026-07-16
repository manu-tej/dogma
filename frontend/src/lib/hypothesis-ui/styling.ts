import type { EdgeState, EdgeValidationStatus, GraphEdge, NodeType } from "../hypothesis-client";

export interface EdgeStateStyle {
  color: string;   // hex, used for stroke + badge
  label: string;
  dashed: boolean;
}

// Harmonized to the Northern Blot system: unified-lightness oklch, "supported"
// tied to the phosphor signal, others desaturated for the graphite canvas.
const EDGE_STATE: Record<EdgeState, EdgeStateStyle> = {
  untested: { color: "oklch(0.58 0.02 264)", label: "untested", dashed: true },
  contested: { color: "oklch(0.78 0.14 75)", label: "contested", dashed: false },
  supported: { color: "oklch(0.82 0.19 150)", label: "supported", dashed: false }, // the signal
  refuted: { color: "oklch(0.68 0.18 25)", label: "refuted", dashed: false },
};

export function edgeStateStyle(state: EdgeState): EdgeStateStyle {
  return EDGE_STATE[state];
}

/** How an edge should be drawn: dashed/dimmed only while it is a still-untested
 *  candidate. A resolved edge (supported/refuted/contested) renders solid even
 *  if the backend left `pending` set. */
export function edgeRenderFlags(
  state: EdgeState,
  pending: boolean,
): { dashed: boolean; dimmed: boolean } {
  return {
    dashed: EDGE_STATE[state].dashed,
    dimmed: pending && state === "untested",
  };
}

export interface EdgeValidationStyle {
  color: string;
  label: string;
  dashed: boolean;
  /** weak edges render at reduced opacity unless selected. */
  weak: boolean;
  /** short chip text appended to the relation label, or null. */
  badge: string | null;
}

const EDGE_VALIDATION: Record<EdgeValidationStatus, EdgeValidationStyle> = {
  unvalidated: { color: "oklch(0.58 0.02 264)", label: "draft", dashed: true, weak: true, badge: null },
  entity_grounded_relation_unchecked: {
    color: "oklch(0.66 0.02 264)",
    label: "entities grounded · relation unchecked",
    dashed: true, weak: true, badge: "entities only",
  },
  // "direct KG link" — the KG connects the two entities; it does NOT assert the
  // edge's specific causal relation/direction. Label avoids implying broad truth.
  kg_supported_direct: { color: "oklch(0.82 0.19 150)", label: "direct KG link", dashed: false, weak: false, badge: "KG link" }, // signal
  kg_supported_indirect: { color: "oklch(0.80 0.12 178)", label: "indirect KG link", dashed: false, weak: false, badge: "KG link (indirect)" }, // teal
  literature_supported: { color: "oklch(0.72 0.13 268)", label: "literature", dashed: false, weak: false, badge: "lit" }, // indigo
  dataset_supported: { color: "oklch(0.82 0.19 150)", label: "dataset-supported", dashed: false, weak: false, badge: "data ✓" }, // signal
  contradicted: { color: "oklch(0.68 0.18 25)", label: "contradicted", dashed: false, weak: false, badge: "contradicted" }, // red
  unsupported: { color: "oklch(0.52 0.02 264)", label: "unsupported", dashed: true, weak: true, badge: "unsupported" },
  ambiguous: { color: "oklch(0.78 0.14 75)", label: "ambiguous", dashed: false, weak: false, badge: "ambiguous" }, // amber
  rejected: { color: "oklch(0.50 0.01 264)", label: "rejected", dashed: true, weak: true, badge: "rejected" },
};

export function edgeValidationStyle(status: EdgeValidationStatus): EdgeValidationStyle {
  return EDGE_VALIDATION[status] ?? EDGE_VALIDATION.unvalidated;
}

/** Resolve the effective validation status of an edge. Old graphs without the
 *  new fields degrade gracefully to "unvalidated". display_status (a backend
 *  override) wins over the raw validation_status. */
export function resolveEdgeStatus(
  edge: Pick<GraphEdge, "display_status" | "validation_status">,
): EdgeValidationStatus {
  return edge.display_status ?? edge.validation_status ?? "unvalidated";
}

export interface NodeTypeStyle {
  color: string;
  /** lucide-react icon component name. */
  icon: string;
}

// Node types stay distinguishable but at unified lightness + moderate chroma so the
// graph reads as a calibrated instrument, not a full-saturation rainbow.
const NODE_TYPE: Record<NodeType, NodeTypeStyle> = {
  target: { color: "oklch(0.72 0.13 250)", icon: "Crosshair" },   // blue
  pathway: { color: "oklch(0.72 0.14 300)", icon: "Workflow" },   // violet
  phenotype: { color: "oklch(0.74 0.15 350)", icon: "Activity" }, // magenta
  cell_type: { color: "oklch(0.80 0.12 178)", icon: "Hexagon" },  // teal
  tissue: { color: "oklch(0.76 0.13 60)", icon: "Layers" },       // amber
  disease: { color: "oklch(0.70 0.16 25)", icon: "Bug" },         // red
  compound: { color: "oklch(0.82 0.13 95)", icon: "FlaskConical" }, // gold
  other: { color: "oklch(0.66 0.012 264)", icon: "Circle" },      // muted
};

export function nodeTypeStyle(type: NodeType): NodeTypeStyle {
  return NODE_TYPE[type] ?? NODE_TYPE.other;
}
