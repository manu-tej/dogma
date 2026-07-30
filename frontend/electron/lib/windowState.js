"use strict";

/**
 * Window bounds persistence.
 *
 * Restoring saved bounds blindly is a classic way to lose a window: unplug the
 * external display the app was last closed on and it reopens at coordinates no
 * screen covers. `sanitizeBounds` keeps a remembered position only when it is
 * still meaningfully visible.
 */

const DEFAULT_BOUNDS = { width: 1440, height: 900 };
const MIN_WIDTH = 900;
const MIN_HEIGHT = 600;

/** A window must overlap a display by at least this much to be reachable. */
const MIN_VISIBLE = 96;

function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function overlaps(bounds, display) {
  const overlapX =
    Math.min(bounds.x + bounds.width, display.x + display.width) -
    Math.max(bounds.x, display.x);
  const overlapY =
    Math.min(bounds.y + bounds.height, display.y + display.height) -
    Math.max(bounds.y, display.y);
  return overlapX >= MIN_VISIBLE && overlapY >= MIN_VISIBLE;
}

/**
 * @param {unknown} saved Previously persisted bounds; may be anything.
 * @param {Array<{x:number,y:number,width:number,height:number}>} displays
 *   Work areas of the currently attached displays.
 * @returns {{width:number,height:number,x?:number,y?:number}}
 *   Bounds safe to hand to BrowserWindow. `x`/`y` are omitted when the saved
 *   position is unusable, which lets Electron center the window.
 */
function sanitizeBounds(saved, displays) {
  if (saved === null || typeof saved !== "object") {
    return { ...DEFAULT_BOUNDS };
  }

  const largestWidth = displays.reduce((max, d) => Math.max(max, d.width), 0);
  const largestHeight = displays.reduce((max, d) => Math.max(max, d.height), 0);

  const width = isFiniteNumber(saved.width)
    ? Math.max(MIN_WIDTH, Math.round(saved.width))
    : DEFAULT_BOUNDS.width;
  const height = isFiniteNumber(saved.height)
    ? Math.max(MIN_HEIGHT, Math.round(saved.height))
    : DEFAULT_BOUNDS.height;

  const result = {
    width: largestWidth > 0 ? Math.min(width, largestWidth) : width,
    height: largestHeight > 0 ? Math.min(height, largestHeight) : height,
  };

  if (!isFiniteNumber(saved.x) || !isFiniteNumber(saved.y)) {
    return result;
  }

  const positioned = {
    x: Math.round(saved.x),
    y: Math.round(saved.y),
    width: result.width,
    height: result.height,
  };

  if (displays.some((display) => overlaps(positioned, display))) {
    result.x = positioned.x;
    result.y = positioned.y;
  }

  return result;
}

module.exports = {
  DEFAULT_BOUNDS,
  MIN_WIDTH,
  MIN_HEIGHT,
  MIN_VISIBLE,
  sanitizeBounds,
};
