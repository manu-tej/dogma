import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";

import { AppShell } from "./AppShell";

function renderShell() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<div>HOME CONTENT</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("AppShell", () => {
  it("renders the primary nav, top bar, and routed content", () => {
    renderShell();
    expect(screen.getByRole("navigation", { name: /Primary/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Open command palette/i })).toBeInTheDocument();
    expect(screen.getByText("HOME CONTENT")).toBeInTheDocument();
  });

  it("opens the shortcuts help on '?'", () => {
    renderShell();
    expect(screen.queryByText("Keyboard shortcuts")).not.toBeInTheDocument();
    fireEvent.keyDown(document.body, { key: "?" });
    expect(screen.getByText("Keyboard shortcuts")).toBeInTheDocument();
  });

  it("uses a drawer (menu button), not a persistent rail, on mobile", () => {
    const original = window.innerWidth;
    Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: 500 });
    try {
      renderShell();
      // The persistent rail is replaced by a menu button that opens the drawer.
      expect(screen.getByRole("button", { name: /Open navigation/i })).toBeInTheDocument();
      expect(screen.queryByRole("navigation", { name: /Primary/i })).not.toBeInTheDocument();
    } finally {
      Object.defineProperty(window, "innerWidth", { configurable: true, writable: true, value: original });
    }
  });
});
