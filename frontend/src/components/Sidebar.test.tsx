import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Sidebar } from "./Sidebar";

const baseProps = {
  selectedDataset: null,
  onSelectDataset: vi.fn(),
  isCollapsed: false,
  onToggleCollapse: vi.fn(),
  conversations: [
    { id: "c1", title: "Chat about EGFR", timestamp: new Date("2026-06-13T00:00:00Z") },
  ],
  currentConversationId: null,
  onSelectConversation: vi.fn(),
  onNewConversation: vi.fn(),
};

afterEach(() => vi.restoreAllMocks());

describe("Sidebar delete", () => {
  it("deletes a conversation via its trash button without selecting it", () => {
    const onDeleteConversation = vi.fn();
    const onSelectConversation = vi.fn();
    render(
      <Sidebar
        {...baseProps}
        onSelectConversation={onSelectConversation}
        onDeleteConversation={onDeleteConversation}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /delete conversation/i }));
    expect(onDeleteConversation).toHaveBeenCalledWith("c1");
    expect(onSelectConversation).not.toHaveBeenCalled(); // stopPropagation kept the row from opening
  });

  it("clears all conversations after confirm", () => {
    const onClearConversations = vi.fn();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<Sidebar {...baseProps} onClearConversations={onClearConversations} />);
    fireEvent.click(screen.getByRole("button", { name: /clear all/i }));
    expect(confirmSpy).toHaveBeenCalled();
    expect(onClearConversations).toHaveBeenCalled();
  });

  it("does not clear when confirm is dismissed", () => {
    const onClearConversations = vi.fn();
    vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<Sidebar {...baseProps} onClearConversations={onClearConversations} />);
    fireEvent.click(screen.getByRole("button", { name: /clear all/i }));
    expect(onClearConversations).not.toHaveBeenCalled();
  });
});
