"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

function parseHostPort(serviceUrl) {
  const url = new URL(serviceUrl);
  return {
    host: url.hostname || "127.0.0.1",
    port: Number(url.port || (url.protocol === "https:" ? 443 : 80))
  };
}

function hasServiceModule(candidate, moduleName = "dogma_service") {
  return fs.existsSync(path.join(candidate, moduleName, "__main__.py"));
}

function hasDogmaRepoShape(candidate) {
  return (
    fs.existsSync(path.join(candidate, "frontend", "package.json")) &&
    (fs.existsSync(path.join(candidate, "src", "quration")) || fs.existsSync(path.join(candidate, "src")))
  );
}

function findDogmaRepoRoot(startPath) {
  let current = path.resolve(startPath);
  while (true) {
    if (hasDogmaRepoShape(current)) return current;
    const parent = path.dirname(current);
    if (parent === current) return null;
    current = parent;
  }
}

function buildServiceEnvironment(baseEnv, workspaceRoot) {
  const env = { ...baseEnv };
  const repoRoot = findDogmaRepoRoot(workspaceRoot);
  if (repoRoot) {
    if (!env.DOGMA_REPO) env.DOGMA_REPO = repoRoot;
    if (!env.QURATION_REPO) env.QURATION_REPO = repoRoot;
  }
  return env;
}

function autoServiceCwdCandidates(workspaceRoot, extensionRoot) {
  const candidates = [];
  const add = (candidate) => {
    if (candidate && !candidates.includes(candidate)) candidates.push(candidate);
  };

  add(extensionRoot ? path.join(extensionRoot, "python-service") : null);
  add(path.resolve(workspaceRoot, "../dogma-local-service"));
  add(path.resolve(workspaceRoot, "../biocursor-local-service"));
  add(path.resolve(workspaceRoot, "dogma-local-service"));
  add(path.resolve(workspaceRoot, "biocursor-local-service"));
  add(path.resolve(workspaceRoot, ".dogma", "local-service"));
  add(extensionRoot ? path.resolve(extensionRoot, "../dogma-local-service") : null);
  add(extensionRoot ? path.resolve(extensionRoot, "../biocursor-local-service") : null);
  add(workspaceRoot);
  return candidates;
}

function resolveServiceCwd(serviceCwd, workspaceRoot, options = {}) {
  const configured = serviceCwd || "auto";
  const extensionRoot = options.extensionRoot;
  const moduleName = options.moduleName || "dogma_service";
  if (configured !== "auto") {
    if (path.isAbsolute(configured)) return { cwd: configured, source: "configured", candidates: [configured] };
    const cwd = path.resolve(workspaceRoot, configured);
    return { cwd, source: "configured", candidates: [cwd] };
  }

  const candidates = autoServiceCwdCandidates(workspaceRoot, extensionRoot);
  const cwd = candidates.find((candidate) => hasServiceModule(candidate, moduleName)) || workspaceRoot;
  return {
    cwd,
    source: cwd === workspaceRoot ? "workspace-module" : "auto",
    candidates
  };
}

function buildServiceCommand(config, workspaceRoot, options = {}) {
  const { host, port } = parseHostPort(config.url);
  const python = config.python || "python3";
  const moduleName = config.moduleName || "dogma_service";
  const cwdResolution = resolveServiceCwd(config.cwd || "auto", workspaceRoot, {
    extensionRoot: options.extensionRoot,
    moduleName
  });
  const args = [
    "-m",
    moduleName,
    "serve",
    workspaceRoot,
    "--host",
    host,
    "--port",
    String(port),
    "--max-files",
    String(config.maxFiles || 200)
  ];

  return { command: python, args, cwd: cwdResolution.cwd, cwdResolution };
}

class ServiceProcessManager {
  constructor(options = {}) {
    this.spawn = options.spawn || spawn;
    this.output = options.output;
    this.extensionRoot = options.extensionRoot;
    this.process = null;
  }

  isRunning() {
    return Boolean(this.process && this.process.exitCode === null && !this.process.killed);
  }

  start(config, workspaceRoot) {
    if (this.isRunning()) {
      return { started: false, alreadyRunning: true };
    }

    const command = buildServiceCommand(config, workspaceRoot, { extensionRoot: this.extensionRoot });
    const child = this.spawn(command.command, command.args, {
      cwd: command.cwd,
      env: buildServiceEnvironment(process.env, workspaceRoot),
      stdio: ["ignore", "pipe", "pipe"]
    });

    this.process = child;
    this.output?.appendLine(`Dogma local service: ${command.command} ${command.args.join(" ")}`);
    this.output?.appendLine(`cwd: ${command.cwd}`);
    if (command.cwdResolution?.source === "auto") {
      this.output?.appendLine(`auto service candidates: ${command.cwdResolution.candidates.join(", ")}`);
    }

    child.stdout?.on("data", (chunk) => this.output?.append(chunk.toString()));
    child.stderr?.on("data", (chunk) => this.output?.append(chunk.toString()));
    child.on("error", (error) => {
      this.output?.appendLine(`Dogma local service failed to start: ${error.message}`);
      if (this.process === child) this.process = null;
    });
    child.on("exit", (code, signal) => {
      this.output?.appendLine(`Dogma local service exited with code=${code} signal=${signal || "none"}`);
      if (this.process === child) this.process = null;
    });

    return { started: true, command };
  }

  stop() {
    if (!this.isRunning()) {
      return { stopped: false };
    }
    const child = this.process;
    child.kill();
    this.process = null;
    return { stopped: true };
  }
}

module.exports = {
  ServiceProcessManager,
  buildServiceCommand,
  parseHostPort,
  resolveServiceCwd,
  autoServiceCwdCandidates,
  buildServiceEnvironment,
  findDogmaRepoRoot,
  hasDogmaRepoShape,
  hasServiceModule
};
