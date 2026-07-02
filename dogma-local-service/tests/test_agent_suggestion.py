from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from biocursor_service.agent_suggestion import build_agent_suggestion, extract_json_object
from biocursor_service.cli import main


OUTPUTS_ROOT = Path(__file__).resolve().parents[2]
DEMO_ROOT = OUTPUTS_ROOT / "dogma-demo-workspace"


class FakeProvider:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompt = ""

    def create_message(self, prompt: str) -> str:
        self.prompt = prompt
        return self.response


class AgentSuggestionTests(unittest.TestCase):
    def test_prompt_ready_without_llm(self) -> None:
        result = build_agent_suggestion(DEMO_ROOT, instruction="Fix the sample sheet safely.", max_files=20)

        self.assertEqual(result["status"], "prompt_ready")
        self.assertFalse(result["llm_executed"])
        self.assertIn("Fix the sample sheet safely.", result["prompt"])
        self.assertIn("sample_sheet.duplicate_sample_id", result["prompt"])
        self.assertIn("methods_graph_preflight", result["prompt"])
        self.assertIn("methods_graph_preflight", result)
        self.assertIn("Do not treat methods-graph coverage gaps as resolved", " ".join(result["suggestion"]["must_not_do"]))
        self.assertIn("# Dogma Agent Suggestion", result["markdown"])
        self.assertIn("## methods-graph Preflight", result["markdown"])
        self.assertNotIn("SYN_001", json.dumps(result, sort_keys=True))

    def test_methods_graph_preflight_gaps_drive_prompt_ready_actions(self) -> None:
        fake_preflight = {
            "service": "dogma-local-service",
            "status": "configuration_gap",
            "substrate_status": "configuration_gap",
            "verdict": {"status": "not_evaluable"},
            "method_chain": {"method_ids": ["nfcore.rnaseq.star_salmon"], "steps": []},
            "dataset_facts": {"facts": {"assay": "rna_seq"}},
            "coverage_gaps": ["methods_graph.audited_substrate_missing"],
            "next_actions": ["Configure DOGMA_METHODS_GRAPH_DB before execution."],
        }
        with patch("biocursor_service.agent_suggestion.build_methods_graph_preflight", return_value=fake_preflight):
            result = build_agent_suggestion(DEMO_ROOT, instruction="Plan with guardrails.", max_files=20)

        self.assertIn("methods_graph.audited_substrate_missing", result["prompt"])
        self.assertIn("nfcore.rnaseq.star_salmon", result["prompt"])
        self.assertIn("methods_graph.audited_substrate_missing", result["methods_graph_preflight"]["coverage_gaps"])
        self.assertTrue(any(action["kind"] == "guardrail" for action in result["suggestion"]["next_actions"]))
        self.assertIn("Configure DOGMA_METHODS_GRAPH_DB", json.dumps(result["suggestion"]["next_actions"]))
        self.assertIn("methods_graph.audited_substrate_missing", result["markdown"])

    def test_editor_context_is_redacted_and_included_in_prompt(self) -> None:
        result = build_agent_suggestion(
            DEMO_ROOT,
            instruction="Explain the selected sample row.",
            max_files=20,
            editor_context={
                "path": "sample_sheet.csv",
                "language_id": "csv",
                "selection": {"start": {"line": 2, "character": 1}, "end": {"line": 2, "character": 22}},
                "selected_text": "SYN_001,control,reads/SYN_001_R1.fastq.gz",
                "current_line": "SYN_001,control,reads/SYN_001_R1.fastq.gz",
            },
        )

        self.assertIn("active_editor", result["prompt"])
        self.assertEqual(result["editor_context"]["path"], "sample_sheet.csv")
        self.assertTrue(result["editor_context"]["redaction"]["sample_ids_redacted"])
        self.assertIn("<sample:1>", result["prompt"])
        self.assertNotIn("SYN_001", result["prompt"])
        self.assertNotIn("SYN_001", json.dumps(result, sort_keys=True))

    def test_fake_provider_json_suggestion(self) -> None:
        provider = FakeProvider(
            json.dumps(
                {
                    "status": "blocked",
                    "summary": "Resolve duplicate samples before execution.",
                    "highest_risks": ["duplicate sample_id"],
                    "next_actions": [
                        {
                            "kind": "patch_preview",
                            "title": "Preview sample validation patch",
                            "proposal_id": "nextflow-sample-validation-1",
                        }
                    ],
                    "must_not_do": ["do not execute real workflow"],
                }
            )
        )

        result = build_agent_suggestion(
            DEMO_ROOT,
            instruction="What next?",
            max_files=20,
            use_llm=True,
            provider_name="claude_subscription",
            provider=provider,
        )

        self.assertEqual(result["status"], "llm_completed")
        self.assertTrue(result["llm_executed"])
        self.assertEqual(result["suggestion"]["summary"], "Resolve duplicate samples before execution.")
        self.assertIn("What next?", provider.prompt)
        self.assertIn("methods_graph_preflight", provider.prompt)

    def test_unstructured_provider_output_is_reported(self) -> None:
        result = build_agent_suggestion(
            DEMO_ROOT,
            instruction="What next?",
            max_files=20,
            use_llm=True,
            provider_name="claude_subscription",
            provider=FakeProvider("not json"),
        )

        self.assertEqual(result["status"], "llm_unstructured")
        self.assertTrue(result["llm_executed"])

    def test_not_configured_when_llm_requested_without_provider(self) -> None:
        result = build_agent_suggestion(
            DEMO_ROOT,
            instruction="What next?",
            max_files=20,
            use_llm=True,
            provider_name="none",
        )

        self.assertEqual(result["status"], "llm_not_configured")
        self.assertFalse(result["llm_executed"])

    def test_extract_json_object_accepts_wrapped_json(self) -> None:
        parsed = extract_json_object("Result:\n```json\n{\"status\":\"blocked\"}\n```")
        self.assertEqual(parsed, {"status": "blocked"})

    def test_cli_writes_agent_suggestion_markdown(self) -> None:
        out = Path("/tmp/biocursor-agent-suggestion-test.md")
        try:
            exit_code = main(["agent-suggestion", str(DEMO_ROOT), "--instruction", "Plan next action", "--format", "markdown", "--out", str(out)])
            self.assertEqual(exit_code, 0)
            text = out.read_text(encoding="utf-8")
            self.assertIn("# Dogma Agent Suggestion", text)
            self.assertIn("Plan next action", text)
        finally:
            out.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
