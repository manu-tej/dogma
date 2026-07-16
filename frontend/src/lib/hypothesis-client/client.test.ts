import { afterEach, describe, expect, it, vi } from "vitest";

import { HypothesisClient } from "./client";

function mockFetch(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: "err",
    json: async () => body,
  });
}

describe("HypothesisClient", () => {
  afterEach(() => vi.restoreAllMocks());

  it("start posts the query and returns StartResult", async () => {
    const fetchMock = mockFetch(200, { kind: "investigative", graph_id: "g1" });
    vi.stubGlobal("fetch", fetchMock);
    const client = new HypothesisClient({ baseUrl: "http://x/" });
    const res = await client.start("does EGFR drive resistance?");
    expect(res.graph_id).toBe("g1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://x/hypothesis/start");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ query: "does EGFR drive resistance?" });
  });

  it("nextProposal unwraps the proposed field", async () => {
    vi.stubGlobal("fetch", mockFetch(200, {
      proposed: { edge_id: "e1", gap: "g", pipeline: "p", data_accession: "d" },
    }));
    const client = new HypothesisClient({ baseUrl: "http://x" });
    const proposed = await client.nextProposal("g1");
    expect(proposed?.edge_id).toBe("e1");
  });

  it("approve posts the proposal and returns the evidence entry", async () => {
    const fetchMock = mockFetch(200, {
      edge_id: "e1", direction: "supports", weight: 1.0,
      provenance: { kind: "pipeline_run", run_id: "r", data_accession: "d" },
    });
    vi.stubGlobal("fetch", fetchMock);
    const client = new HypothesisClient({ baseUrl: "http://x" });
    const entry = await client.approve("g1", { edge_id: "e1", gap: "g", pipeline: "p", data_accession: "d" });
    expect(entry.direction).toBe("supports");
    expect(fetchMock.mock.calls[0][0]).toBe("http://x/hypothesis/g1/approve");
  });

  it("throws with the API detail on error", async () => {
    vi.stubGlobal("fetch", mockFetch(404, { detail: "unknown graph: nope" }));
    const client = new HypothesisClient({ baseUrl: "http://x" });
    await expect(client.getGraph("nope")).rejects.toThrow("unknown graph: nope");
  });

  it("seed posts query+answers and returns the step", async () => {
    const fetchMock = mockFetch(200, {
      kind: "questions",
      questions: [{ id: "context", prompt: "Which cancer?", suggestions: ["lung"], allow_free_text: true }],
    });
    vi.stubGlobal("fetch", fetchMock);
    const client = new HypothesisClient({ baseUrl: "http://x" });
    const step = await client.seed("q", [{ question_id: "context", value: "lung" }]);
    expect(step.kind).toBe("questions");
    expect(fetchMock.mock.calls[0][0]).toBe("http://x/hypothesis/seed");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body as string)).toEqual({
      query: "q", answers: [{ question_id: "context", value: "lung" }],
    });
  });

  it("build posts the skeleton and returns the StartResult", async () => {
    vi.stubGlobal("fetch", mockFetch(200, { kind: "investigative", graph_id: "g9" }));
    const client = new HypothesisClient({ baseUrl: "http://x" });
    const skeleton = { nodes: [], edges: [], rationale: "r" };
    const res = await client.build("q", skeleton);
    expect(res.graph_id).toBe("g9");
  });

  it("edgeChat posts history+message and returns the turn", async () => {
    const fetchMock = mockFetch(200, { reply: "ok", proposed_edit: { op: "flip_edge", edge_id: "e1" } });
    vi.stubGlobal("fetch", fetchMock);
    const client = new HypothesisClient({ baseUrl: "http://x" });
    const turn = await client.edgeChat("g1", "e1", [], "flip it");
    expect(turn.proposed_edit?.op).toBe("flip_edge");
    expect(fetchMock.mock.calls[0][0]).toBe("http://x/hypothesis/g1/edges/e1/chat");
  });

  it("applyEdit posts the edit and returns the graph", async () => {
    vi.stubGlobal("fetch", mockFetch(200, { id: "g1", query: "q", nodes: [], edges: [] }));
    const client = new HypothesisClient({ baseUrl: "http://x" });
    const graph = await client.applyEdit("g1", { op: "flip_edge", edge_id: "e1" });
    expect(graph.id).toBe("g1");
  });

  it("groundNode posts to the ground route and returns the proposal", async () => {
    const fetchMock = mockFetch(200, {
      found: true, summary: "matched",
      proposed_edit: { op: "set_grounding", node_id: "n1", ontology: "UniProt", term_id: "P00533" },
    });
    vi.stubGlobal("fetch", fetchMock);
    const client = new HypothesisClient({ baseUrl: "http://x" });
    const proposal = await client.groundNode("g1", "n1");
    expect(proposal.found).toBe(true);
    expect(proposal.proposed_edit?.op).toBe("set_grounding");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://x/hypothesis/g1/nodes/n1/ground");
    expect(init.method).toBe("POST");
  });

  it("findData posts to the find-data route and unwraps candidates", async () => {
    const fetchMock = mockFetch(200, {
      candidates: [{ source: "geo", accession: "GSE1", title: "t", suggested_pipeline: "nf-core/differentialabundance" }],
    });
    vi.stubGlobal("fetch", fetchMock);
    const client = new HypothesisClient({ baseUrl: "http://x" });
    const cands = await client.findData("g1", "e1");
    expect(cands).toHaveLength(1);
    expect(cands[0].accession).toBe("GSE1");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://x/hypothesis/g1/edges/e1/find-data");
    expect(init.method).toBe("POST");
  });
});
