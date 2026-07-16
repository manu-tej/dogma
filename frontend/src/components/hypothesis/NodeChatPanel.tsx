import { type FormEvent, useState } from "react";

import { useNodeChat } from "../../hooks/useNodeChat";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { ProposedEditCard } from "./ProposedEditCard";

interface NodeChatPanelProps {
  graphId: string;
  nodeId: string;
  onApplied: () => void;
}

export function NodeChatPanel({ graphId, nodeId, onApplied }: NodeChatPanelProps) {
  const { state, send, accept, reject } = useNodeChat(graphId, nodeId, onApplied);
  const [text, setText] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    send(text.trim());
    setText("");
  };

  return (
    <div className="flex flex-col gap-2">
      <h4 className="text-xs uppercase tracking-wide text-muted-foreground/70">Chat with this node</h4>

      <div className="space-y-2">
        {state.messages.map((m, i) => (
          <div key={i}
            className={m.role === "user"
              ? "ml-6 rounded-lg bg-card px-3 py-2 text-sm text-foreground"
              : "mr-6 rounded-lg bg-surface-2 px-3 py-2 text-sm text-foreground/90"}>
            {m.content}
          </div>
        ))}
        {state.status === "sending" && <p className="signal-sweep text-xs text-signal">Thinking…</p>}
      </div>

      {state.pendingEdit && (
        <ProposedEditCard edit={state.pendingEdit} applying={state.status === "applying"}
          onAccept={accept} onReject={reject} />
      )}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input value={text} onChange={(e) => setText(e.target.value)}
          placeholder="Ask about this node, or request a change…"
          aria-label="Message this node"
          className="border-border bg-surface-2 text-foreground placeholder:text-muted-foreground/70" />
        <Button type="submit" disabled={!text.trim() || state.status !== "idle"}>Send</Button>
      </form>
    </div>
  );
}
