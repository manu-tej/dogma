from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from biocursor_service.cli import main
from biocursor_service.evidence_ledger import build_evidence_ledger


OUTPUTS_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = OUTPUTS_ROOT / "dogma-demo-workspace"


class EvidenceLedgerTests(unittest.TestCase):
    def test_demo_workspace_ledger_records_facts_without_verdicts(self) -> None:
        result = build_evidence_ledger(DEMO_ROOT)
        entry_types = {item["type"] for item in result["entries"]}

        self.assertEqual(result["service"], "dogma-local-service")
        self.assertFalse(result["invariants"]["stores_biological_verdicts"])
        self.assertFalse(result["invariants"]["stores_confidence_grades"])
        self.assertTrue(result["invariants"]["sample_ids_redacted"])
        self.assertTrue(result["invariants"]["explicit_gates_required"])
        self.assertTrue(result["invariants"]["deterministic_without_timestamp"])
        self.assertIn("workspace_context", entry_types)
        self.assertIn("privacy", entry_types)
        self.assertIn("execution_plan", entry_types)
        self.assertIn("finding", entry_types)
        self.assertIn("guardrail_check", entry_types)
        self.assertIn("patch_proposal", entry_types)
        self.assertGreater(result["summary"]["blocked"], 0)
        self.assertGreater(result["summary"]["gap"], 0)
        self.assertGreater(result["summary"]["preview"], 0)

    def test_ledger_json_is_serializable_without_raw_sample_ids(self) -> None:
        result = build_evidence_ledger(DEMO_ROOT)
        serialized = json.dumps(result, sort_keys=True)

        self.assertNotIn("SYN_001", serialized)
        self.assertNotIn("SYN_003", serialized)
        self.assertIn("<sample:1>", serialized)
        self.assertIn("quration.factual_ledger_not_verdict", serialized)
        self.assertIn("method.container.FASTQC", serialized)

    def test_cli_writes_evidence_ledger_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "evidence-ledger.md"
            exit_code = main(["evidence-ledger", str(DEMO_ROOT), "--format", "markdown", "--out", str(out)])
            text = out.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("# Dogma Evidence Ledger", text)
        self.assertIn("Stores support/refute verdicts: false", text)
        self.assertIn("Requires explicit execution/apply gates: true", text)
        self.assertIn("quration.factual_ledger_not_verdict", text)
        self.assertNotIn("SYN_001", text)


if __name__ == "__main__":
    unittest.main()
