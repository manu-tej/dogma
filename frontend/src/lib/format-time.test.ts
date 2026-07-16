import { describe, expect, it } from "vitest";

import { formatTimestamp } from "./format-time";

// Fixed reference point: 2026-06-11T20:00:00Z
const NOW = new Date("2026-06-11T20:00:00Z");

describe("formatTimestamp", () => {
  it("returns 'just now' for timestamps less than 60 seconds ago", () => {
    const ts = new Date(NOW.getTime() - 30_000).toISOString();
    expect(formatTimestamp(ts, NOW)).toBe("just now");
  });

  it("returns 'just now' for 0 seconds ago", () => {
    expect(formatTimestamp(NOW.toISOString(), NOW)).toBe("just now");
  });

  it("returns 'Nm ago' for timestamps between 1 and 59 minutes ago", () => {
    const ts = new Date(NOW.getTime() - 5 * 60_000).toISOString();
    expect(formatTimestamp(ts, NOW)).toBe("5m ago");
  });

  it("returns '1m ago' for exactly 60 seconds ago", () => {
    const ts = new Date(NOW.getTime() - 60_000).toISOString();
    expect(formatTimestamp(ts, NOW)).toBe("1m ago");
  });

  it("returns 'Nh ago' for timestamps between 1 and 23 hours ago", () => {
    const ts = new Date(NOW.getTime() - 3 * 3600_000).toISOString();
    expect(formatTimestamp(ts, NOW)).toBe("3h ago");
  });

  it("returns '1h ago' for exactly 60 minutes ago", () => {
    const ts = new Date(NOW.getTime() - 60 * 60_000).toISOString();
    expect(formatTimestamp(ts, NOW)).toBe("1h ago");
  });

  it("returns 'Nd ago' for timestamps between 1 and 6 days ago", () => {
    const ts = new Date(NOW.getTime() - 3 * 86_400_000).toISOString();
    expect(formatTimestamp(ts, NOW)).toBe("3d ago");
  });

  it("returns '1d ago' for exactly 24 hours ago", () => {
    const ts = new Date(NOW.getTime() - 24 * 3600_000).toISOString();
    expect(formatTimestamp(ts, NOW)).toBe("1d ago");
  });

  it("returns an absolute locale string for timestamps older than 7 days", () => {
    const ts = new Date(NOW.getTime() - 8 * 86_400_000).toISOString();
    const result = formatTimestamp(ts, NOW);
    // Should contain a month abbreviation, not a relative form
    expect(result).not.toMatch(/ago|just now/);
    expect(result.length).toBeGreaterThan(4);
  });

  it("handles ISO strings with microseconds and timezone offset", () => {
    // Microseconds in fractional seconds + tz offset — must not crash
    const ts = "2026-06-10T15:30:00.123456+00:00";
    const nowRef = new Date("2026-06-10T15:30:30Z");
    expect(formatTimestamp(ts, nowRef)).toBe("just now");
  });

  it("passes through invalid strings unchanged", () => {
    expect(formatTimestamp("not-a-date", NOW)).toBe("not-a-date");
    expect(formatTimestamp("", NOW)).toBe("");
  });
});
