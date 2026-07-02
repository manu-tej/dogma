from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from biocursor_service.execution_sandbox import build_run_plan_for_workspace, execute_command


OUTPUTS_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = OUTPUTS_ROOT / "dogma-demo-workspace"


class ExecutionSandboxTests(unittest.TestCase):
    def test_demo_workspace_run_plan_is_blocked_but_reviewable(self) -> None:
        plan = build_run_plan_for_workspace(DEMO_ROOT)

        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["error_count"], 3)
        self.assertEqual(plan["trust"]["status"], "untrusted")
        self.assertEqual(plan["commands"][0]["engine"], "nextflow")
        self.assertEqual(plan["commands"][0]["argv"], ["nextflow", "run", "pipeline.nf", "-stub-run"])
        self.assertIn("Human data is detected", plan["commands"][0]["blocked_reason"])
        self.assertFalse(plan["commands"][0]["execution_allowed"])

    def test_execute_defaults_to_preview_without_running(self) -> None:
        result = execute_command(DEMO_ROOT)

        self.assertEqual(result["status"], "preview")
        self.assertFalse(result["executed"])
        self.assertEqual(result["command"]["command"], "nextflow run pipeline.nf -stub-run")

    def test_execute_blocks_when_errors_remain(self) -> None:
        result = execute_command(DEMO_ROOT, execute=True)

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["executed"])
        self.assertIn("Human data is detected", result["message"])

    def test_snakemake_dry_run_plan_is_generated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Snakefile").write_text("rule all:\n    input: []\n", encoding="utf-8")
            plan = build_run_plan_for_workspace(root)

        self.assertEqual(plan["status"], "ready_for_review")
        self.assertEqual(plan["error_count"], 0)
        self.assertEqual(plan["commands"][0]["engine"], "snakemake")
        self.assertEqual(plan["commands"][0]["argv"], ["snakemake", "--snakefile", "Snakefile", "--dry-run", "--printshellcmds"])
        self.assertIn("--dry-run", plan["commands"][0]["command"])


if __name__ == "__main__":
    unittest.main()
