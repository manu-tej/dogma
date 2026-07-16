import { describe, expect, it } from "vitest";

import { initialSeedingState, seedingReducer } from "./seedingReducer";

const questions = [{ id: "context", prompt: "Which?", suggestions: ["lung"], allow_free_text: true }];
const skeleton = {
  nodes: [{ id: "A", type: "target" as const, label: "A" }],
  edges: [{ id: "A-B", source_id: "A", target_id: "B", relation: "drives",
            state: "untested" as const, confidence: 0, suggested_by: [], pending: true }],
  rationale: "r",
};

describe("seedingReducer", () => {
  it("QUERY_SUBMIT records the query and goes seeding", () => {
    const s = seedingReducer(initialSeedingState, { type: "QUERY_SUBMIT", query: "q" });
    expect(s.status).toBe("seeding");
    expect(s.query).toBe("q");
  });

  it("STEP questions shows them; ANSWER appends and re-seeds", () => {
    let s = seedingReducer({ ...initialSeedingState, status: "seeding", query: "q" },
      { type: "STEP", step: { kind: "questions", questions } });
    expect(s.status).toBe("clarifying");
    expect(s.questions).toHaveLength(1);
    s = seedingReducer(s, { type: "ANSWER", answer: { question_id: "context", value: "lung" } });
    expect(s.answers).toEqual([{ question_id: "context", value: "lung" }]);
    expect(s.status).toBe("seeding");
  });

  it("STEP seeds shows the skeleton for confirm", () => {
    const s = seedingReducer({ ...initialSeedingState, status: "seeding" },
      { type: "STEP", step: { kind: "seeds", skeleton } });
    expect(s.status).toBe("proposing");
    expect(s.skeleton?.nodes).toHaveLength(1);
  });

  it("DROP_NODE removes the node and any edge touching it", () => {
    const s = seedingReducer({ ...initialSeedingState, status: "proposing", skeleton },
      { type: "DROP_NODE", nodeId: "A" });
    expect(s.skeleton?.nodes).toHaveLength(0);
    expect(s.skeleton?.edges).toHaveLength(0);
  });

  it("ERROR records the message and un-sticks the UI back to an actionable state", () => {
    // build failure: a skeleton is present -> return to proposing (buttons re-enable)
    const withSkeleton = seedingReducer({ ...initialSeedingState, status: "building", skeleton },
      { type: "ERROR", message: "boom" });
    expect(withSkeleton.error).toBe("boom");
    expect(withSkeleton.status).toBe("proposing");

    // seed failure mid-clarify: questions present -> return to clarifying
    const withQuestions = seedingReducer({ ...initialSeedingState, status: "seeding", questions },
      { type: "ERROR", message: "boom" });
    expect(withQuestions.status).toBe("clarifying");

    // seed failure at the hero: nothing yet -> back to idle
    const empty = seedingReducer({ ...initialSeedingState, status: "seeding" },
      { type: "ERROR", message: "boom" });
    expect(empty.status).toBe("idle");
  });
});
