"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");

const {
  DEFAULT_BOUNDS,
  MIN_HEIGHT,
  MIN_WIDTH,
  sanitizeBounds,
} = require("../lib/windowState");

const LAPTOP = { x: 0, y: 0, width: 1710, height: 1067 };
const EXTERNAL = { x: 1710, y: 0, width: 2560, height: 1440 };

describe("sanitizeBounds", () => {
  it("returns defaults when nothing is stored", () => {
    assert.deepEqual(sanitizeBounds(null, [LAPTOP]), { ...DEFAULT_BOUNDS });
    assert.deepEqual(sanitizeBounds(undefined, [LAPTOP]), { ...DEFAULT_BOUNDS });
  });

  it("ignores a corrupt state file", () => {
    assert.deepEqual(sanitizeBounds("garbage", [LAPTOP]), { ...DEFAULT_BOUNDS });
    assert.deepEqual(sanitizeBounds(42, [LAPTOP]), { ...DEFAULT_BOUNDS });
  });

  it("restores bounds that are still on screen", () => {
    const saved = { x: 100, y: 80, width: 1200, height: 800 };
    assert.deepEqual(sanitizeBounds(saved, [LAPTOP]), saved);
  });

  it("drops a position on a display that is no longer attached", () => {
    // Saved on the external monitor, reopened on the laptop alone: keeping the
    // position would open the window off screen with no way to reach it.
    const saved = { x: 2000, y: 200, width: 1200, height: 800 };
    const result = sanitizeBounds(saved, [LAPTOP]);
    assert.equal(result.x, undefined);
    assert.equal(result.y, undefined);
    assert.equal(result.width, 1200);
    assert.equal(result.height, 800);
  });

  it("keeps a position that is valid on a secondary display", () => {
    const saved = { x: 2000, y: 200, width: 1200, height: 800 };
    assert.deepEqual(sanitizeBounds(saved, [LAPTOP, EXTERNAL]), saved);
  });

  it("drops a position that only barely clips a display", () => {
    const saved = { x: -1190, y: 40, width: 1200, height: 800 };
    const result = sanitizeBounds(saved, [LAPTOP]);
    assert.equal(result.x, undefined);
  });

  it("enforces minimum dimensions", () => {
    const result = sanitizeBounds({ x: 0, y: 0, width: 120, height: 90 }, [LAPTOP]);
    assert.equal(result.width, MIN_WIDTH);
    assert.equal(result.height, MIN_HEIGHT);
  });

  it("clamps dimensions larger than any display", () => {
    const result = sanitizeBounds({ x: 0, y: 0, width: 99999, height: 99999 }, [LAPTOP]);
    assert.equal(result.width, LAPTOP.width);
    assert.equal(result.height, LAPTOP.height);
  });

  it("ignores non-finite values", () => {
    const result = sanitizeBounds(
      { x: NaN, y: Infinity, width: "1200", height: null },
      [LAPTOP],
    );
    assert.deepEqual(result, { ...DEFAULT_BOUNDS });
  });

  it("rounds fractional bounds", () => {
    const result = sanitizeBounds(
      { x: 10.6, y: 20.4, width: 1200.7, height: 800.2 },
      [LAPTOP],
    );
    assert.deepEqual(result, { x: 11, y: 20, width: 1201, height: 800 });
  });

  it("tolerates having no display information", () => {
    const result = sanitizeBounds({ x: 10, y: 10, width: 1200, height: 800 }, []);
    assert.equal(result.width, 1200);
    assert.equal(result.height, 800);
    // No display can vouch for the position, so it is discarded.
    assert.equal(result.x, undefined);
  });
});
