from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dogma_service.cli import main
from dogma_service.quration_handoff import build_quration_handoff


OUTPUTS_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = OUTPUTS_ROOT / "dogma-demo-workspace"


class QurationHandoffTests(unittest.TestCase):
    def test_handoff_exports_quration_shaped_contracts_without_verdicts(self) -> None:
        result = build_quration_handoff(DEMO_ROOT)

        self.assertEqual(result["contract_version"], "quration-handoff.v1")
        self.assertTrue(result["invariants"]["dogma_monorepo_is_canonical"])
        self.assertTrue(result["invariants"]["dogma_web_ui_is_canonical_graph_surface"])
        self.assertTrue(result["invariants"]["quration_is_compatibility_namespace"])
        self.assertFalse(result["invariants"]["stores_biological_verdicts"])
        self.assertFalse(result["invariants"]["stores_confidence_grades"])
        self.assertEqual(result["quration_import"]["frontend_url"], "http://localhost:3000/canvas")
        self.assertEqual(result["quration_import"]["api_url"], "http://localhost:8000")
        self.assertEqual(
            result["quration_import"]["import_endpoint"],
            "http://localhost:8000/hypothesis/build",
        )
        self.assertEqual(
            result["quration_import"]["requires_adapter"],
            "causal_graph_to_seed_skeleton",
        )
        self.assertEqual(result["quration_import"]["status"], "adapter_ready_for_seed_import")
        self.assertTrue(result["quration_import"]["handoff_json_path"].endswith(".dogma/quration-handoff.json"))

        graph = result["causal_graph"]
        self.assertIn("nodes", graph)
        self.assertIn("edges", graph)
        self.assertGreaterEqual(len(graph["nodes"]), 1)
        self.assertEqual(graph["edges"][0]["state"], "untested")
        self.assertEqual(graph["edges"][0]["confidence"], 0.0)
        self.assertEqual(graph["edges"][0]["validation_status"], "unvalidated")

        plan = result["evaluation_plans"][0]
        self.assertEqual(plan["edge_id"], graph["edges"][0]["id"])
        self.assertIn(plan["ideal_readout"]["modality"], {"transcript", "phenotype", "unknown"})
        self.assertEqual(plan["expected_direction"], "unknown")
        self.assertIn("coverage_gaps", plan["resolver_provenance"])

        record = result["evidence_records"][0]
        self.assertEqual(record["edge_id"], plan["edge_id"])
        self.assertEqual(record["directness"], "not_evaluable")
        self.assertEqual(record["provenance"]["kind"], "resolver")
        self.assertNotIn("supports", json.dumps(result, sort_keys=True).lower())
        self.assertNotIn("refutes", json.dumps(result, sort_keys=True).lower())
        self.assertNotIn("SYN_001", json.dumps(result, sort_keys=True))
        self.assertIn("# Dogma Graph Handoff (quration compatibility)", result["markdown"])
        self.assertIn("## Graph Import (quration compatibility)", result["markdown"])
        self.assertEqual(result["quration_contract"]["repo"], "https://github.com/manu-tej/dogma")

    def test_cli_writes_quration_handoff_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            json_out = Path(tmp) / "quration-handoff.json"
            markdown_out = Path(tmp) / "quration-handoff.md"
            json_exit = main(["quration-handoff", str(DEMO_ROOT), "--out", str(json_out)])
            markdown_exit = main(["quration-handoff", str(DEMO_ROOT), "--format", "markdown", "--out", str(markdown_out)])
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            markdown = markdown_out.read_text(encoding="utf-8")

        self.assertEqual(json_exit, 0)
        self.assertEqual(markdown_exit, 0)
        self.assertEqual(payload["service"], "dogma-local-service")
        self.assertIn("causal_graph", payload)
        self.assertIn("quration_import", payload)
        self.assertIn("# Dogma Graph Handoff (quration compatibility)", markdown)
        self.assertIn("Graph UI: http://localhost:3000/canvas", markdown)


if __name__ == "__main__":
    unittest.main()
