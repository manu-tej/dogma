"""The bench journal: an append-only record of what actually happened.

Dogma's checks were all stateless. `build_evidence_ledger` re-derives everything
from a filesystem scan per call and declares `deterministic_without_timestamp`,
so the tools could tell you what a workspace looks like *now* and nothing about
what was done to it. Meanwhile the CLI genuinely acts — it runs stub commands
and writes patched files — and then forgets. `execution_sandbox` even carries a
written spec of the missing feature ("Store stdout, stderr, and exit code for
every dry-run or stub-run attempt") printed as advice to the caller in the
payload where the result belongs.

The journal is one file, `<workspace>/.dogma/journal.ndjson`, one JSON object
per line, never rewritten. Standard library only, so it keeps `bin/dogma`'s
zero-install property.

Four properties carry the design, and each rules out an easier version:

1. **Two halves, kept apart.** Entries the *service* observed are written by the
   function that did the thing, on its success path, and cannot be produced by
   any tool a caller can reach. Entries an *agent* reports are marked
   ``self_reported: true``. Collapsing them would let an agent write "I ran the
   pipeline" into the same record that means a pipeline ran.

2. **No output bytes, ever.** Only ``sha256`` and byte counts. Redaction in this
   codebase runs when ``human_data and not trusted``
   (``assistant_context.py``), but execution *requires* trusted — so every
   machine entry would be written in the un-redacted regime. A digest still
   proves "this is the same output as last time" without the record becoming a
   copy of possibly-human data.

3. **The clock belongs to the service.** ``recorded_at`` is stamped here and a
   caller-supplied value is rejected rather than ignored. A record whose
   timestamps the writer chose is not evidence of ordering.

4. **Corrections supersede; nothing is erased.** A later entry may name an
   earlier ``entry_id`` in ``supersedes``. The mistake stays legible, which is
   the one convention from paper notebooks worth keeping.

Deliberately absent: signatures, DOIs, a hash chain, and any compliance claim.
A ``prev``-hash chain sounds appealing and is wrong here — it needs
read-modify-write, so two ``bin/dogma`` invocations race, and its commonest
break is an ordinary merge, which trains readers to ignore the one integrity
signal. ``entry_id`` is self-contained instead: concatenating two journals is a
valid merge.

The falsifiable test for anything added later: *does this record something that
happened, or does it assert standing?*
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

JOURNAL_RELATIVE_PATH = Path(".dogma") / "journal.ndjson"

#: Written by the service itself, on the success path of the function that acted.
#: No caller-reachable tool can emit one.
MACHINE_KINDS = frozenset({"stub_run", "dry_run", "patch_applied", "trust_granted"})

#: Reported by an agent or a person. Always carries ``self_reported: true``.
SELF_REPORTED_KINDS = frozenset({"decision", "disposition", "note"})

KNOWN_KINDS = MACHINE_KINDS | SELF_REPORTED_KINDS


class JournalError(RuntimeError):
    """A journal write could not be completed. Never swallowed: a record with
    silent gaps is worse than no record, because the gaps are invisible."""


def journal_path(root: str | Path) -> Path:
    return Path(root).expanduser().resolve() / JOURNAL_RELATIVE_PATH


def digest(text: str | bytes | None) -> dict[str, Any]:
    """A content fingerprint that is not the content.

    Enough to answer "did this change?" and "is this the same run?" without the
    journal becoming a copy of output that may contain human sample identifiers.
    """
    if text is None:
        return {"sha256": None, "bytes": 0}
    raw = text.encode("utf-8") if isinstance(text, str) else text
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def _entry_id(body: dict[str, Any]) -> str:
    """Self-contained identity: a hash of this entry alone.

    Not a chain. A chain would make concatenating two journals — the shape an
    ordinary merge takes — look like corruption.
    """
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _ensure_dogma_dir(root: Path) -> Path:
    """Create `.dogma/` and, on first use, a `.gitignore` that keeps the journal
    tracked while keeping the local trust grant out of version control.

    The journal is a record of the analysis and belongs with it. `trust.json` is
    a statement about one machine and does not.
    """
    directory = (root / JOURNAL_RELATIVE_PATH).parent
    directory.mkdir(parents=True, exist_ok=True)
    gitignore = directory / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(
            "# The journal is part of the analysis record and is meant to be\n"
            "# committed. The trust grant describes one machine, and is not.\n"
            "trust.json\n",
            encoding="utf-8",
        )
    return directory


def append(
    root: str | Path,
    kind: str,
    body: dict[str, Any],
    *,
    agent: str | None = None,
    supersedes: str | None = None,
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Append one entry and return it. The only way to write to the journal.

    ``recorded_at`` exists solely to be rejected. Accepting a caller's timestamp
    would make ordering a claim rather than an observation; failing loudly is
    what tells a caller that.
    """
    if recorded_at is not None:
        raise JournalError(
            "recorded_at is stamped by the service and cannot be supplied. A "
            "record whose timestamps its writer chose is not evidence of order."
        )
    if kind not in KNOWN_KINDS:
        raise JournalError(f"unknown journal kind {kind!r}; known: {sorted(KNOWN_KINDS)}")

    self_reported = kind in SELF_REPORTED_KINDS
    if self_reported and not agent:
        raise JournalError(
            f"a {kind!r} entry is self-reported and must name the agent making the "
            "claim; an unattributed claim cannot be weighed later"
        )
    if not self_reported and agent:
        raise JournalError(
            f"a {kind!r} entry is observed by the service; naming an agent would "
            "imply the agent produced it"
        )

    root_path = Path(root).expanduser().resolve()
    _ensure_dogma_dir(root_path)

    entry: dict[str, Any] = {
        "kind": kind,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "self_reported": self_reported,
        "body": body,
    }
    if agent:
        # Caller-supplied and therefore a claim, not an attestation. Kept beside
        # `self_reported` so no reader can mistake one for the other.
        entry["agent"] = agent
    if supersedes:
        entry["supersedes"] = supersedes
    entry["entry_id"] = _entry_id(entry)

    line = json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n"
    path = root_path / JOURNAL_RELATIVE_PATH
    # O_RDWR so the last byte can be inspected under the same lock as the write.
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
        except OSError as exc:
            # Refuse rather than write unlocked. Two `bin/dogma` invocations can
            # be appending at once, and an interleaved half-line is a corrupt
            # record that reads as a missing one.
            raise JournalError(f"could not lock {path}: {exc}") from exc

        # If a previous process died mid-append, the file ends without a
        # newline. Appending straight onto it would splice this entry into the
        # torn one and lose BOTH — one crash silently costing two records. The
        # separator is written under the same lock, so no concurrent append can
        # land between the check and the write.
        size = os.lseek(fd, 0, os.SEEK_END)
        if size:
            os.lseek(fd, size - 1, os.SEEK_SET)
            if os.read(fd, 1) != b"\n":
                os.write(fd, b"\n")

        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    return entry


def read(root: str | Path) -> list[dict[str, Any]]:
    """Every entry, in file order. Absent journal reads as empty, not as an error."""
    return list(iter_entries(root))


def iter_entries(root: str | Path) -> Iterator[dict[str, Any]]:
    path = journal_path(root)
    if not path.is_file():
        return
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except json.JSONDecodeError:
                # A torn final line means a process died mid-append. Skipping it
                # keeps the rest readable; `summary()` counts it so the damage is
                # reported rather than hidden.
                continue


def _unreadable_line_count(root: str | Path) -> int:
    path = journal_path(root)
    if not path.is_file():
        return 0
    bad = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError:
                bad += 1
    return bad


def summary(root: str | Path) -> dict[str, Any]:
    """What this journal contains, split by who is asserting it."""
    entries = read(root)
    by_kind: dict[str, int] = {}
    for entry in entries:
        by_kind[entry.get("kind", "?")] = by_kind.get(entry.get("kind", "?"), 0) + 1

    observed = [e for e in entries if not e.get("self_reported")]
    reported = [e for e in entries if e.get("self_reported")]
    superseded = {e["supersedes"] for e in entries if e.get("supersedes")}

    return {
        "path": str(journal_path(root)),
        "present": journal_path(root).is_file(),
        "entries": len(entries),
        "by_kind": by_kind,
        "service_observed": len(observed),
        "self_reported": len(reported),
        "superseded_entries": len(superseded),
        "unreadable_lines": _unreadable_line_count(root),
        "first_recorded_at": entries[0]["recorded_at"] if entries else None,
        "last_recorded_at": entries[-1]["recorded_at"] if entries else None,
        "invariants": {
            "append_only": True,
            "output_bytes_persisted": False,
            "timestamps_are_service_stamped": True,
            "self_reported_entries_are_marked": True,
        },
    }
