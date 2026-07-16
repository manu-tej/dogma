import type { EdgeChatMessage, EdgeChatTurn, GraphEdit } from "../lib/hypothesis-client";

export type EdgeChatStatus = "idle" | "sending" | "applying";

export interface EdgeChatState {
  messages: EdgeChatMessage[];
  pendingEdit: GraphEdit | null;
  status: EdgeChatStatus;
  error: string | null;
}

export const initialEdgeChatState: EdgeChatState = {
  messages: [], pendingEdit: null, status: "idle", error: null,
};

export type EdgeChatAction =
  | { type: "SEND"; message: string }
  | { type: "TURN"; turn: EdgeChatTurn }
  | { type: "APPLY_START" }
  | { type: "APPLIED" }
  | { type: "REJECT" }
  | { type: "ERROR"; message: string };

export function edgeChatReducer(state: EdgeChatState, action: EdgeChatAction): EdgeChatState {
  switch (action.type) {
    case "SEND":
      return {
        ...state, status: "sending", error: null,
        messages: [...state.messages, { role: "user", content: action.message }],
      };
    case "TURN":
      return {
        ...state, status: "idle",
        messages: [...state.messages, { role: "assistant", content: action.turn.reply }],
        pendingEdit: action.turn.proposed_edit ?? null,
      };
    case "APPLY_START":
      return { ...state, status: "applying", error: null };
    case "APPLIED":
      return {
        ...state, status: "idle", pendingEdit: null,
        messages: [...state.messages, { role: "assistant", content: "✓ Applied." }],
      };
    case "REJECT":
      return { ...state, pendingEdit: null };
    case "ERROR":
      return { ...state, status: "idle", error: action.message };
    default:
      return state;
  }
}
