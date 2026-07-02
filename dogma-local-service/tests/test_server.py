from __future__ import annotations

import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from biocursor_service.server import make_server


OUTPUTS_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = OUTPUTS_ROOT / "dogma-demo-workspace"


def request_json(url: str, payload: dict | None = None) -> dict:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = make_server(DEMO_ROOT, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def test_health_scan_and_context_endpoints(self) -> None:
        health = request_json(f"{self.base_url}/health")
        self.assertEqual(health["status"], "ok")

        scan = request_json(f"{self.base_url}/scan")
        self.assertEqual(scan["summary"]["risk_level"], "blocked")
        self.assertTrue(any(issue["code"] == "sample_sheet.duplicate_sample_id" for issue in scan["issues"]))

        context = request_json(f"{self.base_url}/context")
        self.assertEqual(context["summary"]["samples"], 3)
        self.assertIn("workflow_processes", context["context"])

        run_plan = request_json(f"{self.base_url}/run-plan")
        self.assertEqual(run_plan["status"], "blocked")
        self.assertEqual(run_plan["commands"][0]["engine"], "nextflow")

        assistant_context = request_json(f"{self.base_url}/assistant-context")
        self.assertTrue(assistant_context["redaction"]["sample_ids_redacted"])
        self.assertIn("<sample:1>", assistant_context["markdown"])
        self.assertNotIn("SYN_001", json.dumps(assistant_context, sort_keys=True))

        guardrails = request_json(f"{self.base_url}/guardrails")
        self.assertIn("quration.factual_ledger_not_verdict", {item["code"] for item in guardrails["checks"]})
        self.assertIn("method.container.FASTQC", {item["code"] for item in guardrails["checks"]})
        self.assertIn("# Dogma Method Guardrails", guardrails["markdown"])
        self.assertNotIn("SYN_001", json.dumps(guardrails, sort_keys=True))

        ledger = request_json(f"{self.base_url}/evidence-ledger")
        self.assertIn("# Dogma Evidence Ledger", ledger["markdown"])
        self.assertIn("workspace-context", {item["id"] for item in ledger["entries"]})
        self.assertIn("privacy-boundary", {item["id"] for item in ledger["entries"]})
        self.assertIn("quration.factual_ledger_not_verdict", json.dumps(ledger, sort_keys=True))
        self.assertNotIn("SYN_001", json.dumps(ledger, sort_keys=True))

        edge_plan = request_json(f"{self.base_url}/edge-evaluation-plan")
        self.assertEqual(edge_plan["task_class"], "differential_expression")
        self.assertIn("Readout", {item["stage"] for item in edge_plan["contracts"]})
        self.assertIn("# Dogma Edge Evaluation Plan", edge_plan["markdown"])
        self.assertNotIn("SYN_001", json.dumps(edge_plan, sort_keys=True))

        biological_graph = request_json(f"{self.base_url}/biological-graph")
        self.assertEqual(biological_graph["task_class"], "differential_expression")
        self.assertIn("bioedge.condition_transcript_abundance", {item["id"] for item in biological_graph["edges"]})
        self.assertTrue(biological_graph["invariants"]["selected_edges_seed_evaluation_plans"])
        self.assertNotIn("SYN_001", json.dumps(biological_graph, sort_keys=True))

        quration_handoff = request_json(f"{self.base_url}/quration-handoff")
        self.assertEqual(quration_handoff["contract_version"], "quration-handoff.v1")
        self.assertIn("causal_graph", quration_handoff)
        self.assertIn("evaluation_plans", quration_handoff)
        self.assertIn("evidence_records", quration_handoff)
        self.assertEqual(quration_handoff["causal_graph"]["edges"][0]["state"], "untested")
        self.assertNotIn("SYN_001", json.dumps(quration_handoff, sort_keys=True))

        substrate = request_json(f"{self.base_url}/methods-graph-substrate")
        self.assertIn(substrate["status"], {"configuration_gap", "needs_audit_lock", "ready"})
        self.assertIn("audited_kuzu_graph", {item["name"] for item in substrate["authoritative_surface"]})
        self.assertIn("# Dogma Methods-Graph Substrate", substrate["markdown"])

        preflight = request_json(f"{self.base_url}/methods-graph-preflight")
        self.assertEqual(preflight["service"], "dogma-local-service")
        self.assertIn(preflight["status"], {"configuration_gap", "dependency_gap", "coverage_gap", "evaluable", "blocked", "not_evaluable", "query_gap"})
        self.assertIn("# Dogma Methods-Graph Preflight", preflight["markdown"])

        llm = request_json(f"{self.base_url}/llm-status")
        self.assertIn("provider", llm)
        self.assertIn("# Dogma LLM Provider Status", llm["markdown"])

        agent = request_json(f"{self.base_url}/agent-suggestion")
        self.assertEqual(agent["status"], "prompt_ready")
        self.assertIn("# Dogma Agent Suggestion", agent["markdown"])
        self.assertNotIn("SYN_001", json.dumps(agent, sort_keys=True))

        proposals = request_json(f"{self.base_url}/patch-proposals")
        self.assertEqual(proposals["proposal_count"], 2)
        self.assertEqual(proposals["proposals"][0]["target_file"], "pipeline.nf")
        self.assertIn("metadata.missing_sample_id_policy", {item["kind"] for item in proposals["proposals"]})

        trust = request_json(f"{self.base_url}/trust")
        self.assertEqual(trust["trust"]["status"], "untrusted")
        self.assertEqual(trust["trust"]["human_data"], True)

    def test_post_scan_accepts_explicit_root(self) -> None:
        scan = request_json(f"{self.base_url}/scan", {"root": str(DEMO_ROOT), "max_files": 10})
        self.assertEqual(scan["service"], "dogma-local-service")
        self.assertIn("sample_sheet.csv", {item["path"] for item in scan["files"]})

        run_plan = request_json(f"{self.base_url}/run-plan", {"root": str(DEMO_ROOT), "max_files": 10})
        self.assertEqual(run_plan["commands"][0]["command"], "nextflow run pipeline.nf -stub-run")

        assistant_context = request_json(f"{self.base_url}/assistant-context", {"root": str(DEMO_ROOT), "max_files": 10})
        self.assertEqual(assistant_context["service"], "dogma-local-service")
        self.assertTrue(assistant_context["redaction"]["sample_ids_redacted"])

        guardrails = request_json(f"{self.base_url}/guardrails", {"root": str(DEMO_ROOT), "max_files": 10})
        self.assertEqual(guardrails["service"], "dogma-local-service")
        self.assertGreaterEqual(guardrails["summary"]["pass"], 1)

        ledger = request_json(f"{self.base_url}/evidence-ledger", {"root": str(DEMO_ROOT), "max_files": 10})
        self.assertEqual(ledger["service"], "dogma-local-service")
        self.assertTrue(ledger["invariants"]["explicit_gates_required"])

        edge_plan = request_json(f"{self.base_url}/edge-evaluation-plan", {"root": str(DEMO_ROOT), "max_files": 10})
        self.assertEqual(edge_plan["service"], "dogma-local-service")
        self.assertTrue(edge_plan["invariants"]["coverage_gaps_are_explicit"])

        selected_edge_plan = request_json(
            f"{self.base_url}/edge-evaluation-plan",
            {
                "root": str(DEMO_ROOT),
                "max_files": 10,
                "selected_edge": {
                    "id": "pipeline.nf:FASTQC->ALIGN_STAR:1",
                    "from": "FASTQC",
                    "to": "ALIGN_STAR",
                    "title": "FASTQC -> ALIGN_STAR",
                    "status": "gap",
                    "source": "pipeline.nf: inferred call order",
                    "facts": {
                        "fromMethod": "m:fastqc (sequencing quality control)",
                        "toMethod": "m:star (splice-aware RNA-seq alignment)",
                        "missingContainers": ["FASTQC"],
                    },
                },
            },
        )
        self.assertEqual(selected_edge_plan["selected_edge"]["from"], "FASTQC")
        self.assertEqual(selected_edge_plan["edge"]["target"], "ALIGN_STAR")
        self.assertIn("selected_edge.container.FASTQC.missing", selected_edge_plan["coverage_gaps"])

        biological_graph = request_json(f"{self.base_url}/biological-graph", {"root": str(DEMO_ROOT), "max_files": 10})
        self.assertEqual(biological_graph["service"], "dogma-local-service")
        self.assertEqual(biological_graph["edges"][0]["selected_edge"]["edge_type"], "biological")

        quration_handoff = request_json(f"{self.base_url}/quration-handoff", {"root": str(DEMO_ROOT), "max_files": 10})
        self.assertEqual(quration_handoff["service"], "dogma-local-service")
        self.assertEqual(quration_handoff["causal_graph"]["edges"][0]["confidence"], 0.0)
        self.assertTrue(quration_handoff["invariants"]["quration_web_ui_is_canonical"])

        substrate = request_json(f"{self.base_url}/methods-graph-substrate", {})
        self.assertEqual(substrate["service"], "dogma-local-service")

        preflight = request_json(f"{self.base_url}/methods-graph-preflight", {"root": str(DEMO_ROOT), "max_files": 10})
        self.assertEqual(preflight["service"], "dogma-local-service")
        self.assertIn("method_chain", preflight)

        llm = request_json(f"{self.base_url}/llm-status", {})
        self.assertEqual(llm["service"], "dogma-local-service")

        llm_override = request_json(
            f"{self.base_url}/llm-status",
            {
                "provider": "claude_subscription",
                "cli_path": "/definitely/missing/claude",
                "model": "sonnet",
                "timeout_seconds": 180,
            },
        )
        self.assertEqual(llm_override["provider"], "claude_subscription")
        self.assertEqual(llm_override["status"], "needs_claude_login_or_cli")
        self.assertEqual(llm_override["claude_subscription"]["cli_path"], "/definitely/missing/claude")

        agent = request_json(
            f"{self.base_url}/agent-suggestion",
            {
                "root": str(DEMO_ROOT),
                "max_files": 10,
                "instruction": "Suggest a safe next edit.",
                "use_llm": False,
                "editor_context": {
                    "path": "sample_sheet.csv",
                    "language_id": "csv",
                    "selected_text": "SYN_001,control,reads/SYN_001_R1.fastq.gz",
                },
            },
        )
        self.assertEqual(agent["service"], "dogma-local-service")
        self.assertIn("Suggest a safe next edit.", agent["instruction"])
        self.assertEqual(agent["editor_context"]["path"], "sample_sheet.csv")
        self.assertIn("<sample:1>", agent["prompt"])
        self.assertNotIn("SYN_001", json.dumps(agent, sort_keys=True))

        preview = request_json(f"{self.base_url}/execute", {"root": str(DEMO_ROOT), "max_files": 10})
        self.assertEqual(preview["status"], "preview")
        self.assertFalse(preview["executed"])

        patch_preview = request_json(f"{self.base_url}/apply-patch", {"root": str(DEMO_ROOT), "max_files": 10})
        self.assertEqual(patch_preview["status"], "preview")
        self.assertFalse(patch_preview["applied"])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for file_name in ["pipeline.nf", "sample_sheet.csv", "intervals.bed", "variants.vcf", "metadata.json"]:
                shutil.copy2(DEMO_ROOT / file_name, root / file_name)
            trust = request_json(f"{self.base_url}/trust", {"root": str(root), "max_files": 10})

        self.assertEqual(trust["trust"]["status"], "trusted")
        self.assertEqual(trust["write"]["status"], "written")

    def test_post_scan_rejects_missing_root(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as caught:
            request_json(f"{self.base_url}/scan", {"root": str(DEMO_ROOT / "missing")})
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()


if __name__ == "__main__":
    unittest.main()
