import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { QueryBar } from "./QueryBar";

describe("QueryBar", () => {
  it("prefills from initialValue and submits it", () => {
    const onSubmit = vi.fn();
    render(<QueryBar loading={false} onSubmit={onSubmit} initialValue="seeded question" />);
    const input = screen.getByLabelText(/hypothesis query/i) as HTMLInputElement;
    expect(input.value).toBe("seeded question");
    fireEvent.click(screen.getByRole("button", { name: /investigate/i }));
    expect(onSubmit).toHaveBeenCalledWith("seeded question");
  });

  it("disables submit while loading", () => {
    render(<QueryBar loading={true} onSubmit={vi.fn()} initialValue="x" />);
    // When loading, the button shows a spinner (no text), so query without name restriction.
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("disables submit when empty", () => {
    render(<QueryBar loading={false} onSubmit={vi.fn()} />);
    expect(screen.getByRole("button", { name: /investigate/i })).toBeDisabled();
  });


});

describe("QueryBar re-roll", () => {
  it("renders a Re-roll button and calls onReroll when clicked", () => {
    const onReroll = vi.fn();
    render(<QueryBar loading={false} onSubmit={() => {}} onReroll={onReroll} />);
    const btn = screen.getByRole("button", { name: /re-roll/i });
    fireEvent.click(btn);
    expect(onReroll).toHaveBeenCalledTimes(1);
  });

  it("does not render Re-roll when onReroll is absent", () => {
    render(<QueryBar loading={false} onSubmit={() => {}} />);
    expect(screen.queryByRole("button", { name: /re-roll/i })).toBeNull();
  });
});
