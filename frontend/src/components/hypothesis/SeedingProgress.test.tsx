import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SeedingProgress } from "./SeedingProgress";

describe("SeedingProgress", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders the "Sketching a causal graph…" heading', () => {
    render(<SeedingProgress />);
    expect(screen.getByText(/sketching a causal graph/i)).toBeInTheDocument();
  });

  it("shows an initial 0:00 timer", () => {
    render(<SeedingProgress />);
    expect(screen.getByText("0:00")).toBeInTheDocument();
  });

  it("advances the elapsed timer to 0:03 after 3 seconds", async () => {
    render(<SeedingProgress />);
    expect(screen.getByText("0:00")).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(3000);
    });

    expect(screen.getByText("0:03")).toBeInTheDocument();
  });

  it("shows at least one staged hint", () => {
    render(<SeedingProgress />);
    // One of the known staged hints should be visible initially
    const hints = [
      /parsing your question/i,
      /proposing entities/i,
      /grounding to ontologies/i,
    ];
    const found = hints.some((h) => screen.queryByText(h) !== null);
    expect(found).toBe(true);
  });

  it("advances through staged hints over time", async () => {
    render(<SeedingProgress />);
    // First hint visible at t=0
    expect(screen.getByText(/parsing your question/i)).toBeInTheDocument();

    // After ~10s the second hint should appear
    await act(async () => {
      vi.advanceTimersByTime(10000);
    });
    expect(screen.getByText(/proposing entities/i)).toBeInTheDocument();
  });

  it("accepts a startedAt prop to control elapsed calculation", async () => {
    // startedAt 5 seconds ago
    const startedAt = Date.now() - 5000;
    render(<SeedingProgress startedAt={startedAt} />);

    // Advance by 1 tick so the interval fires
    await act(async () => {
      vi.advanceTimersByTime(1000);
    });

    // Timer should reflect at least 6s elapsed (5s ago + 1s tick)
    const timerEl = screen.getByText(/\d:\d\d/);
    expect(timerEl).toBeInTheDocument();
    const [mins, secs] = timerEl.textContent!.split(":").map(Number);
    expect(mins * 60 + secs).toBeGreaterThanOrEqual(6);
  });

  it("shows the large-model disclaimer", () => {
    render(<SeedingProgress />);
    expect(screen.getByText(/large models take/i)).toBeInTheDocument();
  });
});
