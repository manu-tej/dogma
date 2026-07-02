"use strict";

const DEFAULT_QURATION_CANVAS_URL = "http://localhost:3000/canvas";

function normalizeQurationCanvasUrl(baseUrl) {
  const raw = String(baseUrl || DEFAULT_QURATION_CANVAS_URL).trim() || DEFAULT_QURATION_CANVAS_URL;
  const url = new URL(raw);
  if (!url.pathname || url.pathname === "/") {
    url.pathname = "/canvas";
  }
  return url;
}

function buildQurationCanvasUrl(baseUrl, query) {
  const url = normalizeQurationCanvasUrl(baseUrl);
  const text = String(query || "").trim();
  if (text) {
    url.searchParams.set("q", text);
  }
  return url.toString();
}

function buildQurationGraphUrl(baseUrl, graphId) {
  const id = String(graphId || "").trim();
  if (!id) return null;
  const url = normalizeQurationCanvasUrl(baseUrl);
  const basePath = url.pathname.replace(/\/$/, "");
  url.pathname = `${basePath}/${encodeURIComponent(id)}`;
  url.search = "";
  url.hash = "";
  return url.toString();
}

module.exports = {
  DEFAULT_QURATION_CANVAS_URL,
  buildQurationCanvasUrl,
  buildQurationGraphUrl,
  normalizeQurationCanvasUrl
};
