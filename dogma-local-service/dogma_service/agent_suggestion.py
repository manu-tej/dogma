"""Guarded Dogma agent suggestions backed by the local LLM adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping, Protocol

from .assistant_context import build_assistant_context, build_sample_redactor, redact_value
from .biological_graph import build_biological_graph
from .indexer import scan_workspace
from .llm_provider import ClaudeSubscriptionProvider, build_llm_status, env_get
from .method_guardrails import build_method_guardrails
from .methods_graph_preflight import build_methods_graph_preflight
from .patch_proposals import build_patch_proposals


class MessageProvider(Protocol):
    def create_message(self, prompt: str) -> str:
        ...


DEFAULT_INSTRUCTION = "Review the current workspace and propose the next smallest safe bioinformatics IDE action."


def clip_text(value: str, max_chars: int = 24000) -> str:
    if len(value) <= max_chars:
        return value
    return value[:max_chars] + "\n\n[Dogma clipped additional context before sending this prompt.]"


def extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def normalize_editor_context(editor_context: dict[str, Any] | None, scan: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(editor_context, dict):
        return None

    raw_samples = scan.get("context", {}).get("samples", {})
    sample_ids = [str(item) for item in raw_samples.get("ids", []) if str(item).strip()]
    trust = scan.get("trust", {})
    should_redact = bool(trust.get("human_data") and not trust.get("trusted"))
    _, redact_text = build_sample_redactor(sample_ids, should_redact)

    safe = {
        "path": str(editor_context.get("path") or "active editor")[:240],
        "language_id": str(editor_context.get("language_id") or editor_context.get("languageId") or "")[:80],
        "selection": editor_context.get("selection") if isinstance(editor_context.get("selection"), dict) else {},
        "selected_text": str(editor_context.get("selected_text") or editor_context.get("selectedText") or "")[:6000],
        "current_line": str(editor_context.get("current_line") or editor_context.get("currentLine") or "")[:1000],
        "included": True,
    }
    if not safe["selected_text"]:
        safe["selected_text"] = ""
        safe["included"] = bool(safe["current_line"] or safe["path"] != "active editor")
    safe["redaction"] = {
        "sample_ids_redacted": should_redact,
        "reason": (
            "Editor context was redacted with the workspace sample-id policy."
            if should_redact
            else "Editor context did not require sample-id redaction."
        ),
    }
    return redact_value(safe, redact_text)


def methods_graph_prompt_summary(preflight: dict[str, Any]) -> dict[str, Any]:
    method_chain = preflight.get("method_chain", {}) if isinstance(preflight.get("method_chain"), dict) else {}
    dataset_facts = preflight.get("dataset_facts", {}) if isinstance(preflight.get("dataset_facts"), dict) else {}
    verdict = preflight.get("verdict", {}) if isinstance(preflight.get("verdict"), dict) else {}
    return {
        "status": preflight.get("status"),
        "substrate_status": preflight.get("substrate_status"),
        "verdict_status": verdict.get("status"),
        "method_ids": method_chain.get("method_ids", [])[:12],
        "coverage_gaps": preflight.get("coverage_gaps", [])[:20],
        "next_actions": preflight.get("next_actions", [])[:10],
        "dataset_facts": dataset_facts.get("facts", {}),
        "method_chain_steps": [
            {
                "process": step.get("process"),
                "location": step.get("location"),
                "method_id": step.get("method_id"),
                "status": step.get("status"),
            }
            for step in method_chain.get("steps", [])[:12]
            if isinstance(step, dict)
        ],
    }


def build_prompt(
    instruction: str,
    assistant_context: dict[str, Any],
    guardrails: dict[str, Any],
    methods_graph_preflight: dict[str, Any],
    biological_graph: dict[str, Any],
    patch_proposals: dict[str, Any],
    editor_context: dict[str, Any] | None = None,
) -> str:
    proposal_summary = [
        {
            "id": item.get("id"),
            "kind": item.get("kind"),
            "title": item.get("title"),
            "target_file": item.get("target_file"),
            "requires_review": item.get("safety", {}).get("requires_review"),
        }
        for item in patch_proposals.get("proposals", [])
    ]
    graph_edges = [
        {
            "id": edge.get("id"),
            "title": edge.get("title"),
            "status": edge.get("status"),
            "coverage_gaps": edge.get("facts", {}).get("coverage_gaps", []),
            "methods_graph_status": edge.get("facts", {}).get("methods_graph_status"),
        }
        for edge in biological_graph.get("edges", [])
    ]

    payload = {
        "instruction": instruction or DEFAULT_INSTRUCTION,
        "privacy": assistant_context.get("redaction", {}),
        "trust": assistant_context.get("trust", {}),
        "summary": assistant_context.get("summary", {}),
        "context": assistant_context.get("context", {}),
        "issues": assistant_context.get("issues", []),
        "method_guardrail_checks": guardrails.get("checks", []),
        "methods_graph_preflight": methods_graph_prompt_summary(methods_graph_preflight),
        "biological_edges": graph_edges,
        "patch_proposals": proposal_summary,
        "active_editor": editor_context,
    }

    schema = {
        "status": "blocked | ready_for_review | needs_user_input",
        "summary": "one concise paragraph",
        "highest_risks": ["risk strings grounded in provided files/findings"],
        "next_actions": [
            {
                "kind": "scan | patch_preview | test_plan | guardrail | question",
                "title": "short action title",
                "rationale": "why this is next",
                "target_file": "optional file path",
                "proposal_id": "optional Dogma patch proposal id",
            }
        ],
        "must_not_do": ["actions Dogma should not take yet"],
    }

    return "\n".join(
        [
            "You are the Dogma local IDE agent.",
            "Return only valid JSON matching the requested schema. Do not wrap it in Markdown.",
            "You may propose actions, but you may not claim execution, edit files, infer biological support/refute verdicts, or invent missing metadata.",
            "The Python service owns all execution, patch application, privacy redaction, and methods-graph guardrails.",
            "Treat methods_graph_preflight coverage_gaps as hard guardrail gaps. Do not fill them in from general knowledge.",
            "Prefer the smallest reviewable next action that moves a bioinformatics workflow toward correctness.",
            "",
            "Requested schema:",
            json.dumps(schema, indent=2, sort_keys=True),
            "",
            "Dogma payload:",
            clip_text(json.dumps(payload, indent=2, sort_keys=True)),
        ]
    )


def llm_env(provider_name: str | None = None, cli_path: str | None = None, model: str | None = None, timeout_seconds: int | None = None) -> dict[str, str]:
    values = dict(os.environ)
    if provider_name:
        values["DOGMA_LLM_PROVIDER"] = provider_name
    if cli_path:
        values["DOGMA_CLAUDE_CLI_PATH"] = cli_path
    if model:
        values["DOGMA_CLAUDE_MODEL"] = model
    if timeout_seconds:
        values["DOGMA_LLM_TIMEOUT_SECONDS"] = str(timeout_seconds)
    return values


def provider_from_config(values: Mapping[str, str]) -> MessageProvider | None:
    provider = env_get(values, "DOGMA_LLM_PROVIDER", "BIOCURSOR_LLM_PROVIDER", "QURATION_PROVIDER", default="none")
    if provider != "claude_subscription":
        return None
    cli_path = env_get(values, "DOGMA_CLAUDE_CLI_PATH", "BIOCURSOR_CLAUDE_CLI_PATH", "CLAUDE_CLI_PATH", default="claude") or "claude"
    model = env_get(values, "DOGMA_CLAUDE_MODEL", "BIOCURSOR_CLAUDE_MODEL", "QURATION_CLAUDE_MODEL", default="sonnet") or "sonnet"
    timeout_seconds = int(env_get(values, "DOGMA_LLM_TIMEOUT_SECONDS", "BIOCURSOR_LLM_TIMEOUT_SECONDS", "CLAUDE_TIMEOUT_SECONDS", default="180") or "180")
    return ClaudeSubscriptionProvider(cli_path=cli_path, model=model, timeout_seconds=timeout_seconds)


def render_agent_suggestion_markdown(result: dict[str, Any]) -> str:
    suggestion = result.get("suggestion") or {}
    methods_graph = result.get("methods_graph_preflight") or {}
    risks = suggestion.get("highest_risks") or []
    actions = suggestion.get("next_actions") or []
    must_not = suggestion.get("must_not_do") or []
    coverage_gaps = methods_graph.get("coverage_gaps") or []
    methods_next_actions = methods_graph.get("next_actions") or []

    def action_line(action: dict[str, Any]) -> str:
        parts = [f"**{action.get('kind', 'action')}**", str(action.get("title") or "Untitled action")]
        if action.get("target_file"):
            parts.append(f"`{action['target_file']}`")
        if action.get("proposal_id"):
            parts.append(f"proposal `{action['proposal_id']}`")
        if action.get("rationale"):
            parts.append(str(action["rationale"]))
        return "- " + " - ".join(parts)

    return "\n".join(
        [
            "# Dogma Agent Suggestion",
            "",
            f"- Status: {result.get('status')}",
            f"- Provider: {result.get('llm_status', {}).get('provider')}",
            f"- LLM executed: {str(bool(result.get('llm_executed'))).lower()}",
            f"- Workspace: {result.get('root')}",
            "",
            "## User Instruction",
            "",
            result.get("instruction") or DEFAULT_INSTRUCTION,
            "",
            "## Active Editor",
            "",
            f"- Path: {(result.get('editor_context') or {}).get('path', 'not captured')}",
            f"- Language: {(result.get('editor_context') or {}).get('language_id', 'not captured')}",
            f"- Selected text included: {str(bool((result.get('editor_context') or {}).get('selected_text'))).lower()}",
            f"- Sample IDs redacted: {str(bool((result.get('editor_context') or {}).get('redaction', {}).get('sample_ids_redacted'))).lower()}",
            "",
            "## methods-graph Preflight",
            "",
            f"- Status: {methods_graph.get('status', 'not checked')}",
            f"- Substrate status: {methods_graph.get('substrate_status', 'not checked')}",
            f"- Verdict: {(methods_graph.get('verdict') or {}).get('status', 'not available')}",
            "",
            "### Coverage Gaps",
            "",
            *(f"- {item}" for item in coverage_gaps),
            *(["- none"] if not coverage_gaps else []),
            "",
            "### Preflight Next Actions",
            "",
            *(f"- {item}" for item in methods_next_actions),
            *(["- none"] if not methods_next_actions else []),
            "",
            "## Agent Summary",
            "",
            suggestion.get("summary") or result.get("message") or "No model-generated summary is available.",
            "",
            "## Highest Risks",
            "",
            *(f"- {item}" for item in risks),
            *(["- No model-generated risks are available."] if not risks else []),
            "",
            "## Next Actions",
            "",
            *(action_line(item) for item in actions if isinstance(item, dict)),
            *(["- No model-generated actions are available."] if not actions else []),
            "",
            "## Must Not Do Yet",
            "",
            *(f"- {item}" for item in must_not),
            *(["- Do not bypass Dogma guardrails or apply patches without review."] if not must_not else []),
            "",
            "## Prompt",
            "",
            "```text",
            result.get("prompt", ""),
            "```",
            "",
            "## Raw LLM Output",
            "",
            "```text",
            result.get("raw_output") or "",
            "```",
            "",
        ]
    )


def build_agent_suggestion(
    root: str | Path,
    instruction: str | None = None,
    max_files: int = 500,
    use_llm: bool = False,
    provider_name: str | None = None,
    cli_path: str | None = None,
    model: str | None = None,
    timeout_seconds: int | None = None,
    provider: MessageProvider | None = None,
    editor_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    user_instruction = instruction or DEFAULT_INSTRUCTION
    raw_scan = scan_workspace(root_path, max_files=max_files)
    assistant_context = build_assistant_context(root_path, max_files=max_files)
    guardrails = build_method_guardrails(root_path, max_files=max_files)
    methods_graph_preflight = build_methods_graph_preflight(root_path, max_files=max_files)
    biological_graph = build_biological_graph(root_path, max_files=max_files)
    patch_proposals = build_patch_proposals(root_path, max_files=max_files, methods_graph_preflight=methods_graph_preflight)
    safe_editor_context = normalize_editor_context(editor_context, raw_scan)
    prompt = build_prompt(user_instruction, assistant_context, guardrails, methods_graph_preflight, biological_graph, patch_proposals, safe_editor_context)
    values = llm_env(provider_name=provider_name, cli_path=cli_path, model=model, timeout_seconds=timeout_seconds)
    llm_status = build_llm_status(env=values, check_cli=use_llm and provider is None)
    default_next_actions = [
        {
            "kind": "guardrail",
            "title": "Resolve methods-graph preflight gap",
            "target_file": ".dogma/methods-graph-preflight.md",
            "rationale": action,
        }
        for action in methods_graph_preflight.get("next_actions", [])[:2]
    ]
    default_next_actions.extend(
        {
            "kind": "patch_preview",
            "title": proposal.get("title"),
            "target_file": proposal.get("target_file"),
            "proposal_id": proposal.get("id"),
            "rationale": proposal.get("rationale"),
        }
        for proposal in patch_proposals.get("proposals", [])[:3]
    )

    result: dict[str, Any] = {
        "service": "dogma-local-service",
        "root": str(root_path),
        "instruction": user_instruction,
        "status": "prompt_ready",
        "message": "Agent prompt is ready. Enable/use a local LLM provider to produce a model suggestion.",
        "llm_executed": False,
        "llm_status": llm_status,
        "editor_context": safe_editor_context,
        "methods_graph_preflight": methods_graph_preflight,
        "prompt": prompt,
        "suggestion": {
            "status": "blocked" if assistant_context.get("summary", {}).get("errors", 0) else "ready_for_review",
            "summary": "Dogma has assembled redacted workspace context, methods-graph preflight, guardrails, graph edges, and patch proposals for review.",
            "highest_risks": [
                *[issue.get("message", "") for issue in assistant_context.get("issues", [])[:5]],
                *[f"methods-graph coverage gap: {gap}" for gap in methods_graph_preflight.get("coverage_gaps", [])[:5]],
            ],
            "next_actions": default_next_actions,
            "must_not_do": [
                "Do not execute real workflow commands while error-level Dogma findings remain.",
                "Do not treat methods-graph coverage gaps as resolved unless a fresh preflight says so.",
            ],
        },
        "raw_output": None,
    }

    if use_llm:
        try:
            active_provider = provider or provider_from_config(values)
            if active_provider is None:
                result["status"] = "llm_not_configured"
                result["message"] = "No supported local LLM provider is configured. Set provider to claude_subscription."
            else:
                raw_output = active_provider.create_message(prompt)
                parsed = extract_json_object(raw_output)
                result["raw_output"] = raw_output
                result["llm_executed"] = True
                if parsed is None:
                    result["status"] = "llm_unstructured"
                    result["message"] = "Claude returned text that did not parse as the requested JSON schema."
                else:
                    result["status"] = "llm_completed"
                    result["message"] = "Claude produced a guarded Dogma agent suggestion."
                    result["suggestion"] = parsed
        except Exception as error:  # noqa: BLE001 - surfaced to local caller as typed status
            result["status"] = "llm_error"
            result["message"] = str(error)

    result["markdown"] = render_agent_suggestion_markdown(result)
    return result
