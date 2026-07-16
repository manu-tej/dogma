import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { QueryEntryLanding } from "./QueryEntryLanding";

describe("QueryEntryLanding", () => {
  it("calls onStart when an example query is clicked", () => {
    const onStart = vi.fn();
    render(<QueryEntryLanding onStart={onStart} />);
    expect(screen.getByText(/ask a causal question/i)).toBeInTheDocument();
    fireEvent.click(screen.getAllByTestId("example-query")[0]);
    expect(onStart).toHaveBeenCalledTimes(1);
    expect(typeof onStart.mock.calls[0][0]).toBe("string");
  });
});
