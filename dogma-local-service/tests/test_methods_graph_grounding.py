from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from biocursor_service.indexer import scan_workspace
from biocursor_service.methods_graph_grounding import (
    dataset_format_for_scan,
    ground_edge_with_methods_graph,
)


OUTPUTS_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = OUTPUTS_ROOT / "dogma-demo-workspace"


EDGE = {
    "id": "bioedge.condition_transcript_abundance",
    "source": "control vs treatment",
    "relation": "changes",
    "target": "transcript abundance",
}


class FakeKuzu:
    class Database:
        def __init__(self, path: str, read_only: bool = False) -> None:
            self.path = path
            self.read_only = read_only
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class Connection:
        def __init__(self, db: "FakeKuzu.Database") -> None:
            self.db = db
            self.closed = False

        def close(self) -> None:
            self.closed = True


class FakeSuggestion:
    def to_dict(self) -> dict:
        return {
            "module_id": "mod:deseq2",
            "module_name": "DESeq2 differential expression",
            "chosen_executor": {"method_id": "m:deseq2", "name": "DESeq2", "container": "quay.io/biocontainers/bioconductor-deseq2:1.42"},
            "assumptions": [{"id": "assum:replicates", "name": "sufficient replicates"}],
            "why": "dataset format and edge keywords resolve to DESeq2",
        }


def fake_runtime() -> dict:
    return {
        "kuzu": FakeKuzu,
        "seed_from_edge": lambda conn, edge, dataset_format=None: [dataset_format, "mod:deseq2"],
        "expand": lambda conn, frontier, limit=6: [FakeSuggestion()],
        "method_preconditions": lambda conn, method_id: {
            "method_id": method_id,
            "assumptions": [{"id": "assum:replicates", "checkable": "pre_run"}],
            "diagnostics": [{"id": "diag:replicate_count", "checkable": "pre_run"}],
        },
    }


class MethodsGraphGroundingTests(unittest.TestCase):
    def test_dataset_format_infers_fastq_from_sample_sheet(self) -> None:
        scan = scan_workspace(DEMO_ROOT)
        dataset_format, source = dataset_format_for_scan(scan, env={})

        self.assertEqual(dataset_format, "fmt:format_1930")
        self.assertEqual(source, "heuristic:fastq_edam_format")

    def test_unconfigured_graph_is_coverage_gap(self) -> None:
        scan = scan_workspace(DEMO_ROOT)
        result = ground_edge_with_methods_graph(EDGE, scan, env={})

        self.assertEqual(result["status"], "configuration_gap")
        self.assertIn("methods_graph.audited_substrate_missing", result["coverage_gaps"])
        self.assertTrue(result["advisory_only"])

    def test_ready_graph_missing_runtime_is_dependency_gap(self) -> None:
        scan = scan_workspace(DEMO_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "methods.kuzu"
            db.mkdir()
            (Path(tmp) / "ingest.lock.json").write_text("{}", encoding="utf-8")
            result = ground_edge_with_methods_graph(EDGE, scan, env={"DOGMA_METHODS_GRAPH_DB": str(db)})

        self.assertEqual(result["status"], "dependency_gap")
        self.assertIn("methods_graph.python_dependency_missing", result["coverage_gaps"])

    def test_ready_graph_with_runtime_returns_grounded_suggestions(self) -> None:
        scan = scan_workspace(DEMO_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "methods.kuzu"
            db.mkdir()
            (Path(tmp) / "ingest.lock.json").write_text("{}", encoding="utf-8")
            result = ground_edge_with_methods_graph(
                EDGE,
                scan,
                env={"DOGMA_METHODS_GRAPH_DB": str(db)},
                runtime=fake_runtime(),
            )

        self.assertEqual(result["status"], "grounded")
        self.assertEqual(result["frontier"], ["fmt:format_1930", "mod:deseq2"])
        self.assertEqual(result["chosen_method_ids"], ["m:deseq2"])
        self.assertEqual(result["preconditions"][0]["diagnostics"][0]["id"], "diag:replicate_count")
        self.assertEqual(result["coverage_gaps"], [])


if __name__ == "__main__":
    unittest.main()
