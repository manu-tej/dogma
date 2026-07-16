#!/usr/bin/env node

"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { execFileSync } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const listed = execFileSync(
  "git",
  ["ls-files", "-z", "--cached", "--others", "--exclude-standard"],
  { cwd: root, encoding: "utf8" },
);
const files = [...new Set(listed.split("\0").filter(Boolean))].sort();
const problems = [];

function isForbiddenPath(relativePath) {
  const normalized = relativePath.replaceAll("\\", "/");
  const segments = normalized.split("/");
  const name = segments.at(-1);
  const environmentFile = name === ".env" || name.startsWith(".env.");
  const safeEnvironmentExample = name === ".env.example" || name.endsWith(".example");

  if (environmentFile && !safeEnvironmentExample) return "populated environment file";
  if (segments.some((part) => [".vite", ".dogma", "scratch_notes", "screenshots"].includes(part))) {
    return "generated or scratch directory";
  }
  if (["data", "results", "work", "logs"].includes(segments[0])) {
    return "local analysis input, output, or execution state";
  }
  if (name.startsWith(".nextflow")) return "local Nextflow state";
  if (
    normalized.startsWith("frontend/supabase/") ||
    normalized.startsWith("frontend/src/supabase/") ||
    normalized.startsWith("frontend/src/utils/supabase/")
  ) {
    return "generated Supabase or hosted-project material";
  }
  if (/\.(?:vsix|sqlite3?|db)(?:-(?:shm|wal))?$/i.test(name)) {
    return "generated package or local database";
  }
  if (/quration-publication\.zip$/i.test(name)) return "publication archive";
  if (/benchmark_results.*\.json$/i.test(name)) return "generated benchmark results";
  if (/\.log$/i.test(name)) return "local log";
  return null;
}

const sensitiveContent = [
  [/(?:sk-ant-|sk-proj-)[A-Za-z0-9_-]{16,}/, "API key"],
  [/gh[pousr]_[A-Za-z0-9]{20,}/, "GitHub token"],
  [/AKIA[0-9A-Z]{16}/, "AWS access key"],
  [/xox[baprs]-[A-Za-z0-9-]{20,}/, "Slack token"],
  [/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/, "private key"],
  [/eyJhbGciOiJ[A-Za-z0-9_.-]{80,}/, "embedded JWT"],
  [/\/Users\/(?!test\/|example\/)[^/\s]+\/(?:20\d\d|Documents|Desktop)\//, "developer-local absolute path"],
  [/github\.com\/yourusername\//, "placeholder repository URL"],
  [/production[- ]ready/i, "overstated readiness claim"],
  [/generateMockBio(?:Response)/, "unlabeled synthetic scientific-result fallback"],
  [/GSE(?:253718|149276)/, "legacy real-looking demo accession"],
];

for (const relativePath of files) {
  const pathProblem = isForbiddenPath(relativePath);
  if (pathProblem) problems.push(`${relativePath}: ${pathProblem}`);

  const absolutePath = path.join(root, relativePath);
  let stat;
  try {
    stat = fs.lstatSync(absolutePath);
  } catch {
    continue;
  }
  if (!stat.isFile() || stat.size > 5_000_000) continue;

  const buffer = fs.readFileSync(absolutePath);
  if (buffer.includes(0)) continue;
  const content = buffer.toString("utf8");
  for (const [pattern, label] of sensitiveContent) {
    if (pattern.test(content)) problems.push(`${relativePath}: possible ${label}`);
  }
}

if (problems.length > 0) {
  console.error("Public-safety preflight failed:");
  for (const problem of problems) console.error(`- ${problem}`);
  process.exitCode = 1;
} else {
  console.log(`Public-safety preflight passed (${files.length} candidate files checked).`);
}
