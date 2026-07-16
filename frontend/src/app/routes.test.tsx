import { describe, it, expect } from "vitest";
import { NAV_ITEMS, SETTINGS_ITEM, ALL_DESTINATIONS, findNavItem } from "./routes";

describe("routes config", () => {
  it("exposes the expected primary destinations", () => {
    const paths = NAV_ITEMS.map((i) => i.path);
    expect(paths).toEqual([
      "/",
      "/canvas",
      "/chat",
      "/datasets",
      "/methods",
      "/pipelines",
      "/interpretation",
    ]);
  });

  it("includes settings in the full destination list", () => {
    expect(ALL_DESTINATIONS).toContain(SETTINGS_ITEM);
    expect(ALL_DESTINATIONS).toHaveLength(NAV_ITEMS.length + 1);
  });

  it("every destination has a label, description, and icon", () => {
    for (const item of ALL_DESTINATIONS) {
      expect(item.label).toBeTruthy();
      expect(item.description).toBeTruthy();
      expect(item.icon).toBeTruthy();
    }
  });

  describe("findNavItem", () => {
    it("resolves an exact root match only for the index", () => {
      expect(findNavItem("/")?.label).toBe("Home");
    });

    it("resolves a sub-route to its owning destination", () => {
      expect(findNavItem("/canvas/abc123")?.label).toBe("Canvas");
      expect(findNavItem("/chat/conv-9")?.label).toBe("Chat");
    });

    it("does not match the index for a non-root path", () => {
      expect(findNavItem("/pipelines")?.label).toBe("Pipelines");
    });

    it("returns undefined for an unknown path", () => {
      expect(findNavItem("/nope")).toBeUndefined();
    });
  });
});
