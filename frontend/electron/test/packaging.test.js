"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { describe, it } = require("node:test");

const pkg = require("../../package.json");

const build = pkg.build ?? {};

describe("packaging config", () => {
  it("names the bundle so the macOS menu reads dogma", () => {
    // The menu title comes from CFBundleName in the bundle's Info.plist, not
    // from app.setName(). Both are set: productName drives most of the bundle,
    // extendInfo pins the plist keys the menu and About panel actually read.
    assert.equal(build.productName, "dogma");
    assert.equal(build.mac?.extendInfo?.CFBundleName, "dogma");
    assert.equal(build.mac?.extendInfo?.CFBundleDisplayName, "dogma");
  });

  it("keeps asar disabled", () => {
    // Load-bearing, not a preference. The app:// handler serves the renderer with
    // net.fetch(pathToFileURL(...)), which goes through Chromium's network stack.
    // Electron's asar support is an fs-layer shim, so a file:// URL pointing
    // inside app.asar does not resolve and every asset 404s. If you want asar
    // back, either asarUnpack the build output or switch the handler to
    // fs.readFile with explicit MIME types — and change this test deliberately.
    assert.equal(build.asar, false);
  });

  it("does not sign with a certificate, having none", () => {
    assert.equal(build.mac?.identity, null);
  });

  it("still re-signs ad-hoc after packing", () => {
    // Not cosmetic. Electron's binary arrives linker-signed with a seal over the
    // original bundle; renaming it and rewriting Info.plist invalidates that
    // seal, and arm64 refuses to exec an invalid signature — silently, with exit
    // status 0 and the entry point never reached. See electron/after-pack.js.
    assert.equal(build.afterPack, "electron/after-pack.js");
    assert.ok(
      fs.existsSync(path.join(__dirname, "..", "after-pack.js")),
      "afterPack hook is referenced but missing",
    );
  });

  it("writes output somewhere git ignores", () => {
    const gitignore = fs.readFileSync(
      path.join(__dirname, "..", "..", "..", ".gitignore"),
      "utf8",
    );
    const output = build.directories?.output;
    assert.equal(output, "dist");
    assert.ok(
      gitignore.split(/\r?\n/).includes(`${output}/`),
      `.gitignore must ignore ${output}/`,
    );
  });

  it("keeps buildResources clear of the Vite output directory", () => {
    // electron-builder defaults buildResources to "build", which is exactly
    // where vite.config.ts writes the renderer. Leaving the default would make
    // the two fight over one directory.
    assert.notEqual(build.directories?.buildResources, "build");
    assert.equal(build.directories?.buildResources, "electron/assets");
  });

  it("ships the icon that make-icon.sh produces", () => {
    const icon = build.mac?.icon;
    assert.equal(icon, "electron/assets/icon.icns");
    assert.ok(
      fs.existsSync(path.join(__dirname, "..", "..", icon)),
      `${icon} is missing — run npm run icon`,
    );
  });

  it("excludes tests and source maps from the bundle", () => {
    const files = build.files ?? [];
    assert.ok(files.includes("!electron/test/**"));
    assert.ok(files.includes("!**/*.map"));
  });

  it("includes both halves of the app", () => {
    const files = build.files ?? [];
    assert.ok(files.includes("electron/**/*"), "main process");
    assert.ok(files.includes("build/**/*"), "renderer");
  });

  it("bakes the repo path before invoking the builder", () => {
    // Order matters: the generated file has to exist before electron-builder
    // collects `files`, or the packaged app ships without it and cannot find the
    // .venv.
    const script = pkg.scripts?.package ?? "";
    const bakeAt = script.indexOf("bake-repo-root");
    const buildAt = script.indexOf("electron-builder");
    assert.ok(bakeAt !== -1, "package script must bake the repo root");
    assert.ok(buildAt !== -1, "package script must run electron-builder");
    assert.ok(bakeAt < buildAt, "bake must run before electron-builder");
  });
});
