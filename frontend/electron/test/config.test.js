"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");

const {
  API_BASE_URL,
  API_PROXY_PREFIX,
  APP_ORIGIN,
  APP_URL,
  CONFIG_ARG_PREFIX,
  RENDERER_API_BASE_URL,
  TITLEBAR_INSET,
  TRAFFIC_LIGHT_POSITION,
  TRAFFIC_LIGHT_SIZE,
  isProxyPath,
  parseConfigArg,
  upstreamUrl,
} = require("../lib/config");

describe("config", () => {
  it("addresses the backend over the IPv4 loopback", () => {
    // uvicorn binds 127.0.0.1; "localhost" can resolve to ::1 first and fail.
    assert.equal(API_BASE_URL, "http://127.0.0.1:8000");
  });

  it("exposes a stable origin the backend allowlist can name", () => {
    assert.equal(APP_ORIGIN, "app://dogma");
    assert.equal(APP_URL, "app://dogma/");
  });
});

describe("isProxyPath", () => {
  it("matches the prefix and everything under it", () => {
    assert.equal(isProxyPath("/api"), true);
    assert.equal(isProxyPath("/api/"), true);
    assert.equal(isProxyPath("/api/geo/search"), true);
  });

  it("does not match app routes that merely start with the same letters", () => {
    // A route named /apiary must still be served as the SPA, not proxied.
    assert.equal(isProxyPath("/apiary"), false);
    assert.equal(isProxyPath("/datasets"), false);
    assert.equal(isProxyPath("/"), false);
  });
});

describe("upstreamUrl", () => {
  const UPSTREAM = "http://127.0.0.1:8000";

  it("keeps the renderer base pointing at the proxy", () => {
    assert.equal(RENDERER_API_BASE_URL, `${APP_ORIGIN}${API_PROXY_PREFIX}`);
  });

  it("strips the proxy prefix", () => {
    assert.equal(
      upstreamUrl(UPSTREAM, "app://dogma/api/hypothesis"),
      `${UPSTREAM}/hypothesis`,
    );
    assert.equal(
      upstreamUrl(UPSTREAM, "app://dogma/api/geo/search/stream"),
      `${UPSTREAM}/geo/search/stream`,
    );
  });

  it("preserves the query string", () => {
    assert.equal(
      upstreamUrl(UPSTREAM, "app://dogma/api/geo/search?max_results=10&x=1"),
      `${UPSTREAM}/geo/search?max_results=10&x=1`,
    );
  });

  it("maps a bare prefix to the backend root", () => {
    assert.equal(upstreamUrl(UPSTREAM, "app://dogma/api"), `${UPSTREAM}/`);
  });

  it("tolerates a trailing slash on the upstream base", () => {
    assert.equal(
      upstreamUrl("http://127.0.0.1:8000/", "app://dogma/api/health"),
      `${UPSTREAM}/health`,
    );
  });

  it("returns null for non-proxy paths so they fall through to static files", () => {
    assert.equal(upstreamUrl(UPSTREAM, "app://dogma/datasets"), null);
    assert.equal(upstreamUrl(UPSTREAM, "app://dogma/assets/index.js"), null);
    assert.equal(upstreamUrl(UPSTREAM, "not a url"), null);
  });
});

describe("parseConfigArg", () => {
  it("reads the injected config blob", () => {
    const argv = [
      "electron",
      `${CONFIG_ARG_PREFIX}${JSON.stringify({ apiBaseUrl: "http://127.0.0.1:8000" })}`,
    ];
    assert.deepEqual(parseConfigArg(argv), { apiBaseUrl: "http://127.0.0.1:8000" });
  });

  it("returns an empty object when the argument is absent", () => {
    assert.deepEqual(parseConfigArg(["electron", "--other"]), {});
  });

  it("returns an empty object for malformed JSON rather than throwing", () => {
    assert.deepEqual(parseConfigArg([`${CONFIG_ARG_PREFIX}{not json`]), {});
  });

  it("rejects a non-object payload", () => {
    assert.deepEqual(parseConfigArg([`${CONFIG_ARG_PREFIX}"a string"`]), {});
    assert.deepEqual(parseConfigArg([`${CONFIG_ARG_PREFIX}null`]), {});
  });
});

describe("title bar geometry", () => {
  it("reserves a strip that clears the traffic lights", () => {
    const buttonsEnd = TRAFFIC_LIGHT_POSITION.y + TRAFFIC_LIGHT_SIZE.height;
    assert.ok(
      TITLEBAR_INSET >= buttonsEnd,
      `inset ${TITLEBAR_INSET} must clear buttons ending at ${buttonsEnd}`,
    );
  });

  it("centres the buttons in the reserved strip", () => {
    // Equal space above and below is the whole reason the inset is derived from
    // the position rather than picked by eye.
    const above = TRAFFIC_LIGHT_POSITION.y;
    const below =
      TITLEBAR_INSET - TRAFFIC_LIGHT_POSITION.y - TRAFFIC_LIGHT_SIZE.height;
    assert.equal(above, below);
  });

  it("is a whole number of pixels", () => {
    // It ends up inside a CSS calc(); a fraction would blur the 1px border.
    assert.equal(Number.isInteger(TITLEBAR_INSET), true);
  });

  it("keeps the buttons clear of the collapsed rail's right edge", () => {
    // The collapsed NavRail is w-16 (64px). The buttons run to x=70, so they
    // overhang it — which is exactly why the reserved strip is horizontal-full
    // and vertical, rather than padding the rail from the left. If someone ever
    // narrows the button group inside the rail, the drag strip could shrink to
    // the rail; until then this records why it spans the window.
    const buttonsRight = TRAFFIC_LIGHT_POSITION.x + TRAFFIC_LIGHT_SIZE.width;
    assert.ok(buttonsRight > 64, `buttons end at ${buttonsRight}`);
  });
});
