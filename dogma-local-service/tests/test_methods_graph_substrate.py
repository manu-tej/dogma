from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from biocursor_service.cli import main
from biocursor_service.methods_graph_substrate import build_methods_graph_substrate


class MethodsGraphSubstrateTests(unittest.TestCase):
    def test_unconfigured_report_is_honest_gap(self) -> None:
        result = build_methods_graph_substrate(env={})

        self.assertEqual(result["status"], "configuration_gap")
        self.assertFalse(result["configured_graph"]["exists"])
        self.assertIn("audited_kuzu_graph", {item["name"] for item in result["authoritative_surface"]})
        self.assertIn("COVERAGE_GAP", "\n".join(result["quration_aspiration"]))
        self.assertIn("Dogma Methods-Graph Substrate", result["markdown"])

    def test_configured_graph_with_lock_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "methods.kuzu"
            db.mkdir()
            (root / "ingest.lock.json").write_text("{}", encoding="utf-8")
            result = build_methods_graph_substrate(env={"DOGMA_METHODS_GRAPH_DB": str(db)})

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["configured_graph"]["env_var"], "DOGMA_METHODS_GRAPH_DB")
        self.assertTrue(result["configured_graph"]["exists"])
        self.assertTrue(result["configured_graph"]["ingest_lock_exists"])

    def test_legacy_biocursor_graph_env_alias_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "methods.kuzu"
            db.mkdir()
            (root / "ingest.lock.json").write_text("{}", encoding="utf-8")
            result = build_methods_graph_substrate(env={"BIOCURSOR_METHODS_GRAPH_DB": str(db)})

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["configured_graph"]["env_var"], "BIOCURSOR_METHODS_GRAPH_DB")

    def test_cli_writes_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "substrate.md"
            exit_code = main(["methods-graph-substrate", "--format", "markdown", "--out", str(out)])
            text = out.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("# Dogma Methods-Graph Substrate", text)
        self.assertIn("Current Guardrail Surface", text)


if __name__ == "__main__":
    unittest.main()
