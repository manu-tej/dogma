"""Prove the integration claim from outside, by use rather than by our own tests.

Everything so far has been verified by tests living in the repo, run by the repo's
own tooling, on a machine with a populated `.venv` and an editable install. This
script deliberately has none of that:

  - it clones the repo the way a stranger would (no `.venv`, no npm install, no
    pip install, no PYTHONPATH),
  - it launches `bin/dogma mcp` the way an MCP host does (own working directory,
    scrubbed environment, pipes for stdio),
  - it speaks the real MCP handshake, in order, including the notifications that
    used to draw an illegal reply,
  - and it points the tools at the clone's own workspace, not the source repo's.

Run it with any Python 3. It prints one line per check and exits non-zero on the
first failure.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Derived, not hardcoded: this file lives in <repo>/tools/.
SOURCE_REPO = Path(__file__).resolve().parents[1]
# Whatever is checked out. Cloning a branch proves the branch, not some fixed one.
BRANCH = subprocess.run(
    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
    cwd=SOURCE_REPO, capture_output=True, text=True,
).stdout.strip() or "HEAD"

PASS, FAIL = "  ok  ", " FAIL "
failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"[{PASS if condition else FAIL}] {label}")
    if not condition:
        if detail:
            print(f"         {detail}")
        failures.append(label)


class ServerDidNotAnswer(RuntimeError):
    """Raised when the server never replied — carrying its stderr, which is
    where the launcher writes the actual reason."""


class Host:
    """A minimal MCP host speaking stdio JSON-RPC, as Cursor/Codex/Zed do."""

    def __init__(self, launcher: Path, cwd: Path, env: dict[str, str]):
        # stderr goes to a file, not a pipe. An unread stderr pipe fills and
        # blocks the child the moment anything writes a traceback to it — so the
        # failure mode of this harness would be a hang rather than a message.
        self.stderr_path = Path(tempfile.mkstemp(prefix="dogma-mcp-stderr-")[1])
        self.stderr_file = self.stderr_path.open("w")
        self.proc = subprocess.Popen(
            [str(launcher), "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr_file,
            cwd=str(cwd),
            env=env,
            text=True,
            bufsize=1,
        )

    def send(self, payload: dict) -> None:
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()

    def request(self, method: str, message_id, params=None) -> dict:
        body = {"jsonrpc": "2.0", "id": message_id, "method": method}
        if params is not None:
            body["params"] = params
        self.send(body)
        return self.read_reply()

    def notify(self, method: str, params=None) -> None:
        """A notification has no id. The spec forbids any reply."""
        body = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        self.send(body)

    def read_reply(self) -> dict:
        assert self.proc.stdout
        line = self.proc.stdout.readline()
        if not line:
            # The launcher explains itself on stderr when it cannot start, and
            # that explanation is the whole diagnosis. Reporting only "no reply"
            # would throw it away and leave the reader to guess — which is the
            # same silent-failure shape this harness exists to catch.
            self.stderr_file.flush()
            detail = self.stderr_path.read_text().strip() or "(nothing on stderr)"
            raise ServerDidNotAnswer(
                "the server closed stdout without replying. Its stderr said:\n"
                + "\n".join(f"    {ln}" for ln in detail.splitlines())
            )
        return json.loads(line)

    def close(self) -> tuple[int, str]:
        assert self.proc.stdin
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.stderr_file.close()
        return self.proc.returncode, self.stderr_path.read_text()


def main() -> int:
    # .resolve() matters: on macOS mkdtemp returns /var/folders/..., which is a
    # symlink to /private/var/folders/.... The service resolves the root it is
    # given, so comparing an unresolved path against a resolved one would fail
    # for a reason that has nothing to do with the property being tested.
    workdir = Path(tempfile.mkdtemp(prefix="dogma-fresh-clone-")).resolve()
    clone = workdir / "dogma"
    print(f"clone target: {clone}\n")

    # --- 1. clone as a stranger would --------------------------------------
    result = subprocess.run(
        ["git", "clone", "--quiet", "--branch", BRANCH, "--single-branch",
         f"file://{SOURCE_REPO}", str(clone)],
        capture_output=True, text=True,
    )
    check("git clone succeeds", result.returncode == 0, result.stderr)
    if result.returncode != 0:
        return 1

    check("the clone has no .venv", not (clone / ".venv").exists())
    check("the clone has no node_modules", not (clone / "node_modules").exists())
    check("bin/dogma survived the clone as executable",
          os.access(clone / "bin" / "dogma", os.X_OK),
          "git did not preserve the executable bit")
    check("AGENTS.md is present for agents that do not read CLAUDE.md",
          (clone / "AGENTS.md").is_file())

    # --- 2. launch the way an MCP host does --------------------------------
    # Scrub every hint of the source checkout. An MCP host inherits its own
    # environment, not the user's activated shell.
    env = {
        k: v for k, v in os.environ.items()
        if k not in {"PYTHONPATH", "VIRTUAL_ENV", "DOGMA_PYTHON", "PYTHONHOME"}
    }
    # Dropping the source repo's .venv from PATH is not cosmetic. `npm run
    # install:python` editable-installs dogma-local-service there, and a
    # setuptools editable install works by registering a META-PATH FINDER, which
    # Python consults BEFORE sys.path — so PYTHONPATH would not win. The clone's
    # launcher would find that interpreter, import the SOURCE repo's code, and
    # every check below would pass while testing the wrong checkout.
    env["PATH"] = os.pathsep.join(
        entry for entry in env.get("PATH", "").split(os.pathsep)
        if entry and not Path(entry).resolve().is_relative_to(SOURCE_REPO)
    )

    # Prove the scrub worked rather than trusting it: the interpreter this clone
    # will find must NOT be able to import dogma_service on its own.
    probe = subprocess.run(
        ["python3", "-c", "import dogma_service"],
        capture_output=True, text=True, cwd=str(workdir), env=env,
    )
    check("the chosen interpreter has no pre-installed dogma (so the clone's "
          "own code is what runs)",
          probe.returncode != 0,
          "python3 already imports dogma_service — this run would test the "
          "source checkout, not the clone")
    # Launch from a directory unrelated to the clone, as a host would.
    launch_cwd = workdir

    host = Host(clone / "bin" / "dogma", launch_cwd, env)

    # --- 3. the real handshake, in order -----------------------------------
    init = host.request("initialize", 1, {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "prove-integration", "version": "0"},
    })
    check("initialize returns a result", "result" in init, json.dumps(init))
    check("initialize echoes the request id", init.get("id") == 1)
    check("server identifies itself",
          init.get("result", {}).get("serverInfo", {}).get("name")
          == "dogma-evidence-control-plane")

    # The notification a host sends immediately after initialize. Any reply here
    # is a protocol violation, and the next read would desynchronise the stream.
    host.notify("notifications/initialized")

    # The notification that used to draw an illegal `"id": null` error response.
    host.notify("notifications/cancelled", {"requestId": 99, "reason": "user"})

    # If either notification produced a reply, this read returns it instead of
    # the tools/list result — so the id check below is what actually proves it.
    listed = host.request("tools/list", 2)
    check("no notification drew a reply (stream still in sync)",
          listed.get("id") == 2,
          f"expected id 2, got {json.dumps(listed)[:200]}")

    tools = {t["name"] for t in listed.get("result", {}).get("tools", [])}

    # Subset, not equality. An exact-set assertion fails in the wrong direction:
    # it caught the journal tools being ADDED — which is not a regression — while
    # the thing worth catching is a tool going MISSING from a fresh clone. This
    # assertion failed for that reason once already; the surface is expected to
    # grow, and a check that cries wolf on growth gets muted.
    required_inspection = {
        "create_claim_graph", "record_analysis_run", "attach_evidence",
        "list_untested_or_stale_claims", "check_method_assumptions",
        "export_evidence_bundle",
    }
    check("every workspace-inspection tool is advertised",
          required_inspection <= tools,
          f"missing {sorted(required_inspection - tools)}")

    # The notebook half. Separate, because these carry a different contract: two
    # of them write, and `check_claim_shape` is what compares a claimed graph
    # against what the record can actually support.
    required_journal = {"open_journal", "record_decision", "check_claim_shape"}
    check("every bench-journal tool is advertised",
          required_journal <= tools,
          f"missing {sorted(required_journal - tools)}")
    print(f"         (server advertises {len(tools)} tools)")

    # --- 4. real work against the clone's own workspace --------------------
    demo = clone / "dogma-demo-workspace"
    check("the clone carries a workspace to point at", demo.is_dir())

    called = host.request("tools/call", 3, {
        "name": "check_method_assumptions",
        "arguments": {"root": str(demo)},
    })
    check("check_method_assumptions answers", called.get("id") == 3)
    payload = called.get("result", {}).get("structuredContent", {})
    check("it did not error", called.get("result", {}).get("isError") is False,
          json.dumps(called)[:300])
    check("the answer is about the clone, not the source repo",
          str(payload.get("root", "")).startswith(str(clone)),
          f"root={payload.get('root')!r}")
    check("it reports method contracts", "contracts" in payload)

    untested = host.request("tools/call", 4, {
        "name": "list_untested_or_stale_claims",
        "arguments": {"root": str(demo)},
    })
    upayload = untested.get("result", {}).get("structuredContent", {})
    check("list_untested_or_stale_claims answers", untested.get("id") == 4)
    check("the vocabulary-drift field is present (the bug fixed this session)",
          "unrecognised_edge_states" in upayload,
          f"keys={sorted(upayload)}")
    check("no unrecognised edge states against a real workspace",
          upayload.get("unrecognised_edge_states") == [],
          f"got {upayload.get('unrecognised_edge_states')}")

    # --- 5. the bench journal, round-tripped in the clone ------------------
    # The notebook is the half an agent WRITES to, so proving it from outside
    # means actually writing. Into the clone's own workspace, which is discarded
    # with it — this must never touch the source checkout.
    empty = host.request("tools/call", 5, {
        "name": "open_journal", "arguments": {"root": str(demo)},
    })
    esummary = empty.get("result", {}).get("structuredContent", {}).get("summary", {})
    check("a fresh workspace reports an absent journal rather than erroring",
          esummary.get("present") is False and esummary.get("entries") == 0,
          f"got {esummary}")

    written = host.request("tools/call", 6, {
        "name": "record_decision",
        "arguments": {
            "root": str(demo), "agent": "prove-integration",
            "about": "whether the journal round-trips from a fresh clone",
            "chose": "write one entry and read it back",
            "because": "a notebook that cannot be written from outside is not a notebook",
        },
    })
    entry = written.get("result", {}).get("structuredContent", {}).get("entry", {})
    check("a decision can be recorded", bool(entry.get("entry_id")), f"got {written}")
    check("an agent's claim is marked self-reported",
          entry.get("self_reported") is True,
          "an unmarked agent claim is indistinguishable from an observation")
    check("the service stamped the time, not the caller",
          bool(entry.get("recorded_at")))

    reread = host.request("tools/call", 7, {
        "name": "open_journal", "arguments": {"root": str(demo)},
    })
    rsummary = reread.get("result", {}).get("structuredContent", {}).get("summary", {})
    check("the entry survives a re-read", rsummary.get("entries") == 1, f"got {rsummary}")
    check("it is counted as self-reported, not observed",
          rsummary.get("self_reported") == 1 and rsummary.get("service_observed") == 0,
          f"got {rsummary}")

    shape = host.request("tools/call", 8, {
        "name": "check_claim_shape", "arguments": {"root": str(demo)},
    })
    spayload = shape.get("result", {}).get("structuredContent", {})
    check("claim shape can be checked", "consistent" in spayload, f"keys={sorted(spayload)}")
    check("no edge claims a measurement the record cannot support",
          spayload.get("edges", {}).get("claiming_measurement") == 0,
          f"got {spayload.get('edges')}")
    check("it states the measurement gap rather than hiding it",
          any("never a measurement" in str(limit) for limit in spayload.get("limitations", [])),
          f"limitations={spayload.get('limitations')}")

    # --- 6. stdout hygiene and clean shutdown ------------------------------
    code, stderr = host.close()
    check("server exits cleanly when stdin closes", code == 0, f"exit {code}")
    check("nothing was written to stderr during normal operation",
          stderr.strip() == "", stderr[:300])

    # --- 6. the shell-only path, same clone, same scrubbed env -------------
    cli = subprocess.run(
        [str(clone / "bin" / "dogma"), "guardrails", str(demo)],
        capture_output=True, text=True, cwd=str(launch_cwd), env=env, timeout=120,
    )
    check("CLI mode works for agents without MCP", cli.returncode == 0, cli.stderr[:300])
    try:
        parsed = json.loads(cli.stdout)
        check("CLI stdout is clean JSON (safe to pipe)", True)
        check("CLI reports workflow steps", "workflow_steps" in parsed,
              f"keys={sorted(parsed)[:10]}")
    except json.JSONDecodeError as exc:
        check("CLI stdout is clean JSON (safe to pipe)", False, str(exc))

    # --- 7. a second subcommand, to show the whole CLI is reachable --------
    ledger = subprocess.run(
        [str(clone / "bin" / "dogma"), "evidence-ledger", str(demo)],
        capture_output=True, text=True, cwd=str(launch_cwd), env=env, timeout=120,
    )
    check("a second subcommand also works", ledger.returncode == 0, ledger.stderr[:200])

    print()
    if failures:
        print(f"{len(failures)} FAILED: " + "; ".join(failures))
        print(f"clone kept for inspection: {clone}")
        return 1
    print("all checks passed")
    shutil.rmtree(workdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ServerDidNotAnswer as exc:
        # A stack trace here would bury the one thing the reader needs. This is
        # the expected shape of a genuine integration failure, not a bug in the
        # harness, so report it the same way as any other failed check.
        print(f"[{FAIL}] the MCP server answered nothing")
        print(f"         {exc}")
        print("\n1 FAILED: the integration does not hold from a fresh clone")
        sys.exit(1)
