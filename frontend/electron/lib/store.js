"use strict";

/**
 * Tiny JSON file store for window bounds. Every operation is best-effort:
 * a corrupt or unwritable state file must never stop the app from opening.
 */

const fs = require("node:fs");
const path = require("node:path");

/**
 * @param {string} filePath
 * @returns {unknown} Parsed contents, or null on any failure.
 */
function readJson(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return null;
  }
}

/**
 * @param {string} filePath
 * @param {unknown} value
 * @returns {boolean} Whether the write succeeded.
 */
function writeJson(filePath, value) {
  try {
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, JSON.stringify(value, null, 2), "utf8");
    return true;
  } catch {
    return false;
  }
}

module.exports = { readJson, writeJson };
