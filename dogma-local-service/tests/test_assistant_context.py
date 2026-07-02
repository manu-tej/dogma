from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from biocursor_service.assistant_context import build_assistant_context
from biocursor_service.cli import main
from biocursor_service.trust_policy import write_trust_policy


OUTPUTS_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = OUTPUTS_ROOT / "dogma-demo-workspace"


class AssistantContextTests(unittest.TestCase):
    def test_untrusted_human_data_redacts_sample_ids(self) -> None:
        result = build_assistant_context(DEMO_ROOT)
        serialized = json.dumps(result, sort_keys=True)

        self.assertEqual(result["trust"]["status"], "untrusted")
        self.assertTrue(result["redaction"]["sample_ids_redacted"])
        self.assertIn("<sample:1>", result["markdown"])
        self.assertIn("GRCh38", result["markdown"])
        self.assertIn("sample_sheet.duplicate_sample_id", result["markdown"])
        self.assertNotIn("SYN_001", serialized)
        self.assertNotIn("SYN_003", serialized)

    def test_trusted_human_data_can_include_sample_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for file_name in ["pipeline.nf", "sample_sheet.csv", "intervals.bed", "variants.vcf", "metadata.json"]:
                shutil.copy2(DEMO_ROOT / file_name, root / file_name)
            write_trust_policy(root, reason="unit test")
            result = build_assistant_context(root)

        self.assertEqual(result["trust"]["status"], "trusted")
        self.assertFalse(result["redaction"]["sample_ids_redacted"])
        self.assertIn("SYN_001", json.dumps(result, sort_keys=True))

    def test_cli_writes_assistant_context_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "assistant-context.json"
            exit_code = main(["assistant-context", str(DEMO_ROOT), "--out", str(out)])
            payload = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["redaction"]["sample_ids_redacted"])
        self.assertIn("# Dogma Assistant Context Bundle", payload["markdown"])
        self.assertNotIn("SYN_001", json.dumps(payload, sort_keys=True))

    def test_cli_writes_assistant_context_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "assistant-context.md"
            exit_code = main(["assistant-context", str(DEMO_ROOT), "--format", "markdown", "--out", str(out)])
            text = out.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("Sample IDs redacted: true", text)
        self.assertIn("<sample:1>", text)
        self.assertNotIn("SYN_001", text)


if __name__ == "__main__":
    unittest.main()
