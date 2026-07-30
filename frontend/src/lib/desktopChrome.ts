/**
 * Teaches the shared app shell about desktop window chrome.
 *
 * On macOS the Electron shell hides the title bar and draws the renderer under
 * it, which means the app's own header would collide with the traffic lights.
 * The shell reports how tall a strip to keep clear; this module publishes that
 * as the `--titlebar-inset` custom property and marks the document so the
 * drag-region rules in `index.css` switch on.
 *
 * One `frontend/build` artifact serves both the web app and the desktop app, so
 * this has to be a *runtime* decision. In a browser `window.dogma` is undefined,
 * the inset stays at its 0px default, and no class is added — the web layout is
 * byte-for-byte the one that shipped before any of this existed.
 */

/**
 * Present on <html> only when the window has no native title bar, which is the
 * one case where the app must supply its own drag regions. Windows and Linux
 * keep ordinary chrome and therefore never get this class.
 */
export const CUSTOM_TITLEBAR_CLASS = "dogma-custom-titlebar";

export const TITLEBAR_INSET_PROPERTY = "--titlebar-inset";

/**
 * Ceiling on the reserved strip. The value crosses a process boundary as JSON,
 * and a nonsense number would push the entire header off screen with no way for
 * the user to recover.
 */
export const MAX_TITLEBAR_INSET = 120;

/**
 * Coerce whatever arrived over the bridge into a usable pixel count.
 *
 * @returns 0 for anything absent, negative, non-finite or not a number — all of
 *   which mean "this window has normal chrome, reserve nothing".
 */
export function normalizeTitlebarInset(value: unknown): number {
  if (typeof value !== "number") return 0;
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Math.min(Math.round(value), MAX_TITLEBAR_INSET);
}

/**
 * Pure DOM application, exported for tests.
 *
 * @returns The inset actually applied, in px.
 */
export function applyDesktopChrome(root: HTMLElement, inset: unknown): number {
  const normalized = normalizeTitlebarInset(inset);
  if (normalized === 0) return 0;
  root.classList.add(CUSTOM_TITLEBAR_CLASS);
  root.style.setProperty(TITLEBAR_INSET_PROPERTY, `${normalized}px`);
  return normalized;
}

/**
 * Read the inset off the preload bridge and apply it.
 *
 * Called from `main.tsx` before the first render so the very first paint already
 * has the strip reserved — reserving it in an effect would show one frame of the
 * logo sitting under the traffic lights.
 */
export function initDesktopChrome(): number {
  if (typeof document === "undefined") return 0;
  return applyDesktopChrome(
    document.documentElement,
    typeof window === "undefined" ? 0 : window.dogma?.titlebarInset,
  );
}
