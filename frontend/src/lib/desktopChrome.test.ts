import { beforeEach, describe, expect, it } from "vitest";

import {
  CUSTOM_TITLEBAR_CLASS,
  MAX_TITLEBAR_INSET,
  TITLEBAR_INSET_PROPERTY,
  applyDesktopChrome,
  initDesktopChrome,
  normalizeTitlebarInset,
} from "./desktopChrome";

describe("normalizeTitlebarInset", () => {
  it("passes through a sensible pixel count", () => {
    expect(normalizeTitlebarInset(40)).toBe(40);
  });

  it("treats anything non-numeric as no chrome to avoid", () => {
    for (const value of [undefined, null, "40", "40px", {}, [], NaN]) {
      expect(normalizeTitlebarInset(value)).toBe(0);
    }
  });

  it("treats zero and negatives as no chrome to avoid", () => {
    expect(normalizeTitlebarInset(0)).toBe(0);
    expect(normalizeTitlebarInset(-40)).toBe(0);
  });

  it("rejects non-finite numbers, which calc() would not survive", () => {
    expect(normalizeTitlebarInset(Infinity)).toBe(0);
    expect(normalizeTitlebarInset(-Infinity)).toBe(0);
  });

  it("clamps absurd values so the header cannot be pushed off screen", () => {
    expect(normalizeTitlebarInset(10_000)).toBe(MAX_TITLEBAR_INSET);
  });

  it("rounds fractional pixels", () => {
    expect(normalizeTitlebarInset(39.6)).toBe(40);
  });
});

describe("applyDesktopChrome", () => {
  let root: HTMLElement;

  beforeEach(() => {
    root = document.createElement("html");
  });

  it("publishes the inset and marks the document", () => {
    expect(applyDesktopChrome(root, 40)).toBe(40);
    expect(root.style.getPropertyValue(TITLEBAR_INSET_PROPERTY)).toBe("40px");
    expect(root.classList.contains(CUSTOM_TITLEBAR_CLASS)).toBe(true);
  });

  it("leaves the document untouched when there is no chrome to avoid", () => {
    // The web build must be indistinguishable from before this existed: no
    // class, and no inline property that could beat the 0px stylesheet default.
    expect(applyDesktopChrome(root, 0)).toBe(0);
    expect(root.getAttribute("style")).toBe(null);
    expect(root.classList.contains(CUSTOM_TITLEBAR_CLASS)).toBe(false);
  });

  it("leaves the document untouched for a garbage value", () => {
    expect(applyDesktopChrome(root, "tall")).toBe(0);
    expect(root.classList.contains(CUSTOM_TITLEBAR_CLASS)).toBe(false);
  });

  it("applies the clamped value, not the raw one", () => {
    expect(applyDesktopChrome(root, 10_000)).toBe(MAX_TITLEBAR_INSET);
    expect(root.style.getPropertyValue(TITLEBAR_INSET_PROPERTY)).toBe(
      `${MAX_TITLEBAR_INSET}px`,
    );
  });
});

describe("initDesktopChrome", () => {
  beforeEach(() => {
    delete (window as { dogma?: unknown }).dogma;
    document.documentElement.classList.remove(CUSTOM_TITLEBAR_CLASS);
    document.documentElement.style.removeProperty(TITLEBAR_INSET_PROPERTY);
  });

  it("does nothing in a browser, where the bridge is absent", () => {
    expect(initDesktopChrome()).toBe(0);
    expect(
      document.documentElement.classList.contains(CUSTOM_TITLEBAR_CLASS),
    ).toBe(false);
  });

  it("reads the inset off the preload bridge", () => {
    (window as { dogma?: unknown }).dogma = { titlebarInset: 40 };
    expect(initDesktopChrome()).toBe(40);
    expect(
      document.documentElement.style.getPropertyValue(TITLEBAR_INSET_PROPERTY),
    ).toBe("40px");
  });

  it("does nothing when the shell reports a native title bar", () => {
    // What every non-macOS desktop platform sends.
    (window as { dogma?: unknown }).dogma = { titlebarInset: 0 };
    expect(initDesktopChrome()).toBe(0);
    expect(
      document.documentElement.classList.contains(CUSTOM_TITLEBAR_CLASS),
    ).toBe(false);
  });
});
