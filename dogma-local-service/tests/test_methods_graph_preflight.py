from __future__ import annotations

import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from dogma_service.methods_graph_preflight import build_methods_graph_preflight


OUTPUTS_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = OUTPUTS_ROOT / "dogma-demo-workspace"


class MethodsGraphPreflightTests(unittest.TestCase):
    def test_reports_configuration_gap_without_audited_graph(self) -> None:
        result = build_methods_graph_preflight(DEMO_ROOT, env={})

        self.assertEqual(result["status"], "configuration_gap")
        self.assertIn("methods_graph.audited_substrate_missing", result["coverage_gaps"])
        self.assertEqual(result["dataset_facts"]["facts"]["replicates_per_group"], 1)
        self.assertIn("m:fastqc", result["method_chain"]["method_ids"])
        self.assertIn("# Dogma Methods-Graph Preflight", result["markdown"])

    def test_runs_configured_methods_graph_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "methods.kuzu"
            db.mkdir()
            (db / "ingest.lock.json").write_text('{"audit":"ok"}\n', encoding="utf-8")
            fake_cli = root / "methods-graph-fake"
            fake_cli.write_text(
                textwrap.dedent(
                    """\
                    #!/usr/bin/env python3
                    import json
                    import sys
                    if "verify-substrate" in sys.argv:
                        print(json.dumps({"schema": 1, "status": "verified", "verified": True, "audit": {"ok": True}, "graph_hash": "sha256:" + "a" * 64, "expected_graph_hash": "sha256:" + "a" * 64}))
                        sys.exit(0)
                    print(json.dumps({
                        "status": "EVALUABLE",
                        "steps": [{"step": "m:fastqc", "status": "EVALUABLE", "method_id": "m:fastqc", "gates": []}],
                        "handoffs": [],
                        "argv": sys.argv[1:],
                    }))
                    """
                ),
                encoding="utf-8",
            )
            os.chmod(fake_cli, 0o755)

            result = build_methods_graph_preflight(
                DEMO_ROOT,
                env={
                    "DOGMA_METHODS_GRAPH_DB": str(db),
                    "DOGMA_METHODS_GRAPH_CLI": str(fake_cli),
                },
            )

        self.assertEqual(result["status"], "evaluable")
        self.assertEqual(result["verdict"]["status"], "EVALUABLE")
        self.assertIn("guardrail-chain", result["command"])
        self.assertIn("--json", result["command"])
        self.assertIn("replicates_per_group=1", result["command"])
        self.assertIn("Continue with Dogma dry-run", " ".join(result["next_actions"]))


if __name__ == "__main__":
    unittest.main()


def test_mixed_known_unknown_chain_never_queries_recognized_subset(tmp_path):
    from unittest.mock import patch
    (tmp_path / 'main.nf').write_text("process FASTQC {\n script:\n 'fastqc'\n}\nprocess UNKNOWN_UNBOUND_STEP {\n script:\n 'unknown'\n}\n")
    with patch('dogma_service.methods_graph_preflight.build_methods_graph_substrate', return_value={
        'status': 'ready', 'configured_graph': {'path': '/fixture/methods.kuzu'}}), patch(
        'dogma_service.methods_graph_preflight.run_guardrail_chain') as query:
        result = build_methods_graph_preflight(tmp_path, env={})
    assert result['status'] == 'coverage_gap'
    assert 'm:fastqc' in result['method_chain']['method_ids']
    assert any('UNKNOWN_UNBOUND_STEP' in gap for gap in result['coverage_gaps'])
    query.assert_not_called()
