"""The bench journal, and the check it makes possible.

Dogma acted and forgot. The CLI genuinely runs stub commands and writes patched
files, and every check was re-derived from a filesystem scan with
`deterministic_without_timestamp` set — so the tools could describe a workspace
but never what had been done to it.

The properties below are the ones that would fail silently, and each rules out
an easier version of this feature:

  - Persisting stdout would leak. Redaction runs only when
    `human_data and not trusted`, and execution *requires* trusted, so every
    machine entry would be written in the un-redacted regime.
  - Accepting a caller's timestamp would make ordering a claim.
  - Letting an agent write a machine-kind entry would let it record "the
    pipeline ran" into the field that means a pipeline ran.
  - A shape check that cannot fail is worse than none, so the fabricated-claim
    case is tested directly rather than against a workspace that happens to have
    no such edge.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dogma_service import claim_shape, journal


class JournalTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()


class TestAppendAndRead(JournalTestCase):
    def test_an_entry_round_trips(self):
        journal.append(self.root, "trust_granted", {"policy_path": "p", "reason": "r"})
        entries = journal.read(self.root)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["kind"], "trust_granted")
        self.assertEqual(entries[0]["body"]["reason"], "r")

    def test_entries_accumulate_in_order(self):
        for i in range(3):
            journal.append(self.root, "trust_granted", {"n": i})
        self.assertEqual([e["body"]["n"] for e in journal.read(self.root)], [0, 1, 2])

    def test_an_absent_journal_reads_as_empty_not_an_error(self):
        self.assertEqual(journal.read(self.root), [])
        self.assertFalse(journal.summary(self.root)["present"])

    def test_every_entry_carries_a_self_contained_id(self):
        """Not a chain: concatenating two journals is a valid merge, and a
        `prev`-hash would make that look like corruption."""
        a = journal.append(self.root, "trust_granted", {"n": 1})
        b = journal.append(self.root, "trust_granted", {"n": 2})
        self.assertNotEqual(a["entry_id"], b["entry_id"])
        self.assertEqual(len(a["entry_id"]), 12)

    def test_a_torn_line_does_not_hide_the_rest(self):
        journal.append(self.root, "trust_granted", {"n": 1})
        with journal.journal_path(self.root).open("a") as fh:
            fh.write('{"kind": "trust_gran')  # process died mid-append
        journal.append(self.root, "trust_granted", {"n": 2})
        self.assertEqual(len(journal.read(self.root)), 2)
        self.assertEqual(journal.summary(self.root)["unreadable_lines"], 1)


class TestTheClockBelongsToTheService(JournalTestCase):
    def test_a_caller_supplied_timestamp_is_refused(self):
        """Refused, not ignored. A record whose timestamps its writer chose is
        not evidence of ordering, and silently discarding the value would let a
        caller believe it had been honoured."""
        with self.assertRaises(journal.JournalError) as ctx:
            journal.append(
                self.root, "trust_granted", {}, recorded_at="1999-01-01T00:00:00Z"
            )
        self.assertIn("stamped by the service", str(ctx.exception))

    def test_the_service_stamps_one(self):
        entry = journal.append(self.root, "trust_granted", {})
        self.assertTrue(entry["recorded_at"].endswith("+00:00"))


class TestTheTwoHalvesStayApart(JournalTestCase):
    """Collapsing them would let an agent write "I ran the pipeline" into the
    record that means a pipeline ran."""

    def test_a_machine_entry_is_not_self_reported(self):
        entry = journal.append(self.root, "stub_run", {"return_code": 0})
        self.assertFalse(entry["self_reported"])
        self.assertNotIn("agent", entry)

    def test_a_machine_entry_refuses_an_agent(self):
        with self.assertRaises(journal.JournalError):
            journal.append(self.root, "stub_run", {}, agent="claude-code")

    def test_a_self_reported_entry_is_marked(self):
        entry = journal.append(
            self.root, "decision", {"about": "a"}, agent="claude-code"
        )
        self.assertTrue(entry["self_reported"])
        self.assertEqual(entry["agent"], "claude-code")

    def test_a_self_reported_entry_must_name_its_agent(self):
        """An unattributed claim cannot be weighed later."""
        with self.assertRaises(journal.JournalError):
            journal.append(self.root, "decision", {"about": "a"})

    def test_an_unknown_kind_is_refused(self):
        with self.assertRaises(journal.JournalError):
            journal.append(self.root, "measurement", {}, agent="x")

    def test_measurement_is_not_a_kind(self):
        """The word that would let this record claim something it cannot."""
        self.assertNotIn("measurement", journal.KNOWN_KINDS)
        self.assertNotIn("run", journal.KNOWN_KINDS)


class TestNoOutputBytesArePersisted(JournalTestCase):
    """The privacy property. Redaction runs only when the workspace is
    *untrusted*, and execution requires trusted — so anything persisted from a
    run is written in exactly the regime where the redactor is off."""

    def test_a_digest_is_not_the_content(self):
        secret = "PATIENT-00123 mapped 91.2%"
        d = journal.digest(secret)
        self.assertNotIn("PATIENT", json.dumps(d))
        self.assertEqual(d["bytes"], len(secret.encode()))
        self.assertEqual(len(d["sha256"]), 64)

    def test_the_same_text_digests_the_same(self):
        self.assertEqual(journal.digest("x"), journal.digest("x"))

    def test_different_text_digests_differently(self):
        self.assertNotEqual(journal.digest("x")["sha256"], journal.digest("y")["sha256"])

    def test_none_is_handled(self):
        self.assertEqual(journal.digest(None), {"sha256": None, "bytes": 0})


class TestCorrectionsSupersede(JournalTestCase):
    def test_the_earlier_entry_survives(self):
        first = journal.append(
            self.root, "decision", {"chose": "STAR"}, agent="claude-code"
        )
        journal.append(
            self.root, "decision", {"chose": "salmon"}, agent="claude-code",
            supersedes=first["entry_id"],
        )
        entries = journal.read(self.root)
        self.assertEqual(len(entries), 2, "a correction erased the original")
        self.assertEqual(entries[1]["supersedes"], first["entry_id"])
        self.assertEqual(journal.summary(self.root)["superseded_entries"], 1)


class TestTheGitignoreSplitsRecordFromMachineState(JournalTestCase):
    def test_trust_json_is_ignored_but_the_journal_is_not(self):
        journal.append(self.root, "trust_granted", {})
        text = (self.root / ".dogma" / ".gitignore").read_text()
        self.assertIn("trust.json", text)
        self.assertNotIn("journal.ndjson", text)


class TestTheServiceRecordsWhatItDid(JournalTestCase):
    """The unforgeable half: written inside the function that acted."""

    def test_a_stub_run_is_recorded_without_its_output(self):
        from dogma_service.execution_sandbox import _record_execution

        _record_execution(
            self.root,
            {"id": "nextflow-1", "engine": "nextflow", "mode": "stub-run",
             "argv": ["nextflow", "run", "main.nf", "-stub-run"],
             "workflow_file": "main.nf"},
            return_code=0,
            stdout="PATIENT-00123 aligned 91.2%",
            stderr="",
            duration_seconds=1.5,
            timed_out=False,
        )
        entry = journal.read(self.root)[0]
        self.assertEqual(entry["kind"], "stub_run")
        self.assertFalse(entry["self_reported"])
        self.assertFalse(entry["body"]["executed_real_pipeline"])
        # The property the whole storage design exists for.
        self.assertNotIn("PATIENT", json.dumps(entry))
        self.assertEqual(len(entry["body"]["stdout"]["sha256"]), 64)

    def test_a_dry_run_is_named_a_dry_run(self):
        """Not `run`. `build_command` can only emit `-stub-run` or `--dry-run`,
        so calling either a run overstates it by exactly the margin that
        matters."""
        from dogma_service.execution_sandbox import _record_execution

        _record_execution(
            self.root, {"id": "s1", "engine": "snakemake", "mode": "dry-run", "argv": []},
            return_code=0, stdout="", stderr="", duration_seconds=0.1, timed_out=False,
        )
        self.assertEqual(journal.read(self.root)[0]["kind"], "dry_run")

    def test_a_timeout_is_recorded_too(self):
        """Otherwise the record is quietly optimistic: only runs that finished
        would exist in it."""
        from dogma_service.execution_sandbox import _record_execution

        _record_execution(
            self.root, {"id": "n1", "engine": "nextflow", "mode": "stub-run", "argv": []},
            return_code=None, stdout="", stderr="", duration_seconds=30.0, timed_out=True,
        )
        entry = journal.read(self.root)[0]
        self.assertTrue(entry["body"]["timed_out"])
        self.assertIsNone(entry["body"]["return_code"])

    def test_a_blocked_command_records_nothing(self):
        """Nothing ran, so nothing is recorded. A journal that logged attempts
        as runs would be worse than silent."""
        from dogma_service.execution_sandbox import execute_command

        result = execute_command(self.root, execute=True)
        self.assertFalse(result.get("executed"))
        self.assertEqual(journal.read(self.root), [])

    def test_an_applied_patch_is_recorded_without_the_file_text(self):
        from dogma_service.patch_proposals import _record_patch

        _record_patch(
            self.root,
            {"id": "p1", "target_file": "samplesheet.csv", "rationale": "why"},
            before="sample_id\nPATIENT-00123\n",
            after="sample_id\nPATIENT-00123\nvalidated\n",
        )
        entry = journal.read(self.root)[0]
        self.assertEqual(entry["kind"], "patch_applied")
        self.assertNotIn("PATIENT", json.dumps(entry))
        self.assertNotEqual(
            entry["body"]["before"]["sha256"], entry["body"]["after"]["sha256"]
        )


class TestClaimShape(JournalTestCase):
    """The check the journal exists to make possible."""

    def test_an_edge_claiming_a_measurement_with_no_record_is_reported(self):
        """The case that must fail. Every per-object validator passes on such an
        edge, because each only sees the object in front of it."""
        graph = {"edges": [{"id": "e1", "state": "examined"}]}
        findings = claim_shape._findings_for(graph, [])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["code"], "UNSUPPORTED_MEASUREMENT_CLAIM")
        self.assertEqual(findings[0]["edge_id"], "e1")

    def test_a_stub_run_does_not_support_a_measurement_claim(self):
        """The asymmetry that matters: `build_command` can only ever emit a
        dry-run or a stub-run, so no journal entry can ever support EXAMINED."""
        graph = {"edges": [{"id": "e1", "state": "examined"}]}
        runs = [{"kind": "stub_run", "body": {"return_code": 0, "edge_id": "e1"}}]
        findings = claim_shape._findings_for(graph, runs)
        codes = {f["code"] for f in findings}
        self.assertIn("UNSUPPORTED_MEASUREMENT_CLAIM", codes)
        self.assertFalse(findings[0]["runs_are_measurements"])

    def test_untested_and_assessed_edges_are_not_findings(self):
        """Assessed is the state most real edges legitimately reach."""
        graph = {"edges": [{"id": "a", "state": "untested"}, {"id": "b", "state": "assessed"}]}
        self.assertEqual(claim_shape._findings_for(graph, []), [])

    def test_runs_with_no_edge_are_reported_as_unlinked(self):
        graph = {"edges": []}
        runs = [{"kind": "stub_run", "body": {"return_code": 0}}]
        codes = {f["code"] for f in claim_shape._findings_for(graph, runs)}
        self.assertEqual(codes, {"RUNS_NOT_LINKED_TO_ANY_EDGE"})

    def test_it_emits_no_verdict(self):
        graph = {"edges": [{"id": "e1", "state": "examined"}]}
        blob = json.dumps(claim_shape._findings_for(graph, [])).lower()
        for banned in ("supported", "refuted", "confidence", "score", "pass", "fail"):
            self.assertNotIn(f'"{banned}"', blob)

    def test_the_limitations_are_stated_not_implied(self):
        """A clean result would otherwise read as 'everything was measured'."""
        report = claim_shape.check_claim_shape(self.root, max_files=5)
        joined = " ".join(report["limitations"]).lower()
        self.assertIn("no journal entry can support an examined edge", joined)
        self.assertFalse(report["invariants"]["stores_biological_verdicts"])


if __name__ == "__main__":
    unittest.main()
