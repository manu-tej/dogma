import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { ShortcutsHelp } from "./ShortcutsHelp";

describe("ShortcutsHelp", () => {
  it("lists the app shortcuts when open", () => {
    render(<ShortcutsHelp open onOpenChange={vi.fn()} />);
    expect(screen.getByText("Keyboard shortcuts")).toBeInTheDocument();
    expect(screen.getByText(/command palette/i)).toBeInTheDocument();
    expect(screen.getByText(/Collapse or expand the sidebar/i)).toBeInTheDocument();
  });

  it("renders nothing when closed", () => {
    render(<ShortcutsHelp open={false} onOpenChange={vi.fn()} />);
    expect(screen.queryByText("Keyboard shortcuts")).not.toBeInTheDocument();
  });
});
