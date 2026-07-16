import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { NavRail } from "./NavRail";

function renderRail(initialPath = "/") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <NavRail />
    </MemoryRouter>,
  );
}

describe("NavRail", () => {
  beforeEach(() => localStorage.removeItem("dogma:navCollapsed"));

  it("renders the dogma brand", () => {
    renderRail();
    expect(screen.getAllByLabelText("dogma").length).toBeGreaterThan(0);
  });

  it("renders nav links with correct hrefs", () => {
    renderRail();
    expect(screen.getByRole("link", { name: /Canvas/i })).toHaveAttribute("href", "/canvas");
    expect(screen.getByRole("link", { name: /Pipelines/i })).toHaveAttribute("href", "/pipelines");
    expect(screen.getByRole("link", { name: /Settings/i })).toHaveAttribute("href", "/settings");
  });

  it("collapses and expands via the footer button", () => {
    renderRail();
    const nav = screen.getByRole("navigation", { name: /Primary/i });
    expect(nav).toHaveAttribute("data-collapsed", "false");
    fireEvent.click(screen.getByRole("button", { name: /Collapse sidebar/i }));
    expect(nav).toHaveAttribute("data-collapsed", "true");
    fireEvent.click(screen.getByRole("button", { name: /Expand sidebar/i }));
    expect(nav).toHaveAttribute("data-collapsed", "false");
  });
});
