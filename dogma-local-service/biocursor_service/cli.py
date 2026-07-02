"""Command-line interface for the Dogma local companion service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_suggestion import build_agent_suggestion
from .assistant_context import build_assistant_context
from .biological_graph import build_biological_graph
from .edge_evaluation_plan import build_edge_evaluation_plan
from .evidence_ledger import build_evidence_ledger
from .execution_sandbox import build_run_plan_for_workspace, execute_command
from .indexer import scan_workspace
from .llm_provider import build_llm_status
from .method_guardrails import build_method_guardrails
from .methods_graph_preflight import build_methods_graph_preflight
from .methods_graph_substrate import build_methods_graph_substrate
from .mcp_server import run_stdio as run_mcp_stdio
from .patch_proposals import apply_patch_proposal, build_patch_proposals
from .quration_handoff import build_quration_handoff
from .server import serve
from .trust_policy import write_trust_policy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dogma_service", description="Dogma local companion service")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan a bioinformatics workspace and emit JSON.")
    scan_parser.add_argument("root", help="Workspace root to scan.")
    scan_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan.")
    scan_parser.add_argument("--out", help="Optional output path for the JSON scan result.")

    run_plan_parser = subparsers.add_parser("run-plan", help="Generate a safe workflow dry-run/stub-run plan.")
    run_plan_parser.add_argument("root", help="Workspace root to scan.")
    run_plan_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan.")
    run_plan_parser.add_argument("--out", help="Optional output path for the JSON run plan.")

    assistant_parser = subparsers.add_parser("assistant-context", help="Generate a privacy-aware assistant context bundle.")
    assistant_parser.add_argument("root", help="Workspace root to scan.")
    assistant_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan.")
    assistant_parser.add_argument("--format", choices=["json", "markdown"], default="json", help="Output JSON bundle or just the rendered Markdown.")
    assistant_parser.add_argument("--out", help="Optional output path for the assistant context result.")

    guardrails_parser = subparsers.add_parser("guardrails", help="Generate a quration/methods-graph-inspired guardrails report.")
    guardrails_parser.add_argument("root", help="Workspace root to scan.")
    guardrails_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan.")
    guardrails_parser.add_argument("--format", choices=["json", "markdown"], default="json", help="Output JSON bundle or just the rendered Markdown.")
    guardrails_parser.add_argument("--out", help="Optional output path for the guardrails result.")

    ledger_parser = subparsers.add_parser("evidence-ledger", help="Generate a factual Dogma evidence ledger.")
    ledger_parser.add_argument("root", help="Workspace root to scan.")
    ledger_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan.")
    ledger_parser.add_argument("--format", choices=["json", "markdown"], default="json", help="Output JSON bundle or just the rendered Markdown.")
    ledger_parser.add_argument("--out", help="Optional output path for the evidence ledger result.")

    edge_plan_parser = subparsers.add_parser("edge-evaluation-plan", help="Generate a quration-style typed edge evaluation plan.")
    edge_plan_parser.add_argument("root", help="Workspace root to scan.")
    edge_plan_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan.")
    edge_plan_parser.add_argument("--format", choices=["json", "markdown"], default="json", help="Output JSON bundle or just the rendered Markdown.")
    edge_plan_parser.add_argument("--selected-edge-json", help="Optional selected Graph Workbench edge JSON.")
    edge_plan_parser.add_argument("--out", help="Optional output path for the edge evaluation plan result.")

    biological_graph_parser = subparsers.add_parser("biological-graph", help="Generate a factual biological graph for selected-edge planning.")
    biological_graph_parser.add_argument("root", help="Workspace root to scan.")
    biological_graph_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan.")
    biological_graph_parser.add_argument("--format", choices=["json", "markdown"], default="json", help="Output JSON bundle or just the rendered Markdown.")
    biological_graph_parser.add_argument("--out", help="Optional output path for the biological graph result.")

    quration_handoff_parser = subparsers.add_parser("quration-handoff", help="Generate a quration-compatible graph/evidence handoff artifact.")
    quration_handoff_parser.add_argument("root", help="Workspace root to scan.")
    quration_handoff_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan.")
    quration_handoff_parser.add_argument("--format", choices=["json", "markdown"], default="json", help="Output JSON bundle or just the rendered Markdown.")
    quration_handoff_parser.add_argument("--out", help="Optional output path for the quration handoff result.")

    substrate_parser = subparsers.add_parser("methods-graph-substrate", help="Report Dogma methods-graph guardrail substrate configuration.")
    substrate_parser.add_argument("--format", choices=["json", "markdown"], default="json", help="Output JSON bundle or just the rendered Markdown.")
    substrate_parser.add_argument("--out", help="Optional output path for the methods-graph substrate result.")

    preflight_parser = subparsers.add_parser("methods-graph-preflight", help="Run methods-graph guardrail-chain preflight for a workspace when configured.")
    preflight_parser.add_argument("root", help="Workspace root to scan.")
    preflight_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan.")
    preflight_parser.add_argument("--format", choices=["json", "markdown"], default="json", help="Output JSON bundle or just the rendered Markdown.")
    preflight_parser.add_argument("--out", help="Optional output path for the methods-graph preflight result.")

    llm_parser = subparsers.add_parser("llm-status", help="Report local Dogma LLM provider configuration.")
    llm_parser.add_argument("--format", choices=["json", "markdown"], default="json", help="Output JSON bundle or just the rendered Markdown.")
    llm_parser.add_argument("--out", help="Optional output path for the LLM provider status result.")

    agent_parser = subparsers.add_parser("agent-suggestion", help="Generate a guarded local Dogma agent suggestion.")
    agent_parser.add_argument("root", help="Workspace root to scan.")
    agent_parser.add_argument("--instruction", help="User instruction for the Dogma agent.")
    agent_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan.")
    agent_parser.add_argument("--use-llm", action="store_true", help="Call the configured local LLM provider instead of only producing the prompt.")
    agent_parser.add_argument("--provider", help="Optional provider override, e.g. claude_subscription.")
    agent_parser.add_argument("--cli-path", help="Optional Claude CLI path override.")
    agent_parser.add_argument("--model", help="Optional Claude model alias override.")
    agent_parser.add_argument("--timeout-seconds", type=int, help="Optional LLM timeout override.")
    agent_parser.add_argument("--editor-context-json", help="Optional active editor context JSON from the VS Code extension.")
    agent_parser.add_argument("--format", choices=["json", "markdown"], default="json", help="Output JSON bundle or just the rendered Markdown.")
    agent_parser.add_argument("--out", help="Optional output path for the agent suggestion result.")

    execute_parser = subparsers.add_parser("execute", help="Preview or explicitly execute an allowlisted dry-run/stub-run command.")
    execute_parser.add_argument("root", help="Workspace root to scan.")
    execute_parser.add_argument("--command-id", help="Command id from the run plan. Defaults to the first command.")
    execute_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan.")
    execute_parser.add_argument("--timeout-seconds", type=int, default=30, help="Execution timeout in seconds.")
    execute_parser.add_argument("--execute", action="store_true", help="Actually execute the selected allowlisted dry-run/stub-run command.")
    execute_parser.add_argument("--out", help="Optional output path for the JSON execution result.")

    proposals_parser = subparsers.add_parser("patch-proposals", help="Generate review-first Dogma patch proposals.")
    proposals_parser.add_argument("root", help="Workspace root to scan.")
    proposals_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan.")
    proposals_parser.add_argument("--out", help="Optional output path for the JSON proposal result.")

    apply_patch_parser = subparsers.add_parser("apply-patch", help="Preview or explicitly apply a Dogma patch proposal.")
    apply_patch_parser.add_argument("root", help="Workspace root to scan.")
    apply_patch_parser.add_argument("--proposal-id", help="Proposal id. Defaults to the first proposal.")
    apply_patch_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan.")
    apply_patch_parser.add_argument("--apply", action="store_true", help="Actually apply the selected patch proposal.")
    apply_patch_parser.add_argument("--out", help="Optional output path for the JSON patch result.")

    trust_parser = subparsers.add_parser("trust-status", help="Show Dogma workspace trust status.")
    trust_parser.add_argument("root", help="Workspace root to scan.")
    trust_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan.")
    trust_parser.add_argument("--out", help="Optional output path for the JSON trust result.")

    trust_write_parser = subparsers.add_parser("trust-workspace", help="Write .dogma/trust.json for local Dogma operations.")
    trust_write_parser.add_argument("root", help="Workspace root to trust.")
    trust_write_parser.add_argument("--reason", help="Reason recorded in .dogma/trust.json.")
    trust_write_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan after writing trust.")
    trust_write_parser.add_argument("--out", help="Optional output path for the JSON trust result.")

    subparsers.add_parser("mcp", help="Run the dependency-free Dogma MCP stdio server.")

    serve_parser = subparsers.add_parser("serve", help="Run the local HTTP API.")
    serve_parser.add_argument("root", help="Workspace root to scan.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    serve_parser.add_argument("--port", type=int, default=8765, help="Port to bind.")
    serve_parser.add_argument("--max-files", type=int, default=500, help="Maximum candidate files to scan.")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "scan":
        result = scan_workspace(args.root, max_files=args.max_files)
        write_json(result, args.out)
        return 0
    if args.command == "run-plan":
        result = build_run_plan_for_workspace(args.root, max_files=args.max_files)
        write_json(result, args.out)
        return 0
    if args.command == "assistant-context":
        result = build_assistant_context(args.root, max_files=args.max_files)
        if args.format == "markdown":
            write_text(result["markdown"], args.out)
        else:
            write_json(result, args.out)
        return 0
    if args.command == "guardrails":
        result = build_method_guardrails(args.root, max_files=args.max_files)
        if args.format == "markdown":
            write_text(result["markdown"], args.out)
        else:
            write_json(result, args.out)
        return 0
    if args.command == "evidence-ledger":
        result = build_evidence_ledger(args.root, max_files=args.max_files)
        if args.format == "markdown":
            write_text(result["markdown"], args.out)
        else:
            write_json(result, args.out)
        return 0
    if args.command == "edge-evaluation-plan":
        selected_edge = json.loads(args.selected_edge_json) if args.selected_edge_json else None
        result = build_edge_evaluation_plan(args.root, max_files=args.max_files, selected_edge=selected_edge)
        if args.format == "markdown":
            write_text(result["markdown"], args.out)
        else:
            write_json(result, args.out)
        return 0
    if args.command == "biological-graph":
        result = build_biological_graph(args.root, max_files=args.max_files)
        if args.format == "markdown":
            write_text(result["markdown"], args.out)
        else:
            write_json(result, args.out)
        return 0
    if args.command == "quration-handoff":
        result = build_quration_handoff(args.root, max_files=args.max_files)
        if args.format == "markdown":
            write_text(result["markdown"], args.out)
        else:
            write_json(result, args.out)
        return 0
    if args.command == "methods-graph-substrate":
        result = build_methods_graph_substrate()
        if args.format == "markdown":
            write_text(result["markdown"], args.out)
        else:
            write_json(result, args.out)
        return 0
    if args.command == "methods-graph-preflight":
        result = build_methods_graph_preflight(args.root, max_files=args.max_files)
        if args.format == "markdown":
            write_text(result["markdown"], args.out)
        else:
            write_json(result, args.out)
        return 0
    if args.command == "llm-status":
        result = build_llm_status()
        if args.format == "markdown":
            write_text(result["markdown"], args.out)
        else:
            write_json(result, args.out)
        return 0
    if args.command == "agent-suggestion":
        editor_context = json.loads(args.editor_context_json) if args.editor_context_json else None
        result = build_agent_suggestion(
            args.root,
            instruction=args.instruction,
            max_files=args.max_files,
            use_llm=args.use_llm,
            provider_name=args.provider,
            cli_path=args.cli_path,
            model=args.model,
            timeout_seconds=args.timeout_seconds,
            editor_context=editor_context,
        )
        if args.format == "markdown":
            write_text(result["markdown"], args.out)
        else:
            write_json(result, args.out)
        return 0
    if args.command == "execute":
        result = execute_command(
            args.root,
            command_id=args.command_id,
            max_files=args.max_files,
            timeout_seconds=args.timeout_seconds,
            execute=args.execute,
        )
        write_json(result, args.out)
        return 0
    if args.command == "patch-proposals":
        result = build_patch_proposals(args.root, max_files=args.max_files)
        write_json(result, args.out)
        return 0
    if args.command == "apply-patch":
        result = apply_patch_proposal(
            args.root,
            proposal_id=args.proposal_id,
            max_files=args.max_files,
            apply=args.apply,
        )
        write_json(result, args.out)
        return 0
    if args.command == "trust-status":
        scan = scan_workspace(args.root, max_files=args.max_files)
        write_json({"service": "dogma-local-service", "root": scan["root"], "trust": scan["trust"], "summary": scan["summary"]}, args.out)
        return 0
    if args.command == "trust-workspace":
        write_result = write_trust_policy(args.root, reason=args.reason)
        scan = scan_workspace(args.root, max_files=args.max_files)
        write_json({"service": "dogma-local-service", "root": scan["root"], "write": write_result, "trust": scan["trust"], "summary": scan["summary"]}, args.out)
        return 0
    if args.command == "mcp":
        return run_mcp_stdio()
    if args.command == "serve":
        serve(args.root, host=args.host, port=args.port, max_files=args.max_files)
        return 0
    return 2


def write_json(result: dict, output: str | None) -> None:
    payload = json.dumps(result, indent=2, sort_keys=True)
    if output:
        output_path = Path(output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


def write_text(result: str, output: str | None) -> None:
    payload = result.rstrip() + "\n"
    if output:
        output_path = Path(output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    raise SystemExit(main())
