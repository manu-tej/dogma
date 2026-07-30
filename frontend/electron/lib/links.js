"use strict";

/**
 * Navigation policy for the renderer.
 *
 * Without this, a stray anchor or a compromised dependency can navigate the
 * application window itself to an arbitrary page, leaving the user staring at
 * someone else's site inside what looks like Dogma. Anything that is not an
 * in-app URL or a plain web link is refused outright.
 */

/**
 * Origin of a URL, computed without relying on `URL.prototype.origin`.
 *
 * `origin` is unusable here: for a scheme the runtime does not know as
 * special, the spec says the origin is opaque, so Node returns the string
 * "null" for `app://dogma/x`. Chromium returns a real `app://dogma` tuple —
 * but only because of our `registerSchemesAsPrivileged` call, which Node knows
 * nothing about. Since this module runs in the main process on Node's URL
 * implementation, deriving the origin from the parts is the only form that is
 * correct in both runtimes.
 *
 * @param {URL} url
 * @returns {string}
 */
function originOf(url) {
  return `${url.protocol}//${url.host}`;
}

/**
 * @param {string} rawUrl
 * @param {string[]} internalOrigins Origins that may load in the app window.
 * @returns {"internal"|"external"|"blocked"}
 */
function classifyUrl(rawUrl, internalOrigins) {
  let url;
  try {
    url = new URL(rawUrl);
  } catch {
    return "blocked";
  }

  if (internalOrigins.includes(originOf(url))) {
    return "internal";
  }

  // Only ordinary web links are worth handing to the system browser.
  // file:, data:, javascript:, vscode: and friends are refused.
  if (url.protocol === "http:" || url.protocol === "https:") {
    return "external";
  }

  return "blocked";
}

module.exports = { classifyUrl, originOf };
