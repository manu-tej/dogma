import { useCallback, useReducer } from "react";
import { toast } from "sonner";

import { hypothesisClient } from "../services/hypothesisService";
import { edgeChatReducer, initialEdgeChatState } from "./edgeChatReducer";

/** Per-node conversation. Reuses the chat reducer (shape is element-agnostic). */
export function useNodeChat(graphId: string, nodeId: string, onApplied: () => void) {
  const [state, dispatch] = useReducer(edgeChatReducer, initialEdgeChatState);

  const fail = useCallback((err: unknown) => {
    const message = err instanceof Error ? err.message : String(err);
    toast.error(message);
    dispatch({ type: "ERROR", message });
  }, []);

  const send = useCallback(async (message: string) => {
    if (!message.trim()) return;
    dispatch({ type: "SEND", message: message.trim() });
    try {
      const turn = await hypothesisClient.nodeChat(graphId, nodeId, state.messages, message.trim());
      dispatch({ type: "TURN", turn });
    } catch (err) {
      fail(err);
    }
  }, [graphId, nodeId, state.messages, fail]);

  const accept = useCallback(async () => {
    if (!state.pendingEdit) return;
    dispatch({ type: "APPLY_START" });
    try {
      await hypothesisClient.applyEdit(graphId, state.pendingEdit);
      dispatch({ type: "APPLIED" });
      onApplied();
    } catch (err) {
      fail(err);
    }
  }, [graphId, state.pendingEdit, onApplied, fail]);

  const reject = useCallback(() => dispatch({ type: "REJECT" }), []);

  return { state, send, accept, reject };
}
