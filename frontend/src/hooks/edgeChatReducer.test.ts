import { describe, expect, it } from "vitest";

import { edgeChatReducer, initialEdgeChatState } from "./edgeChatReducer";

const edit = { op: "flip_edge" as const, edge_id: "e1" };

describe("edgeChatReducer", () => {
  it("SEND appends the user message and goes sending", () => {
    const s = edgeChatReducer(initialEdgeChatState, { type: "SEND", message: "flip it" });
    expect(s.status).toBe("sending");
    expect(s.messages).toEqual([{ role: "user", content: "flip it" }]);
  });

  it("TURN appends the assistant reply and stores the proposed edit", () => {
    let s = edgeChatReducer(initialEdgeChatState, { type: "SEND", message: "flip it" });
    s = edgeChatReducer(s, { type: "TURN", turn: { reply: "ok", proposed_edit: edit } });
    expect(s.status).toBe("idle");
    expect(s.messages.at(-1)).toEqual({ role: "assistant", content: "ok" });
    expect(s.pendingEdit).toEqual(edit);
  });

  it("REJECT clears the pending edit", () => {
    const s = edgeChatReducer(
      { ...initialEdgeChatState, pendingEdit: edit }, { type: "REJECT" });
    expect(s.pendingEdit).toBeNull();
  });

  it("APPLIED clears the pending edit and notes it", () => {
    const s = edgeChatReducer(
      { ...initialEdgeChatState, pendingEdit: edit, status: "applying" }, { type: "APPLIED" });
    expect(s.pendingEdit).toBeNull();
    expect(s.status).toBe("idle");
    expect(s.messages.at(-1)?.role).toBe("assistant");
  });

  it("ERROR records the message and returns to idle", () => {
    const s = edgeChatReducer({ ...initialEdgeChatState, status: "sending" },
      { type: "ERROR", message: "boom" });
    expect(s.error).toBe("boom");
    expect(s.status).toBe("idle");
  });
});
