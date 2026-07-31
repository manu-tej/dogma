export type QueryKind = "simple" | "investigative";
/** "assessed" = we established whether the claim *could* be measured, but did not
 *  measure it. Distinct from "examined", which requires a measurement. The last
 *  three are deprecated truth-stamps the backend no longer emits. */
export type EdgeState =
  | "untested"
  | "assessed"
  | "examined"
  | "contested"
  | "supported"
  | "refuted";
export type NodeType =
  | "target" | "pathway" | "phenotype" | "cell_type"
  | "tissue" | "disease" | "compound" | "other";
export type EvidenceDirection = "supports" | "refutes" | "inconclusive";

export interface OntologyTermProvenance { kind: "ontology_term"; ontology: string; term_id: string; label?: string | null; }
export interface ProteinModification { kind: "phosphorylation"; residues: string[]; }
export interface ProteinStateProvenance {
  kind: "protein_state";
  family_label: string;
  members: OntologyTermProvenance[];
  modification: ProteinModification;
  resolved_to?: string | null;
}
export type NodeGrounding = OntologyTermProvenance | ProteinStateProvenance;
export interface KGEdgeProvenance { kind: "kg_edge"; source: string; reference: string; statement_count?: number | null; }
export interface LiteratureProvenance { kind: "literature"; pmid: string; }
export interface PipelineRunProvenance { kind: "pipeline_run"; run_id: string; data_accession: string; }
export type Provenance =
  | OntologyTermProvenance | KGEdgeProvenance | LiteratureProvenance | PipelineRunProvenance;

export interface GraphNode { id: string; type: NodeType; label: string; grounding?: NodeGrounding | null; position?: { x: number; y: number } | null; }

export type EdgeValidationStatus =
  | "unvalidated" | "entity_grounded_relation_unchecked"
  | "kg_supported_direct" | "kg_supported_indirect"
  | "literature_supported" | "dataset_supported"
  | "contradicted" | "unsupported" | "ambiguous" | "rejected";
/** Who proposed an edge. "demo" is built-in offline fixture content — kept
 *  distinct from "llm" so a fixture edge cannot claim a model proposed it. */
export type ProposalSource =
  | "user"
  | "llm"
  | "kg"
  | "literature"
  | "dataset"
  | "system"
  | "demo";
export interface EdgeValidation {
  status: EdgeValidationStatus; source: ProposalSource;
  evidence?: Provenance | null; rationale?: string | null;
  kg_source?: string | null; kg_version?: string | null;
  event_id?: string | null; created_at: string;
}

export interface GraphEdge {
  id: string; source_id: string; target_id: string; relation: string;
  state: EdgeState; confidence: number; suggested_by: KGEdgeProvenance[]; pending: boolean;
  // Epistemic edge validation status — separate from EdgeState and node grounding.
  // All may be absent on old graphs.
  proposal_source?: ProposalSource;
  validation_status?: EdgeValidationStatus;
  validations?: EdgeValidation[];
  display_status?: EdgeValidationStatus | null;
}
export interface CausalGraph { id: string; query: string; nodes: GraphNode[]; edges: GraphEdge[]; }

export interface MethodChoice {
  method_id: string; name: string; score: number;
  source: "structural" | "fallback"; rationale: string;
  grounding?: string | null;
}
export interface ProposedTest {
  edge_id: string; gap: string; pipeline: string; data_accession: string;
  est_cost?: number | null; est_time?: string | null;
  method?: MethodChoice | null;
}
export interface StartResult { kind: QueryKind; graph_id?: string | null; }
export interface EvidenceEntry {
  edge_id: string; direction: EvidenceDirection; weight: number;
  magnitude?: string | null; rationale?: string | null; provenance: PipelineRunProvenance;
}
export interface NextResponse { proposed: ProposedTest | null; }

export interface ClarifyingQuestion {
  id: string; prompt: string; suggestions: string[]; allow_free_text: boolean;
}
export interface SeedAnswer { question_id: string; value: string; }
export interface SeedSkeleton { nodes: GraphNode[]; edges: GraphEdge[]; rationale: string; }
export interface ClarifyingStep { kind: "questions"; questions: ClarifyingQuestion[]; }
export interface SeedStep { kind: "seeds"; skeleton: SeedSkeleton; }
export type SeedingStep = ClarifyingStep | SeedStep;

export type GraphEdit =
  | { op: "set_relation"; edge_id: string; relation: string }
  | { op: "flip_edge"; edge_id: string }
  | { op: "set_test"; edge_id: string; pipeline?: string | null; data_accession?: string | null; expected?: string | null }
  | { op: "split_edge"; edge_id: string; mechanism_label: string; mechanism_type: NodeType; source_relation: string; target_relation: string }
  | { op: "set_label"; node_id: string; label: string }
  | { op: "set_node_type"; node_id: string; node_type: NodeType }
  | { op: "set_grounding"; node_id: string; ontology: string; term_id: string; label?: string | null }
  | { op: "set_protein_state_grounding"; node_id: string; family_label: string; members: OntologyTermProvenance[]; residues: string[]; resolved_to?: string | null }
  | { op: "resolve_isoform"; node_id: string; resolved_to?: string | null }
  | { op: "merge_nodes"; node_id: string; into_node_id: string }
  | { op: "split_node"; node_id: string; new_label: string; new_type: NodeType; move_edge_ids: string[] }
  | { op: "add_connected_node"; anchor_node_id: string; new_label: string; new_type: NodeType; relation: string; direction: "to" | "from"; suggested_by: KGEdgeProvenance[] }
  | { op: "connect_nodes"; source_id: string; target_id: string; relation: string; suggested_by: KGEdgeProvenance[]; proposal_source?: ProposalSource; pending?: boolean }
  | { op: "remove_edge"; edge_id: string }
  | { op: "remove_node"; node_id: string };
export interface EdgeKnowledge { found: boolean; relations: string[]; sources: string[]; summary: string; }
export interface KGNeighbor { id: string; symbol: string; name: string; relation: string; sources: string[]; existing_node_id?: string | null; }
export interface EdgeChatMessage { role: "user" | "assistant"; content: string; }
export interface EdgeChatTurn { reply: string; proposed_edit?: GraphEdit | null; }
export interface GroundingProposal { found: boolean; summary: string; proposed_edit?: GraphEdit | null; }
export interface DatasetCandidate {
  source: "geo" | "pride";
  accession: string;
  title: string;
  summary?: string;
  n_samples?: number | null;
  organism?: string | null;
  assay?: string | null;
  primary_pmid?: string | null;
  match_reasons?: string[];
  suggested_pipeline?: string | null;
}
export interface FindDataResponse { candidates: DatasetCandidate[]; }

export type Modality =
  | "transcript" | "protein" | "phospho" | "activity"
  | "binding" | "methylation" | "phenotype" | "unknown";
export type Directness =
  | "direct" | "proxy_modality" | "proxy_correlation" | "wrong_assay" | "not_evaluable";
export type ExpectedDirection = "increase" | "decrease" | "none" | "unknown";

export interface ReadoutSpec { claimed_entity: string; modality: Modality; ideal_assay_class: string; }
export interface ResolvedReadout {
  measured_entity: string; measured_modality: Modality; assay: string;
  source: "geo" | "pride"; accession: string; feature_present?: boolean | null;
}
export interface AssumptionOutcome {
  name: string; checkable: string; threshold?: Record<string, number> | null;
  via: Array<Record<string, string>>; status: "unchecked" | "holds" | "violated" | "unknown";
}
export interface Claim { source_symbol: string; target_symbol: string; relation: string; }
export interface EvaluationPlan {
  edge_id: string; claim: Claim; ideal_readout: ReadoutSpec;
  resolved_readout: ResolvedReadout | null; directness: Directness | null; proxy_rationale: string;
  dataset: DatasetCandidate | null; alternatives: DatasetCandidate[];
  method: MethodChoice | null; assumptions: AssumptionOutcome[];
  expected_direction: ExpectedDirection; not_evaluable: boolean;
  resolver_provenance: Record<string, unknown>;
}

export interface GraphSummary {
  id: string;
  query: string;
  status: string;
  created_at: string;
  updated_at: string;
  n_nodes: number;
  n_edges: number;
}
export interface HypothesisEvent {
  ts: string;
  trace_id: string | null;
  graph_id: string | null;
  query: string | null;
  op: string;
  status: string;
  latency_ms: number | null;
  detail: Record<string, unknown> | null;
  raw_input: string | null;
  raw_output: string | null;
  error: string | null;
}
