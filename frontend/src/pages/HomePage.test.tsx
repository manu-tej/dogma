import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { HomePage } from "./HomePage";

// HomePage's useHistory fetches the graph list; stub fetch so it resolves empty.
beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve([]) } as Response)),
  );
});

describe("HomePage", () => {
  it("renders the hero and capability cards", () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );
    expect(screen.getByText("What do you want to investigate?")).toBeInTheDocument();
    // Capability cards (everything except Home) — anchor to the label, since
    // seeded example chats can also contain words like "datasets".
    expect(screen.getByRole("link", { name: /^Canvas/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Pipelines/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Datasets/i })).toBeInTheDocument();
  });
});
