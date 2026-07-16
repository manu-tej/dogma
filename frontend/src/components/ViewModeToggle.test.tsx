import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ViewModeToggle } from "./ViewModeToggle";

describe("ViewModeToggle", () => {
  it("marks the active view and switches on click", () => {
    const onSelect = vi.fn();
    render(<ViewModeToggle active="canvas" onSelect={onSelect} />);

    const canvas = screen.getByRole("button", { name: /canvas/i });
    const chat = screen.getByRole("button", { name: /chat/i });
    expect(canvas).toHaveAttribute("aria-pressed", "true");
    expect(chat).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(chat);
    expect(onSelect).toHaveBeenCalledWith("chat");

    // Clicking the already-active view still reports it (idempotent).
    fireEvent.click(canvas);
    expect(onSelect).toHaveBeenCalledWith("canvas");
  });
});
