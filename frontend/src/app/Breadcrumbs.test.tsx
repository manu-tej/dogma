import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { Breadcrumbs } from "./Breadcrumbs";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Breadcrumbs />
    </MemoryRouter>,
  );
}

describe("Breadcrumbs", () => {
  it("shows the destination label", () => {
    renderAt("/pipelines");
    expect(screen.getByRole("link", { name: "Pipelines" })).toHaveAttribute("href", "/pipelines");
  });

  it("appends a trailing segment as a leaf crumb", () => {
    renderAt("/canvas/abc123");
    expect(screen.getByRole("link", { name: "Canvas" })).toBeInTheDocument();
    expect(screen.getByText("abc123")).toBeInTheDocument();
  });

  it("falls back to the brand for an unknown route", () => {
    renderAt("/totally-unknown");
    expect(screen.getByText("dogma")).toBeInTheDocument();
  });
});
