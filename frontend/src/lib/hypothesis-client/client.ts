import type {
  CausalGraph, DatasetCandidate, EdgeChatMessage, EdgeChatTurn, EdgeKnowledge, FindDataResponse,
  GraphEdit, GraphSummary, GroundingProposal, EvidenceEntry, EvaluationPlan, HypothesisEvent, KGNeighbor,
  NextResponse, ProposedTest, SeedAnswer, SeedingStep, SeedSkeleton, StartResult,
} from "./types";

export interface HypothesisClientOptions {
  /** Base URL of the FastAPI backend (e.g. "http://localhost:8000"). */
  baseUrl: string;
}

/** Client for the /hypothesis API (the checkpointed hypothesis loop). */
export class HypothesisClient {
  private baseUrl: string;

  constructor(options: HypothesisClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const resp = await fetch(`${this.baseUrl}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
    if (!resp.ok) {
      let detail = resp.statusText;
      try {
        const body = await resp.json();
        if (body && typeof body.detail === "string") detail = body.detail;
      } catch {
        // non-JSON error body; keep statusText
      }
      throw new Error(`Hypothesis API ${resp.status}: ${detail}`);
    }
    return (await resp.json()) as T;
  }

  /** Triage a query and (if investigative) assemble + save a candidate graph. */
  start(query: string): Promise<StartResult> {
    return this.request<StartResult>("/hypothesis/start", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
  }

  /** Get the next seeding step (more clarifying questions, or the seed skeleton). */
  seed(query: string, answers: SeedAnswer[]): Promise<SeedingStep> {
    return this.request<SeedingStep>("/hypothesis/seed", {
      method: "POST",
      body: JSON.stringify({ query, answers }),
    });
  }

  /** Persist an authored skeleton as the candidate graph. */
  build(query: string, skeleton: SeedSkeleton): Promise<StartResult> {
    return this.request<StartResult>("/hypothesis/build", {
      method: "POST",
      body: JSON.stringify({ query, skeleton }),
    });
  }

  /** Fetch the current causal graph. */
  getGraph(graphId: string): Promise<CausalGraph> {
    return this.request<CausalGraph>(`/hypothesis/${graphId}`);
  }

  /** Get the next checkpoint card (the decisive edge to test). Nothing runs. */
  async nextProposal(graphId: string): Promise<ProposedTest | null> {
    const res = await this.request<NextResponse>(`/hypothesis/${graphId}/next`);
    return res.proposed;
  }

  /** Approve a proposed test: runs the pipeline, records evidence, flips the edge. */
  approve(graphId: string, proposed: ProposedTest): Promise<EvidenceEntry> {
    return this.request<EvidenceEntry>(`/hypothesis/${graphId}/approve`, {
      method: "POST",
      body: JSON.stringify({ proposed }),
    });
  }

  /** One turn of the per-edge conversation (reply + optional proposed edit). */
  edgeChat(
    graphId: string, edgeId: string, history: EdgeChatMessage[], message: string,
  ): Promise<EdgeChatTurn> {
    return this.request<EdgeChatTurn>(`/hypothesis/${graphId}/edges/${edgeId}/chat`, {
      method: "POST",
      body: JSON.stringify({ history, message }),
    });
  }

  /** One turn of the per-node conversation (reply + optional proposed edit). */
  nodeChat(
    graphId: string, nodeId: string, history: EdgeChatMessage[], message: string,
  ): Promise<EdgeChatTurn> {
    return this.request<EdgeChatTurn>(`/hypothesis/${graphId}/nodes/${nodeId}/chat`, {
      method: "POST",
      body: JSON.stringify({ history, message }),
    });
  }

  /** Apply a structured edge edit; returns the mutated graph. */
  applyEdit(graphId: string, edit: GraphEdit): Promise<CausalGraph> {
    return this.request<CausalGraph>(`/hypothesis/${graphId}/apply-edit`, {
      method: "POST",
      body: JSON.stringify({ edit }),
    });
  }

  async saveLayout(
    graphId: string,
    positions: Record<string, { x: number; y: number }>,
  ): Promise<CausalGraph> {
    return this.request<CausalGraph>(`/hypothesis/${graphId}/layout`, {
      method: "PUT",
      body: JSON.stringify({ positions }),
    });
  }

  /** Look up a node's canonical ontology term; returns a reviewable grounding proposal. */
  groundNode(graphId: string, nodeId: string): Promise<GroundingProposal> {
    return this.request<GroundingProposal>(`/hypothesis/${graphId}/nodes/${nodeId}/ground`, {
      method: "POST",
    });
  }

  /** Search GEO + PRIDE for datasets relevant to an edge; attach via applyEdit(SetTest). */
  async findData(graphId: string, edgeId: string): Promise<DatasetCandidate[]> {
    const res = await this.request<FindDataResponse>(
      `/hypothesis/${graphId}/edges/${edgeId}/find-data`, { method: "POST" });
    return res.candidates;
  }

  /** What the knowledge graph knows about an edge (relation + source DBs). */
  edgeKnown(graphId: string, edgeId: string): Promise<EdgeKnowledge> {
    return this.request<EdgeKnowledge>(
      `/hypothesis/${graphId}/edges/${edgeId}/known`, { method: "POST" });
  }

  /** Top real KG neighbors of a node, offerable as new connected nodes. */
  async expandNode(graphId: string, nodeId: string): Promise<KGNeighbor[]> {
    const res = await this.request<{ neighbors: KGNeighbor[] }>(
      `/hypothesis/${graphId}/nodes/${nodeId}/expand`, { method: "POST" });
    return res.neighbors;
  }

  /** All persisted hypothesis graphs, newest first. */
  async listGraphs(): Promise<GraphSummary[]> {
    return this.request<GraphSummary[]>("/hypothesis");
  }

  /** Delete one saved graph (and its evidence + event trail) from history. */
  async deleteGraph(graphId: string): Promise<{ deleted: boolean }> {
    return this.request<{ deleted: boolean }>(`/hypothesis/${graphId}`, { method: "DELETE" });
  }

  /** Clear ALL saved graphs — returns how many were removed. */
  async clearGraphs(): Promise<{ deleted: number }> {
    return this.request<{ deleted: number }>("/hypothesis", { method: "DELETE" });
  }

  /** The full event trail for one graph, in insertion order. */
  async graphEvents(graphId: string): Promise<HypothesisEvent[]> {
    return this.request<HypothesisEvent[]>(`/hypothesis/${graphId}/events`);
  }

  /** Recent failed events across all graphs (includes seed failures with no graph). */
  async failedEvents(limit = 100): Promise<HypothesisEvent[]> {
    return this.request<HypothesisEvent[]>(`/hypothesis/events/failed?limit=${limit}`);
  }

  /** Cheap, edge-specific plan skeleton (ideal readout + grounding). No side effects. */
  getEvaluationPlan(graphId: string, edgeId: string): Promise<EvaluationPlan> {
    return this.request<EvaluationPlan>(`/hypothesis/${graphId}/edges/${edgeId}/plan`);
  }

  /** Run the agentic GEO+PRIDE resolve; fills resolved readout + directness, persists a record. */
  resolveReadout(graphId: string, edgeId: string): Promise<EvaluationPlan> {
    return this.request<EvaluationPlan>(`/hypothesis/${graphId}/edges/${edgeId}/resolve`, {
      method: "POST",
    });
  }
}
