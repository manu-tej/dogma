import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const client = { nodeChat: vi.fn(), applyEdit: vi.fn() };
vi.mock("../../services/hypothesisService", () => ({
  get hypothesisClient() { return client; },
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

import { NodeChatPanel } from "./NodeChatPanel";

afterEach(() => vi.clearAllMocks());

describe("NodeChatPanel", () => {
  it("sends a message, shows reply + edit, accepts", async () => {
    client.nodeChat.mockResolvedValue({ reply: "Renaming.", proposed_edit: { op: "set_label", node_id: "n1", label: "ErbB1" } });
    client.applyEdit.mockResolvedValue({ id: "g1", query: "q", nodes: [], edges: [] });
    const onApplied = vi.fn();
    render(<NodeChatPanel graphId="g1" nodeId="n1" onApplied={onApplied} />);

    fireEvent.change(screen.getByLabelText(/message/i), { target: { value: "rename" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));
    await waitFor(() => expect(screen.getByText("Renaming.")).toBeInTheDocument());
    expect(screen.getByText(/proposed change/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /accept/i }));
    await waitFor(() => expect(onApplied).toHaveBeenCalled());
    expect(client.applyEdit).toHaveBeenCalledWith("g1", { op: "set_label", node_id: "n1", label: "ErbB1" });
  });
});
