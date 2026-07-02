#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..");
const repoParent = path.dirname(repoRoot);
const renameTarget = path.join(repoParent, "dogma");
const ignoredEntries = new Set([".DS_Store"]);
const ignoredDirs = new Set([
  ".git",
  ".dogma",
  ".pytest_cache",
  "__pycache__",
  "node_modules",
  "out",
  "dist",
  "build"
]);
const scanRoots = [
  "README.md",
  "package.json",
  "docs/dogma",
  "dogma-local-service",
  "dogma-vscode-extension/src",
  "dogma-vscode-extension/test",
  "dogma-vscode-extension/README.md"
];
const textExtensions = new Set([
  ".cjs",
  ".css",
  ".html",
  ".js",
  ".json",
  ".md",
  ".mjs",
  ".py",
  ".sh",
  ".toml",
  ".txt",
  ".yaml",
  ".yml"
]);

function listUsefulEntries(dir) {
  try {
    return fs.readdirSync(dir).filter((entry) => !ignoredEntries.has(entry));
  } catch {
    return [];
  }
}

function isTextFile(filePath) {
  const stat = fs.statSync(filePath);
  if (stat.size > 1_000_000) return false;
  return textExtensions.has(path.extname(filePath).toLowerCase());
}

function walkTextFiles(startPath, files = []) {
  if (!fs.existsSync(startPath)) return files;
  const stat = fs.statSync(startPath);
  if (stat.isDirectory()) {
    if (ignoredDirs.has(path.basename(startPath))) return files;
    for (const entry of fs.readdirSync(startPath)) {
      walkTextFiles(path.join(startPath, entry), files);
    }
  } else if (stat.isFile() && isTextFile(startPath)) {
    files.push(startPath);
  }
  return files;
}

function relative(filePath) {
  return path.relative(repoRoot, filePath) || ".";
}

const failures = [];
const warnings = [];

if (path.basename(repoRoot) !== "dogma") {
  if (fs.existsSync(renameTarget)) {
    const entries = listUsefulEntries(renameTarget);
    if (path.resolve(renameTarget) !== repoRoot && entries.length > 0) {
      failures.push(`Rename target exists and is not empty: ${renameTarget}`);
    } else {
      warnings.push(`Rename target already exists but is empty: ${renameTarget}`);
    }
  } else {
    warnings.push(`Rename target is available: ${renameTarget}`);
  }
}

const forbiddenPaths = [];
if (path.basename(repoRoot) !== "dogma") {
  forbiddenPaths.push(repoRoot);
}
if (repoRoot.endsWith(`${path.sep}quration`)) {
  forbiddenPaths.push(repoRoot.replace(/quration$/, "dogma"));
}

for (const root of scanRoots) {
  for (const filePath of walkTextFiles(path.join(repoRoot, root))) {
    const text = fs.readFileSync(filePath, "utf8");
    for (const forbidden of forbiddenPaths) {
      if (forbidden && text.includes(forbidden)) {
        failures.push(`${relative(filePath)} contains machine-specific path ${forbidden}`);
      }
    }
  }
}

console.log("Dogma rename preflight");
console.log(`- repo: ${repoRoot}`);
console.log(`- expected target: ${renameTarget}`);
for (const warning of warnings) console.log(`- warning: ${warning}`);

if (failures.length) {
  console.error("\nRename preflight failed:");
  for (const failure of failures) console.error(`- ${failure}`);
  process.exit(1);
}

console.log("- status: ready");
