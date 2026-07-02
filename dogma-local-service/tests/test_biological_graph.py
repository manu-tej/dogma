from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from biocursor_service.biological_graph import build_biological_graph
from biocursor_service.cli import main
from biocursor_service.edge_evaluation_plan import build_edge_evaluation_plan


OUTPUTS_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = OUTPUTS_ROOT / "dogma-demo-workspace"


class BiologicalGraphTests(unittest.TestCase):
    def test_demo_workspace_builds_biological_edge_graph(self) -> None:
        result = build_biological_graph(DEMO_ROOT)
        edge = result["edges"][0]

        self.assertEqual(result["service"], "dogma-local-service")
        self.assertEqual(result["task_class"], "differential_expression")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("bioedge.condition_transcript_abundance", edge["id"])
        self.assertEqual(edge["relation"], "changes")
        self.assertEqual(edge["target"], "transcript abundance")
        self.assertEqual(edge["selected_edge"]["edge_type"], "biological")
        self.assertEqual(edge["methods_graph_grounding"]["status"], "configuration_gap")
        self.assertIn("methodsGraphGrounding", edge["selected_edge"]["facts"])
        self.assertIn("m:deseq2", edge["selected_edge"]["facts"]["methodCandidates"])
        self.assertIn("methods_graph.audited_substrate_missing", result["coverage_gaps"])
        self.assertFalse(result["invariants"]["stores_biological_verdicts"])
        self.assertTrue(result["invariants"]["selected_edges_seed_evaluation_plans"])

    def test_biological_selected_edge_seeds_edge_evaluation_plan(self) -> None:
        graph = build_biological_graph(DEMO_ROOT)
        selected_edge = graph["edges"][0]["selected_edge"]
        plan = build_edge_evaluation_plan(DEMO_ROOT, selected_edge=selected_edge)

        self.assertEqual(plan["edge"]["id"], "bioedge.condition_transcript_abundance")
        self.assertEqual(plan["edge"]["relation"], "changes")
        self.assertEqual(plan["selected_edge"]["edge_type"], "biological")
        self.assertIn("Selected Biological Edge", plan["markdown"])
        self.assertIn("Methods-graph grounding: configuration_gap", plan["markdown"])
        self.assertIn("Method candidates: m:fastqc, m:star, m:featurecounts, m:deseq2", plan["markdown"])

    def test_graph_json_is_serializable_without_raw_sample_ids(self) -> None:
        result = build_biological_graph(DEMO_ROOT)
        serialized = json.dumps(result, sort_keys=True)

        self.assertNotIn("SYN_001", serialized)
        self.assertNotIn("SYN_003", serialized)
        self.assertIn("sample_ids_redacted", serialized)

    def test_cli_writes_biological_graph_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "biological-graph.md"
            exit_code = main(["biological-graph", str(DEMO_ROOT), "--format", "markdown", "--out", str(out)])
            text = out.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("# Dogma Biological Graph", text)
        self.assertIn("bioedge.condition_transcript_abundance", text)
        self.assertIn("Biological support/refute verdicts are not emitted.", text)


if __name__ == "__main__":
    unittest.main()
