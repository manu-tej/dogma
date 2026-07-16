import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const client = { edgeChat: vi.fn(), applyEdit: vi.fn() };
vi.mock("../../services/hypothesisService", () => ({
  get hypothesisClient() { return client; },
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn() } }));

import { EdgeChatPanel } from "./EdgeChatPanel";

afterEach(() => vi.clearAllMocks());

describe("EdgeChatPanel", () => {
  it("sends a message and shows the reply + proposed edit, then accepts", async () => {
    client.edgeChat.mockResolvedValue({ reply: "Let's flip it.", proposed_edit: { op: "flip_edge", edge_id: "e1" } });
    client.applyEdit.mockResolvedValue({ id: "g1", query: "q", nodes: [], edges: [] });
    const onApplied = vi.fn();
    render(<EdgeChatPanel graphId="g1" edgeId="e1" onApplied={onApplied} />);

    fireEvent.change(screen.getByLabelText(/message/i), { target: { value: "flip it" } });
    fireEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() => expect(screen.getByText("Let's flip it.")).toBeInTheDocument());
    expect(screen.getByText(/proposed change/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /accept/i }));
    await waitFor(() => expect(onApplied).toHaveBeenCalled());
    expect(client.applyEdit).toHaveBeenCalledWith("g1", { op: "flip_edge", edge_id: "e1" });
  });
});
