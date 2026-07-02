"use strict";

const assert = require("assert");
const {
  DEFAULT_QURATION_CANVAS_URL,
  buildQurationCanvasUrl,
  buildQurationGraphUrl,
  normalizeQurationCanvasUrl
} = require("../src/qurationCanvasLink");

assert.strictEqual(DEFAULT_QURATION_CANVAS_URL, "http://localhost:3000/canvas");
assert.strictEqual(normalizeQurationCanvasUrl("http://localhost:3000").toString(), "http://localhost:3000/canvas");
assert.strictEqual(normalizeQurationCanvasUrl("http://localhost:5173/canvas").toString(), "http://localhost:5173/canvas");
assert.strictEqual(
  buildQurationCanvasUrl("http://localhost:3000/canvas", "Does condition contrast affect transcript abundance?"),
  "http://localhost:3000/canvas?q=Does+condition+contrast+affect+transcript+abundance%3F"
);
assert.strictEqual(
  buildQurationCanvasUrl("http://localhost:3000/canvas?theme=dark", "  "),
  "http://localhost:3000/canvas?theme=dark"
);
assert.strictEqual(
  buildQurationCanvasUrl("", "RNA-seq differential expression"),
  "http://localhost:3000/canvas?q=RNA-seq+differential+expression"
);
assert.strictEqual(
  buildQurationGraphUrl("http://localhost:3000/canvas", "graph-123"),
  "http://localhost:3000/canvas/graph-123"
);
assert.strictEqual(
  buildQurationGraphUrl("http://localhost:3000/canvas?theme=dark", "graph 123"),
  "http://localhost:3000/canvas/graph%20123"
);
assert.strictEqual(buildQurationGraphUrl("http://localhost:3000/canvas", "  "), null);

console.log("quration canvas link tests passed");
