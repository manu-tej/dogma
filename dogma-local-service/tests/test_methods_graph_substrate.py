from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dogma_service.cli import main
from dogma_service.methods_graph_substrate import build_methods_graph_substrate


class MethodsGraphSubstrateTests(unittest.TestCase):
    def test_unconfigured_report_is_honest_gap(self) -> None:
        result = build_methods_graph_substrate(env={})

        self.assertEqual(result["status"], "configuration_gap")
        self.assertFalse(result["configured_graph"]["exists"])
        self.assertIn("audited_kuzu_graph", {item["name"] for item in result["authoritative_surface"]})
        self.assertIn("COVERAGE_GAP", "\n".join(result["dogma_execution_aspiration"]))
        self.assertNotIn("quration_repo", result["sources"])
        self.assertEqual(result["sources"]["dogma_repo"], "https://github.com/manu-tej/dogma")
        self.assertIn("Dogma Execution Aspiration", result["markdown"])
        self.assertIn("Dogma Methods-Graph Substrate", result["markdown"])

    def test_empty_ingest_lock_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "methods.kuzu"
            db.mkdir()
            (root / "ingest.lock.json").write_text("{}", encoding="utf-8")
            result = build_methods_graph_substrate(env={"DOGMA_METHODS_GRAPH_DB": str(db)})

        self.assertNotEqual(result["status"], "ready")
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

        self.assertNotEqual(result["status"], "ready")
        self.assertEqual(result["configured_graph"]["env_var"], "BIOCURSOR_METHODS_GRAPH_DB")

    def test_unverified_rebuild_lock_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "methods.kuzu"
            db.touch()
            lock = root / "methods.lock.json"
            lock.write_text('{"graph_hash": "sha256:fixture"}', encoding="utf-8")
            result = build_methods_graph_substrate(env={"QURATION_METHODS_GRAPH_DB": str(db)})

        self.assertNotEqual(result["status"], "ready")
        self.assertEqual(result["configured_graph"]["ingest_lock"], str(lock.resolve()))
        self.assertTrue(result["configured_graph"]["ingest_lock_exists"])
        self.assertIn(str(lock.resolve()), result["markdown"])

    def test_existing_ingest_lock_keeps_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "methods.kuzu"
            db.touch()
            for name in ("ingest.lock.json", "methods.lock.json"):
                (root / name).write_text("{}", encoding="utf-8")
            result = build_methods_graph_substrate(env={"DOGMA_METHODS_GRAPH_DB": str(db)})

        self.assertEqual(result["configured_graph"]["ingest_lock"], str((root / "ingest.lock.json").resolve()))

    def test_graph_file_without_a_lock_remains_a_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db = root / "methods.kuzu"
            db.touch()
            result = build_methods_graph_substrate(env={"DOGMA_METHODS_GRAPH_DB": str(db)})

        self.assertEqual(result["status"], "needs_audit_lock")
        self.assertFalse(result["configured_graph"]["ingest_lock_exists"])

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


def test_injected_verification_requires_semantic_and_exit_agreement(tmp_path):
    import json
    import sys
    from types import SimpleNamespace
    db = tmp_path / 'methods.kuzu'; db.touch()
    (tmp_path / 'methods.lock.json').write_text('{}')
    env = {'DOGMA_METHODS_GRAPH_DB': str(db), 'DOGMA_METHODS_GRAPH_CLI': sys.executable}
    valid = {'schema': 1, 'status': 'verified', 'verified': True, 'audit': {'ok': True},
        'graph_hash': 'sha256:' + 'a' * 64, 'expected_graph_hash': 'sha256:' + 'a' * 64}
    for report, code in [(valid, 1), ({**valid, 'status': 'mismatch'}, 0),
        ({**valid, 'audit': {'ok': False}}, 0), ({**valid, 'graph_hash': 'sha256:x'}, 0), ({}, 0), ([], 0)]:
        result = build_methods_graph_substrate(env, runner=lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(report), returncode=code))
        assert result['status'] != 'ready'
    result = build_methods_graph_substrate(env, runner=lambda *args, **kwargs: SimpleNamespace(stdout=json.dumps(valid), returncode=0))
    assert result['status'] == 'ready'
