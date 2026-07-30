import { describe, expect, it } from "vitest";

import { DEFAULT_API_BASE_URL, resolveApiBaseUrl } from "./apiBaseUrl";

describe("resolveApiBaseUrl", () => {
  it("falls back to the local development default", () => {
    expect(resolveApiBaseUrl(null, {})).toBe(DEFAULT_API_BASE_URL);
  });

  it("prefers the desktop runtime value over build-time env", () => {
    expect(
      resolveApiBaseUrl("http://127.0.0.1:8000", {
        VITE_API_URL: "http://example.test",
        VITE_GEO_API_URL: "http://other.test",
      }),
    ).toBe("http://127.0.0.1:8000");
  });

  it("prefers VITE_API_URL over the legacy VITE_GEO_API_URL", () => {
    expect(
      resolveApiBaseUrl(null, {
        VITE_API_URL: "http://new.test",
        VITE_GEO_API_URL: "http://legacy.test",
      }),
    ).toBe("http://new.test");
  });

  it("still honours VITE_GEO_API_URL on its own", () => {
    expect(resolveApiBaseUrl(null, { VITE_GEO_API_URL: "http://legacy.test" })).toBe(
      "http://legacy.test",
    );
  });

  it("ignores blank and whitespace-only values", () => {
    expect(
      resolveApiBaseUrl("   ", { VITE_API_URL: "", VITE_GEO_API_URL: "  " }),
    ).toBe(DEFAULT_API_BASE_URL);
  });

  it("strips trailing slashes so appended paths stay well formed", () => {
    expect(resolveApiBaseUrl("http://127.0.0.1:8000///")).toBe(
      "http://127.0.0.1:8000",
    );
  });

  it("ignores non-string env values", () => {
    expect(
      resolveApiBaseUrl(null, { VITE_API_URL: true, VITE_GEO_API_URL: undefined }),
    ).toBe(DEFAULT_API_BASE_URL);
  });
});
