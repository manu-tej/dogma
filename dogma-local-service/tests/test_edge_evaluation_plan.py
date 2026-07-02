from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from biocursor_service.cli import main
from biocursor_service.edge_evaluation_plan import build_edge_evaluation_plan


OUTPUTS_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = OUTPUTS_ROOT / "dogma-demo-workspace"


SELECTED_EDGE = {
    "id": "pipeline.nf:FASTQC->ALIGN_STAR:1",
    "from": "FASTQC",
    "to": "ALIGN_STAR",
    "title": "FASTQC -> ALIGN_STAR",
    "status": "gap",
    "source": "pipeline.nf: inferred call order",
    "facts": {
        "fromMethod": "m:fastqc (sequencing quality control)",
        "toMethod": "m:star (splice-aware RNA-seq alignment)",
        "missingContainers": ["FASTQC", "ALIGN_STAR"],
        "missingMethods": [],
        "assumptions": ["FASTQ reads are paired with declared samples."],
    },
    "nextActions": ["Declare containers before real execution."],
}


class EdgeEvaluationPlanTests(unittest.TestCase):
    def test_demo_workspace_builds_typed_edge_plan(self) -> None:
        result = build_edge_evaluation_plan(DEMO_ROOT)
        stages = {item["stage"]: item for item in result["contracts"]}

        self.assertEqual(result["service"], "dogma-local-service")
        self.assertEqual(result["task_class"], "differential_expression")
        self.assertEqual(result["status"], "blocked")
        self.assertIn("condition_transcript_abundance", result["edge"]["id"])
        self.assertEqual(set(stages), {"Readout", "Grounding", "Compose", "Execute", "Interpret"})
        self.assertEqual(stages["Interpret"]["status"], "facts_only")
        self.assertFalse(result["invariants"]["stores_biological_verdicts"])
        self.assertFalse(result["invariants"]["stores_confidence_grades"])
        self.assertTrue(result["invariants"]["coverage_gaps_are_explicit"])
        self.assertIn("methods_graph.audited_substrate_missing", result["coverage_gaps"])
        self.assertIn("workflow.process.FEATURECOUNTS.missing", result["coverage_gaps"])
        self.assertIn("workflow.process.DESEQ2.missing", result["coverage_gaps"])

    def test_selected_workbench_edge_is_preserved_as_plan_scope(self) -> None:
        result = build_edge_evaluation_plan(DEMO_ROOT, selected_edge=SELECTED_EDGE)
        grounding = next(item for item in result["contracts"] if item["stage"] == "Grounding")
        compose = next(item for item in result["contracts"] if item["stage"] == "Compose")

        self.assertEqual(result["edge"]["id"], "pipeline.nf:FASTQC->ALIGN_STAR:1")
        self.assertEqual(result["edge"]["source"], "FASTQC")
        self.assertEqual(result["edge"]["target"], "ALIGN_STAR")
        self.assertEqual(result["selected_edge"]["title"], "FASTQC -> ALIGN_STAR")
        self.assertIn("selected_edge.container.FASTQC.missing", result["coverage_gaps"])
        self.assertIn("selected_edge.container.ALIGN_STAR.missing", result["coverage_gaps"])
        self.assertIn("m:fastqc (sequencing quality control)", grounding["facts"]["method_candidates"])
        self.assertEqual(compose["facts"]["selected_workflow_edge"]["from"], "FASTQC")
        self.assertIn("## Selected Workbench Edge", result["markdown"])
        self.assertIn("Missing containers: FASTQC, ALIGN_STAR", result["markdown"])

    def test_plan_json_is_serializable_without_raw_sample_ids(self) -> None:
        result = build_edge_evaluation_plan(DEMO_ROOT)
        serialized = json.dumps(result, sort_keys=True)

        self.assertNotIn("SYN_001", serialized)
        self.assertNotIn("SYN_003", serialized)
        self.assertIn("Readout", serialized)
        self.assertIn("Grounding", serialized)
        self.assertIn("facts_only", serialized)

    def test_selected_edge_payload_redacts_raw_sample_ids(self) -> None:
        selected = dict(SELECTED_EDGE)
        selected["title"] = "FASTQC -> SYN_001"
        selected["facts"] = {**SELECTED_EDGE["facts"], "assumptions": ["SYN_003 has paired FASTQ reads."]}
        result = build_edge_evaluation_plan(DEMO_ROOT, selected_edge=selected)
        serialized = json.dumps(result, sort_keys=True)

        self.assertNotIn("SYN_001", serialized)
        self.assertNotIn("SYN_003", serialized)
        self.assertIn("<sample:1>", serialized)
        self.assertIn("<sample:2>", serialized)

    def test_selected_biological_edge_preserves_methods_graph_grounding(self) -> None:
        selected = {
            "id": "bioedge.condition_transcript_abundance",
            "from": "control vs treatment",
            "to": "transcript abundance",
            "title": "control vs treatment -> transcript abundance",
            "edge_type": "biological",
            "relation": "changes",
            "question": "Does control vs treatment change transcript abundance?",
            "facts": {
                "readout": "transcript abundance",
                "methodCandidates": ["m:deseq2"],
                "coverageGaps": [],
                "methodsGraphGrounding": {
                    "status": "grounded",
                    "chosen_method_ids": ["m:deseq2"],
                    "suggestions": [{"module_id": "mod:deseq2", "chosen_executor": {"method_id": "m:deseq2"}}],
                    "preconditions": [{"method_id": "m:deseq2", "diagnostics": [{"id": "diag:replicate_count"}]}],
                    "coverage_gaps": [],
                },
                "methodsGraphSuggestions": [{"module_id": "mod:deseq2"}],
                "methodsGraphPreconditions": [{"method_id": "m:deseq2"}],
            },
        }
        result = build_edge_evaluation_plan(DEMO_ROOT, selected_edge=selected)
        grounding = next(item for item in result["contracts"] if item["stage"] == "Grounding")

        self.assertEqual(result["selected_edge"]["edge_type"], "biological")
        self.assertEqual(grounding["facts"]["methods_graph_grounding"]["status"], "grounded")
        self.assertIn("m:deseq2", grounding["facts"]["method_candidates"])
        self.assertIn("Methods-graph grounding: grounded", result["markdown"])

    def test_cli_writes_edge_plan_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "edge-evaluation-plan.md"
            exit_code = main(
                [
                    "edge-evaluation-plan",
                    str(DEMO_ROOT),
                    "--format",
                    "markdown",
                    "--selected-edge-json",
                    json.dumps(SELECTED_EDGE),
                    "--out",
                    str(out),
                ]
            )
            text = out.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("# Dogma Edge Evaluation Plan", text)
        self.assertIn("FASTQC -> ALIGN_STAR", text)
        self.assertIn("Readout", text)
        self.assertIn("Stores support/refute verdicts: false", text)
        self.assertIn("methods_graph.audited_substrate_missing", text)


if __name__ == "__main__":
    unittest.main()
