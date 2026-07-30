"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");
const { describe, it } = require("node:test");

const {
  REPO_ROOT_ENV_VAR,
  describeAttempts,
  looksLikeRepo,
  resolveRepoRoot,
} = require("../lib/repoRoot");

/** A probe that treats the given directories as real Dogma checkouts. */
function repoAt(...roots) {
  const valid = new Set();
  for (const root of roots) {
    valid.add(path.join(root, "pyproject.toml"));
    valid.add(path.join(root, "frontend", "package.json"));
  }
  return (p) => valid.has(p);
}

const REPO = "/Users/dev/dogma";
const OTHER = "/Volumes/work/dogma";
const BUNDLE = "/Applications/dogma.app/Contents/Resources";

describe("looksLikeRepo", () => {
  it("accepts a directory with both markers", () => {
    assert.equal(looksLikeRepo(REPO, repoAt(REPO)), true);
  });

  it("rejects a directory missing a marker", () => {
    const onlyPyproject = (p) => p === path.join(REPO, "pyproject.toml");
    assert.equal(looksLikeRepo(REPO, onlyPyproject), false);
  });

  it("rejects the inside of an app bundle", () => {
    // The whole reason validation exists: pyproject.toml is never bundled, so a
    // packaged app's derived path cannot masquerade as a checkout.
    assert.equal(looksLikeRepo(BUNDLE, repoAt(REPO)), false);
  });

  it("rejects empty, non-string and relative values", () => {
    const probe = repoAt(REPO);
    for (const value of ["", null, undefined, 42, {}]) {
      assert.equal(looksLikeRepo(value, probe), false);
    }
    assert.equal(looksLikeRepo("./dogma", probe), false);
  });
});

describe("resolveRepoRoot", () => {
  it("uses the derived path when running from the checkout", () => {
    const result = resolveRepoRoot({
      derived: REPO,
      fileExists: repoAt(REPO),
    });
    assert.equal(result.root, REPO);
    assert.equal(result.source, "derived");
  });

  it("falls through to the baked path when packaged", () => {
    // Packaged: derived points inside the bundle and fails validation.
    const result = resolveRepoRoot({
      derived: BUNDLE,
      baked: REPO,
      fileExists: repoAt(REPO),
    });
    assert.equal(result.root, REPO);
    assert.equal(result.source, "baked");
  });

  it("lets the environment override a valid derived path", () => {
    const result = resolveRepoRoot({
      envValue: OTHER,
      derived: REPO,
      fileExists: repoAt(REPO, OTHER),
    });
    assert.equal(result.root, OTHER);
    assert.equal(result.source, "env");
  });

  it("ignores a stale override rather than trusting it", () => {
    const result = resolveRepoRoot({
      envValue: "/gone",
      derived: REPO,
      fileExists: repoAt(REPO),
    });
    assert.equal(result.root, REPO);
    assert.equal(result.source, "derived");
  });

  it("falls back to a previously chosen directory", () => {
    const result = resolveRepoRoot({
      derived: BUNDLE,
      baked: "/moved/away",
      stored: REPO,
      fileExists: repoAt(REPO),
    });
    assert.equal(result.root, REPO);
    assert.equal(result.source, "stored");
  });

  it("reports failure when nothing validates", () => {
    const result = resolveRepoRoot({
      derived: BUNDLE,
      baked: "/moved/away",
      fileExists: repoAt(REPO),
    });
    assert.equal(result.root, null);
    assert.equal(result.source, null);
    assert.equal(result.tried.length, 2);
    assert.ok(result.tried.every((t) => t.valid === false));
  });

  it("skips absent sources without recording an attempt", () => {
    const result = resolveRepoRoot({
      envValue: "",
      derived: undefined,
      baked: "   ",
      stored: REPO,
      fileExists: repoAt(REPO),
    });
    assert.equal(result.source, "stored");
    assert.deepEqual(
      result.tried.map((t) => t.source),
      ["stored"],
    );
  });

  it("normalises a relative or untidy value before probing", () => {
    const result = resolveRepoRoot({
      envValue: `${REPO}/frontend/..`,
      fileExists: repoAt(REPO),
    });
    assert.equal(result.root, REPO);
  });

  it("returns nothing when given nothing", () => {
    const result = resolveRepoRoot({ fileExists: () => true });
    assert.equal(result.root, null);
    assert.deepEqual(result.tried, []);
  });
});

describe("describeAttempts", () => {
  it("names the environment variable so a bad override is diagnosable", () => {
    const { tried } = resolveRepoRoot({
      envValue: "/gone",
      fileExists: () => false,
    });
    const text = describeAttempts(tried);
    assert.match(text, new RegExp(REPO_ROOT_ENV_VAR));
    assert.match(text, /\/gone/);
  });

  it("says something useful when there was nothing to try", () => {
    assert.match(describeAttempts([]), /No candidate/);
  });
});
