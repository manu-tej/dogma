from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from biocursor_service.indexer import scan_workspace
from biocursor_service.trust_policy import trust_policy_path, write_trust_policy


OUTPUTS_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = OUTPUTS_ROOT / "dogma-demo-workspace"


class TrustPolicyTests(unittest.TestCase):
    def test_human_data_requires_trust_file(self) -> None:
        result = scan_workspace(DEMO_ROOT)

        self.assertEqual(result["trust"]["status"], "untrusted")
        self.assertFalse(result["trust"]["trusted"])
        self.assertIn("Human data is detected", result["trust"]["blockers"][0])

    def test_write_trust_policy_allows_human_data_operations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for file_name in ["pipeline.nf", "sample_sheet.csv", "intervals.bed", "variants.vcf", "metadata.json"]:
                shutil.copy2(DEMO_ROOT / file_name, root / file_name)

            written = write_trust_policy(root, reason="unit test")
            result = scan_workspace(root)

        self.assertEqual(Path(written["policy_path"]).name, "trust.json")
        self.assertEqual(result["trust"]["status"], "trusted")
        self.assertTrue(result["trust"]["trusted"])
        self.assertEqual(result["trust"]["policy"]["reason"], "unit test")

    def test_non_human_workspace_does_not_require_trust(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "metadata.json").write_text('{"organism":"yeast","reference":{"genome_build":"sacCer3","annotation":"SGD"}}', encoding="utf-8")
            result = scan_workspace(root)

        self.assertEqual(result["trust"]["status"], "not_required")
        self.assertTrue(result["trust"]["trusted"])

    def test_invalid_trust_file_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for file_name in ["pipeline.nf", "sample_sheet.csv", "intervals.bed", "variants.vcf", "metadata.json"]:
                shutil.copy2(DEMO_ROOT / file_name, root / file_name)
            path = trust_policy_path(root)
            path.parent.mkdir(parents=True)
            path.write_text("{not json", encoding="utf-8")

            result = scan_workspace(root)

        self.assertEqual(result["trust"]["status"], "untrusted")
        self.assertIn("not valid JSON", " ".join(result["trust"]["blockers"]))


if __name__ == "__main__":
    unittest.main()
