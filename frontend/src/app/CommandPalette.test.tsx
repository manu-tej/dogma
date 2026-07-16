import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { CommandPalette } from "./CommandPalette";

beforeEach(() => {
  localStorage.clear();
  // useHistory fetches the graph list when the palette opens; return none.
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response)),
  );
});

function renderPalette(onOpenChange = vi.fn()) {
  render(
    <MemoryRouter>
      <CommandPalette open onOpenChange={onOpenChange} />
    </MemoryRouter>,
  );
  return onOpenChange;
}

describe("CommandPalette", () => {
  it("lists every destination when open", () => {
    renderPalette();
    expect(screen.getByText("Datasets")).toBeInTheDocument();
    expect(screen.getByText("Canvas")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("offers quick actions", () => {
    renderPalette();
    expect(screen.getByText("New canvas")).toBeInTheDocument();
    expect(screen.getByText("New chat")).toBeInTheDocument();
  });

  it("surfaces recent conversations as jump targets", () => {
    localStorage.setItem(
      "antonConversations",
      JSON.stringify([
        {
          id: "saved-1",
          title: "My saved dataset search",
          timestamp: "2026-07-15T00:00:00.000Z",
        },
      ]),
    );
    renderPalette();
    expect(screen.getByText("My saved dataset search")).toBeInTheDocument();
  });

  it("closes after selecting a destination", () => {
    const onOpenChange = renderPalette();
    fireEvent.click(screen.getByText("Methods"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
