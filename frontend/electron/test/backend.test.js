"use strict";

const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const http = require("node:http");
const { describe, it } = require("node:test");

const {
  BackendStartError,
  LIVENESS_PATH,
  createLogBuffer,
  probeDependencies,
  probeLiveness,
  startBackend,
  terminate,
  waitForLiveness,
} = require("../lib/backend");

/**
 * Start a throwaway HTTP server that answers every request with `status`.
 * @returns {Promise<{baseUrl: string, paths: string[], close: () => Promise<void>}>}
 */
async function stubServer(status, body = "{}") {
  const paths = [];
  const server = http.createServer((req, res) => {
    paths.push(req.url);
    res.writeHead(status, { "content-type": "application/json" });
    res.end(body);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address();
  return {
    baseUrl: `http://127.0.0.1:${port}`,
    paths,
    close: () => new Promise((resolve) => server.close(resolve)),
  };
}

/** Minimal stand-in for a spawned uvicorn process. */
function fakeChild() {
  const child = new EventEmitter();
  child.stdout = new EventEmitter();
  child.stderr = new EventEmitter();
  child.exitCode = null;
  child.signalCode = null;
  child.killed = [];
  child.kill = (signal) => {
    child.killed.push(signal);
    return true;
  };
  return child;
}

const noSleep = () => Promise.resolve();

describe("createLogBuffer", () => {
  it("splits chunks into lines and keeps the tail", () => {
    const logs = createLogBuffer(3);
    logs.push("one\ntwo\n");
    logs.push("three\r\nfour\n");
    assert.equal(logs.length, 3);
    assert.equal(logs.tail(), "two\nthree\nfour");
  });

  it("drops blank lines", () => {
    const logs = createLogBuffer();
    logs.push("\n\nreal\n\n");
    assert.equal(logs.tail(), "real");
  });

  it("returns an empty string when nothing was logged", () => {
    assert.equal(createLogBuffer().tail(), "");
  });
});

describe("probeLiveness", () => {
  it("probes a dependency-free endpoint rather than /health", () => {
    // /health Depends on Postgres and Redis, so on a machine without them it
    // answers 500 forever and gating startup on it would never let the app open.
    assert.equal(LIVENESS_PATH, "/openapi.json");
  });

  it("treats a 200 as live", async () => {
    const server = await stubServer(200);
    try {
      assert.equal(await probeLiveness(server.baseUrl), true);
      assert.deepEqual(server.paths, [LIVENESS_PATH]);
    } finally {
      await server.close();
    }
  });

  it("treats a 500 as live, because the app is still routing", async () => {
    const server = await stubServer(500);
    try {
      assert.equal(await probeLiveness(server.baseUrl), true);
    } finally {
      await server.close();
    }
  });

  it("treats a refused connection as not live", async () => {
    // Port 1 is reserved and nothing listens there.
    assert.equal(await probeLiveness("http://127.0.0.1:1", 500), false);
  });
});

describe("probeDependencies", () => {
  it("reports a healthy backend", async () => {
    const server = await stubServer(200, JSON.stringify({ status: "healthy" }));
    try {
      const result = await probeDependencies(server.baseUrl);
      assert.equal(result.ok, true);
      assert.equal(result.status, 200);
      assert.equal(result.detail, "healthy");
      assert.deepEqual(server.paths, ["/health"]);
    } finally {
      await server.close();
    }
  });

  it("reports a degraded backend without throwing", async () => {
    const server = await stubServer(
      500,
      JSON.stringify({ message: "no database configured" }),
    );
    try {
      const result = await probeDependencies(server.baseUrl);
      assert.equal(result.ok, false);
      assert.equal(result.status, 500);
      assert.equal(result.detail, "no database configured");
    } finally {
      await server.close();
    }
  });

  it("tolerates a non-JSON body", async () => {
    const server = await stubServer(500, "<html>boom</html>");
    try {
      const result = await probeDependencies(server.baseUrl);
      assert.equal(result.ok, false);
      assert.equal(result.status, 500);
      assert.equal(result.detail, null);
    } finally {
      await server.close();
    }
  });

  it("reports an unreachable backend", async () => {
    const result = await probeDependencies("http://127.0.0.1:1", 500);
    assert.equal(result.ok, false);
    assert.equal(result.status, null);
  });
});

describe("waitForLiveness", () => {
  it("resolves as soon as the probe succeeds", async () => {
    let calls = 0;
    const result = await waitForLiveness({
      probe: async () => ++calls >= 3,
      sleep: noSleep,
    });
    assert.deepEqual(result, { ok: true });
    assert.equal(calls, 3);
  });

  it("reports a timeout using the injected clock", async () => {
    let clock = 0;
    const result = await waitForLiveness({
      probe: async () => false,
      timeoutMs: 1_000,
      intervalMs: 100,
      sleep: async () => {
        clock += 100;
      },
      now: () => clock,
    });
    assert.deepEqual(result, { ok: false, reason: "timeout" });
  });

  it("stops early when the process has already exited", async () => {
    let probes = 0;
    const result = await waitForLiveness({
      probe: async () => {
        probes += 1;
        return false;
      },
      sleep: noSleep,
      shouldAbort: () => true,
    });
    assert.deepEqual(result, { ok: false, reason: "exited" });
    // One probe, then the abort check — no pointless polling for 90 seconds.
    assert.equal(probes, 1);
  });

  it("still succeeds when the probe passes on the same tick the process exits", async () => {
    const result = await waitForLiveness({
      probe: async () => true,
      sleep: noSleep,
      shouldAbort: () => true,
    });
    assert.deepEqual(result, { ok: true });
  });
});

describe("startBackend", () => {
  const base = {
    repoRoot: "/repo",
    corsOrigin: "app://dogma",
    fileExists: () => true,
  };

  it("adopts an already-responding backend without spawning", async () => {
    let spawned = false;
    const statuses = [];
    const backend = await startBackend({
      ...base,
      probe: async () => true,
      spawnFn: () => {
        spawned = true;
        return fakeChild();
      },
      onStatus: (s) => statuses.push(s),
    });

    assert.equal(backend.mode, "adopted");
    assert.equal(spawned, false, "must not spawn a rival uvicorn");
    assert.equal(backend.baseUrl, "http://127.0.0.1:8000");
    assert.match(statuses.join(" "), /already running/);
    // Adopting must not kill a process we do not own.
    await backend.stop();
  });

  it("fails with actionable guidance when the venv is missing", async () => {
    await assert.rejects(
      startBackend({
        ...base,
        fileExists: () => false,
        probe: async () => false,
        spawnFn: () => fakeChild(),
      }),
      (error) => {
        assert.ok(error instanceof BackendStartError);
        assert.equal(error.code, "NO_VENV");
        assert.match(error.message, /npm run install:all/);
        assert.match(error.message, /\.venv/);
        return true;
      },
    );
  });

  it("spawns uvicorn and passes the renderer origin through DOGMA_CORS_ORIGINS", async () => {
    let recorded = null;
    let live = false;
    const child = fakeChild();

    const backend = await startBackend({
      ...base,
      probe: async () => live,
      spawnFn: (cmd, args, options) => {
        recorded = { cmd, args, options };
        // Become live only once the process exists.
        live = true;
        return child;
      },
    });

    assert.equal(backend.mode, "spawned");
    assert.match(recorded.cmd, /\.venv[/\\]bin[/\\]python$|python\.exe$/);
    assert.deepEqual(recorded.args, [
      "-m",
      "uvicorn",
      "quration.api.server:app",
      "--host",
      "127.0.0.1",
      "--port",
      "8000",
    ]);
    assert.equal(recorded.options.cwd, "/repo");
    assert.match(recorded.options.env.DOGMA_CORS_ORIGINS, /app:\/\/dogma/);
    assert.equal(recorded.options.env.PYTHONUNBUFFERED, "1");
  });

  it("surfaces captured output when the process dies during startup", async () => {
    const child = fakeChild();
    await assert.rejects(
      startBackend({
        ...base,
        probe: async () => false,
        spawnFn: () => {
          setImmediate(() => {
            child.stderr.emit("data", "ModuleNotFoundError: No module named 'quration'\n");
            child.exitCode = 1;
            child.emit("exit", 1, null);
          });
          return child;
        },
      }),
      (error) => {
        assert.ok(error instanceof BackendStartError);
        assert.equal(error.code, "EXITED");
        // Without the captured stderr this failure is unactionable.
        assert.match(error.logs, /ModuleNotFoundError/);
        return true;
      },
    );
  });

  it("reports a timeout when the process lives but never responds", async () => {
    const child = fakeChild();
    await assert.rejects(
      startBackend({
        ...base,
        probe: async () => false,
        spawnFn: () => child,
        startupTimeoutMs: 0,
      }),
      (error) => {
        assert.equal(error.code, "TIMEOUT");
        return true;
      },
    );
    assert.ok(child.killed.includes("SIGTERM"), "a stuck backend must be cleaned up");
  });
});

describe("terminate", () => {
  it("sends SIGTERM and resolves when the child exits", async () => {
    const child = fakeChild();
    const done = terminate(child, 1_000);
    assert.deepEqual(child.killed, ["SIGTERM"]);
    child.emit("exit", 0, "SIGTERM");
    await done;
  });

  it("escalates to SIGKILL when the grace period lapses", async () => {
    const child = fakeChild();
    await terminate(child, 1);
    assert.deepEqual(child.killed, ["SIGTERM", "SIGKILL"]);
  });

  it("is a no-op for a process that already exited", async () => {
    const child = fakeChild();
    child.exitCode = 0;
    await terminate(child);
    assert.deepEqual(child.killed, []);
  });

  it("tolerates a missing child", async () => {
    await terminate(null);
  });
});
