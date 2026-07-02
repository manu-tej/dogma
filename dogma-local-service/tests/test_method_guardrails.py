from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from biocursor_service.cli import main
from biocursor_service.method_guardrails import build_method_guardrails


OUTPUTS_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = OUTPUTS_ROOT / "dogma-demo-workspace"


class MethodGuardrailsTests(unittest.TestCase):
    def test_demo_workspace_guardrails_encode_quration_and_methods_graph_principles(self) -> None:
        result = build_method_guardrails(DEMO_ROOT)
        checks = {item["code"]: item for item in result["checks"]}

        self.assertEqual(result["service"], "dogma-local-service")
        self.assertIn("docs/superpowers/specs", result["sources"]["quration_north_star"])
        self.assertIn("methods-graph", result["sources"]["methods_graph_validator"])
        self.assertGreater(result["summary"]["pass"], 0)
        self.assertGreater(result["summary"]["gap"], 0)
        self.assertGreater(result["summary"]["blocked"], 0)
        self.assertEqual(checks["quration.factual_ledger_not_verdict"]["status"], "pass")
        self.assertEqual(checks["privacy.assistant_context_redaction"]["status"], "pass")
        self.assertEqual(checks["method.grounded.FASTQC"]["status"], "pass")
        self.assertEqual(checks["method.container.FASTQC"]["status"], "gap")
        self.assertEqual(checks["workflow.error_findings_block_execution"]["status"], "blocked")
        self.assertIn("# Dogma Method Guardrails", result["markdown"])
        self.assertIn("facts, never verdicts", result["markdown"])
        self.assertIn("m:fastqc", result["markdown"])

    def test_guardrails_json_is_serializable_without_raw_sample_ids(self) -> None:
        result = build_method_guardrails(DEMO_ROOT)
        serialized = json.dumps(result, sort_keys=True)

        self.assertNotIn("SYN_001", serialized)
        self.assertNotIn("SYN_003", serialized)
        self.assertIn("method.container.ALIGN_STAR", serialized)

    def test_cli_writes_guardrails_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "guardrails.md"
            exit_code = main(["guardrails", str(DEMO_ROOT), "--format", "markdown", "--out", str(out)])
            text = out.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("Dogma Method Guardrails", text)
        self.assertIn("methods-graph", text)
        self.assertIn("workflow.error_findings_block_execution", text)


if __name__ == "__main__":
    unittest.main()
