"use strict";

const assert = require("assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { EventEmitter } = require("events");
const {
  ServiceProcessManager,
  autoServiceCwdCandidates,
  buildServiceEnvironment,
  buildServiceCommand,
  findDogmaRepoRoot,
  hasServiceModule,
  parseHostPort,
  resolveServiceCwd
} = require("../src/serviceProcessManager");

assert.deepStrictEqual(parseHostPort("http://127.0.0.1:8765"), { host: "127.0.0.1", port: 8765 });
assert.deepStrictEqual(parseHostPort("http://localhost"), { host: "localhost", port: 80 });
assert.strictEqual(resolveServiceCwd("../dogma-local-service", "/workspace/demo").cwd, "/workspace/dogma-local-service");
assert(autoServiceCwdCandidates("/workspace/demo", "/extensions/dogma").includes("/extensions/dogma/python-service"));
assert.strictEqual(hasServiceModule("/definitely/missing/dogma-service"), false);

const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), "dogma-extension-"));
const bundledService = path.join(tmpRoot, "python-service");
fs.mkdirSync(path.join(bundledService, "dogma_service"), { recursive: true });
fs.writeFileSync(path.join(bundledService, "dogma_service", "__main__.py"), "", "utf8");
assert.strictEqual(resolveServiceCwd("auto", "/workspace/demo", { extensionRoot: tmpRoot }).cwd, bundledService);

const repoRoot = path.join(tmpRoot, "dogma");
const repoWorkspace = path.join(repoRoot, "dogma-demo-workspace");
fs.mkdirSync(path.join(repoRoot, "frontend"), { recursive: true });
fs.mkdirSync(path.join(repoRoot, "src", "quration"), { recursive: true });
fs.mkdirSync(repoWorkspace, { recursive: true });
fs.writeFileSync(path.join(repoRoot, "frontend", "package.json"), "{}", "utf8");
assert.strictEqual(findDogmaRepoRoot(repoWorkspace), repoRoot);
const serviceEnv = buildServiceEnvironment({ PATH: "/bin" }, repoWorkspace);
assert.strictEqual(serviceEnv.DOGMA_REPO, repoRoot);
assert.strictEqual(serviceEnv.QURATION_REPO, repoRoot);

const command = buildServiceCommand(
  {
    url: "http://127.0.0.1:8765",
    python: "python3",
    moduleName: "dogma_service",
    cwd: "../dogma-local-service",
    maxFiles: 500
  },
  "/workspace/demo"
);
assert.strictEqual(command.command, "python3");
assert.deepStrictEqual(command.args, [
  "-m",
  "dogma_service",
  "serve",
  "/workspace/demo",
  "--host",
  "127.0.0.1",
  "--port",
  "8765",
  "--max-files",
  "500"
]);
assert.strictEqual(command.cwd, "/workspace/dogma-local-service");
assert.strictEqual(command.cwdResolution.source, "configured");

const spawned = [];
const fakeChild = new EventEmitter();
fakeChild.stdout = new EventEmitter();
fakeChild.stderr = new EventEmitter();
fakeChild.exitCode = null;
fakeChild.killed = false;
fakeChild.kill = () => {
  fakeChild.killed = true;
  fakeChild.exitCode = 0;
};

const manager = new ServiceProcessManager({
  spawn: (cmd, args, options) => {
    spawned.push({ cmd, args, options });
    return fakeChild;
  },
  output: { appendLine() {}, append() {} }
});

const started = manager.start({ url: "http://127.0.0.1:8765", cwd: "../dogma-local-service" }, "/workspace/demo");
assert.strictEqual(started.started, true);
assert.strictEqual(manager.isRunning(), true);
assert.strictEqual(spawned[0].cmd, "python3");
assert.strictEqual(spawned[0].options.cwd, "/workspace/dogma-local-service");
assert.strictEqual(spawned[0].options.env.PATH, process.env.PATH);

const secondStart = manager.start({ url: "http://127.0.0.1:8765", cwd: "../dogma-local-service" }, "/workspace/demo");
assert.strictEqual(secondStart.started, false);
assert.strictEqual(secondStart.alreadyRunning, true);

const stopped = manager.stop();
assert.strictEqual(stopped.stopped, true);
assert.strictEqual(manager.isRunning(), false);

console.log("service process manager tests passed");
