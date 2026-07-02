from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from biocursor_service.patch_proposals import apply_patch_proposal, build_patch_proposals
from biocursor_service.trust_policy import write_trust_policy


OUTPUTS_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = OUTPUTS_ROOT / "dogma-demo-workspace"


class PatchProposalTests(unittest.TestCase):
    def test_builds_nextflow_sample_validation_proposal(self) -> None:
        result = build_patch_proposals(DEMO_ROOT)

        self.assertEqual(result["proposal_count"], 2)
        self.assertEqual(result["methods_graph_preflight"]["status"], "configuration_gap")
        self.assertIn("methods_graph.audited_substrate_missing", result["methods_graph_preflight"]["coverage_gaps"])
        proposal = result["proposals"][0]
        self.assertEqual(proposal["kind"], "nextflow.sample_sheet_validation")
        self.assertEqual(proposal["target_file"], "pipeline.nf")
        self.assertIn("def validateSampleRow", proposal["after"])
        self.assertIn(".map { row -> validateSampleRow(row) }", proposal["after"])
        self.assertIn("--- a/pipeline.nf", proposal["diff"])
        self.assertFalse(proposal["safety"]["auto_apply"])

    def test_builds_metadata_sample_id_policy_proposal(self) -> None:
        result = build_patch_proposals(DEMO_ROOT)
        proposal = next(item for item in result["proposals"] if item["kind"] == "metadata.missing_sample_id_policy")

        self.assertEqual(proposal["target_file"], "metadata.json")
        self.assertIn("sample_id_policy", proposal["after"])
        self.assertIn("de-identified", proposal["after"])
        self.assertIn("--- a/metadata.json", proposal["diff"])
        self.assertEqual(proposal["safety"]["scope"], "single-file metadata JSON edit")

    def test_apply_patch_defaults_to_preview(self) -> None:
        result = apply_patch_proposal(DEMO_ROOT)

        self.assertEqual(result["status"], "preview")
        self.assertFalse(result["applied"])
        self.assertEqual(result["proposal"]["target_file"], "pipeline.nf")
        self.assertEqual(result["methods_graph_preflight"]["status"], "configuration_gap")
        self.assertIn("methods_graph.audited_substrate_missing", result["methods_graph_preflight"]["coverage_gaps"])

    def test_apply_patch_requires_explicit_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for file_name in ["pipeline.nf", "sample_sheet.csv", "intervals.bed", "variants.vcf", "metadata.json"]:
                shutil.copy2(DEMO_ROOT / file_name, root / file_name)
            write_trust_policy(root, reason="test trust")

            result = apply_patch_proposal(root, apply=True)
            patched = (root / "pipeline.nf").read_text(encoding="utf-8")

        self.assertEqual(result["status"], "applied")
        self.assertTrue(result["applied"])
        self.assertIn("def validateSampleRow", patched)
        self.assertIn(".map { row -> validateSampleRow(row) }", patched)

    def test_apply_specific_metadata_policy_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for file_name in ["pipeline.nf", "sample_sheet.csv", "intervals.bed", "variants.vcf", "metadata.json"]:
                shutil.copy2(DEMO_ROOT / file_name, root / file_name)
            write_trust_policy(root, reason="test trust")

            result = apply_patch_proposal(root, proposal_id="metadata-sample-id-policy-1", apply=True)
            metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "applied")
        self.assertTrue(result["applied"])
        self.assertEqual(result["proposal"]["kind"], "metadata.missing_sample_id_policy")
        self.assertIn("sample_id_policy", metadata["samples"])
        self.assertIn("de-identified", metadata["samples"]["sample_id_policy"])

    def test_apply_patch_blocks_untrusted_human_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for file_name in ["pipeline.nf", "sample_sheet.csv", "intervals.bed", "variants.vcf", "metadata.json"]:
                shutil.copy2(DEMO_ROOT / file_name, root / file_name)

            result = apply_patch_proposal(root, apply=True)

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["applied"])
        self.assertEqual(result["trust"]["status"], "untrusted")

    def test_no_nextflow_proposal_after_patch_is_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for file_name in ["pipeline.nf", "sample_sheet.csv", "intervals.bed", "variants.vcf", "metadata.json"]:
                shutil.copy2(DEMO_ROOT / file_name, root / file_name)
            write_trust_policy(root, reason="test trust")
            apply_patch_proposal(root, apply=True)

            result = build_patch_proposals(root)

        self.assertFalse(any(item["kind"] == "nextflow.sample_sheet_validation" for item in result["proposals"]))
        self.assertTrue(any(item["kind"] == "metadata.missing_sample_id_policy" for item in result["proposals"]))


if __name__ == "__main__":
    unittest.main()
