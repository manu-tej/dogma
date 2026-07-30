"use strict";

/**
 * Re-sign the packaged bundle ad-hoc, so macOS will actually run it.
 *
 * This is not optional on Apple Silicon. The Electron binary ships with a
 * linker-signed ad-hoc signature whose identifier is "Electron" and whose seal
 * covers the original bundle. Packaging renames the bundle, rewrites Info.plist
 * and adds resources, which invalidates that seal:
 *
 *   codesign --verify --deep --strict dogma.app
 *   dogma.app: code has no resources but signature indicates they must be present
 *
 * On arm64 the kernel refuses to exec a binary whose signature does not verify.
 * The failure is completely silent — no dialog, no stderr, exit status 0, and the
 * entry point never runs, so no amount of logging inside main.js reveals it.
 *
 * `mac.identity: null` in the build config disables electron-builder's own
 * signing, which is right: there are no Developer ID credentials here. But "do
 * not sign with a certificate" still needs "do sign ad-hoc", which is this hook.
 *
 * Ad-hoc signing does not make the app distributable. Gatekeeper still blocks it
 * for anyone who did not build it. It only makes it runnable locally, which is
 * the whole intent — see the desktop section of frontend/README.md.
 */

const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

exports.default = async function afterPack(context) {
  if (context.electronPlatformName !== "darwin") return;

  const appName = context.packager.appInfo.productFilename;
  const appPath = path.join(context.appOutDir, `${appName}.app`);

  if (!fs.existsSync(appPath)) {
    throw new Error(`afterPack: expected a bundle at ${appPath}`);
  }

  // --deep is the wrong tool for real distribution signing, but it is the right
  // one here: it walks the nested helper apps and frameworks that also carry
  // stale seals, and for an ad-hoc identity there is nothing to get wrong.
  execFileSync("codesign", ["--force", "--deep", "--sign", "-", appPath], {
    stdio: "inherit",
  });

  // Verify rather than assume. A silently unrunnable bundle is the exact failure
  // this hook exists to prevent, so a broken signature must fail the build.
  execFileSync("codesign", ["--verify", "--deep", "--strict", appPath], {
    stdio: "inherit",
  });

  console.log(`  • ad-hoc signed and verified  ${appName}.app`);
};
