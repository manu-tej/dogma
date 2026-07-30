"use strict";

const assert = require("node:assert/strict");
const { describe, it } = require("node:test");

const { STRIPPED_VARS, electronEnv } = require("../lib/env");

describe("electronEnv", () => {
  it("strips ELECTRON_RUN_AS_NODE", () => {
    // Inherited from a VS Code / Cursor terminal this makes the Electron binary
    // run as plain Node, and `require("electron")` then returns a path string
    // instead of the API — the app crashes on the first protocol call.
    const env = electronEnv({ ELECTRON_RUN_AS_NODE: "1", PATH: "/usr/bin" });
    assert.equal("ELECTRON_RUN_AS_NODE" in env, false);
    assert.equal(env.PATH, "/usr/bin");
  });

  it("applies overrides", () => {
    const env = electronEnv({ PATH: "/usr/bin" }, { DOGMA_SMOKE: "1" });
    assert.equal(env.DOGMA_SMOKE, "1");
    assert.equal(env.PATH, "/usr/bin");
  });

  it("strips the variables even when supplied as an override", () => {
    const env = electronEnv({}, { ELECTRON_RUN_AS_NODE: "1" });
    assert.equal("ELECTRON_RUN_AS_NODE" in env, false);
  });

  it("does not mutate the source environment", () => {
    const base = { ELECTRON_RUN_AS_NODE: "1" };
    electronEnv(base);
    assert.equal(base.ELECTRON_RUN_AS_NODE, "1");
  });

  it("names at least the known breaking variable", () => {
    assert.ok(STRIPPED_VARS.includes("ELECTRON_RUN_AS_NODE"));
  });
});
