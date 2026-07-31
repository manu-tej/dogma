"""HTTP API for the Dogma local companion service."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import __version__
from .agent_suggestion import build_agent_suggestion, llm_env
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
from .patch_proposals import apply_patch_proposal, build_patch_proposals
from .quration_handoff import build_quration_handoff
from .trust_policy import write_trust_policy


def json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")


def make_handler(default_root: str | Path, max_files: int = 500) -> type[BaseHTTPRequestHandler]:
    root_path = Path(default_root).expanduser().resolve()

    class DogmaHandler(BaseHTTPRequestHandler):
        server_version = "DogmaLocalService/0.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json_bytes(payload)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self.send_json(HTTPStatus.OK, {"ok": True})

        def do_GET(self) -> None:
            route = urlparse(self.path).path
            if route == "/health":
                self.send_json(HTTPStatus.OK, {"status": "ok", "service": "dogma-local-service", "version": __version__})
                return
            if route == "/scan":
                self.respond_scan(root_path, max_files)
                return
            if route == "/context":
                result = scan_workspace(root_path, max_files=max_files)
                self.send_json(HTTPStatus.OK, {"context": result["context"], "summary": result["summary"], "issues": result["issues"]})
                return
            if route == "/run-plan":
                self.respond_run_plan(root_path, max_files)
                return
            if route == "/assistant-context":
                self.respond_assistant_context(root_path, max_files)
                return
            if route == "/guardrails":
                self.respond_guardrails(root_path, max_files)
                return
            if route == "/evidence-ledger":
                self.respond_evidence_ledger(root_path, max_files)
                return
            if route == "/edge-evaluation-plan":
                self.respond_edge_evaluation_plan(root_path, max_files)
                return
            if route == "/biological-graph":
                self.respond_biological_graph(root_path, max_files)
                return
            if route == "/quration-handoff":
                self.respond_quration_handoff(root_path, max_files)
                return
            if route == "/methods-graph-substrate":
                self.respond_methods_graph_substrate()
                return
            if route == "/methods-graph-preflight":
                self.respond_methods_graph_preflight(root_path, max_files)
                return
            if route == "/llm-status":
                self.respond_llm_status()
                return
            if route == "/agent-suggestion":
                self.respond_agent_suggestion(root_path, max_files)
                return
            if route == "/patch-proposals":
                self.respond_patch_proposals(root_path, max_files)
                return
            if route == "/trust":
                self.respond_trust(root_path, max_files)
                return
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found", "routes": ["/health", "/scan", "/context", "/run-plan", "/assistant-context", "/guardrails", "/evidence-ledger", "/edge-evaluation-plan", "/biological-graph", "/quration-handoff", "/methods-graph-substrate", "/methods-graph-preflight", "/llm-status", "/agent-suggestion", "/execute", "/patch-proposals", "/trust"]})

        def do_POST(self) -> None:
            route = urlparse(self.path).path
            if route not in {"/scan", "/run-plan", "/assistant-context", "/guardrails", "/evidence-ledger", "/edge-evaluation-plan", "/biological-graph", "/quration-handoff", "/methods-graph-substrate", "/methods-graph-preflight", "/llm-status", "/agent-suggestion", "/execute", "/patch-proposals", "/apply-patch", "/trust"}:
                self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found", "routes": ["/scan", "/run-plan", "/assistant-context", "/guardrails", "/evidence-ledger", "/edge-evaluation-plan", "/biological-graph", "/quration-handoff", "/methods-graph-substrate", "/methods-graph-preflight", "/llm-status", "/agent-suggestion", "/execute", "/patch-proposals", "/apply-patch", "/trust"]})
                return

            body = self.read_json_body()
            if body is None:
                return

            request_root = Path(body.get("root") or root_path).expanduser().resolve()
            request_max_files = int(body.get("max_files") or max_files)
            if route == "/scan":
                self.respond_scan(request_root, request_max_files)
            elif route == "/run-plan":
                self.respond_run_plan(request_root, request_max_files)
            elif route == "/assistant-context":
                self.respond_assistant_context(request_root, request_max_files)
            elif route == "/guardrails":
                self.respond_guardrails(request_root, request_max_files)
            elif route == "/evidence-ledger":
                self.respond_evidence_ledger(request_root, request_max_files)
            elif route == "/edge-evaluation-plan":
                self.respond_edge_evaluation_plan(request_root, request_max_files, selected_edge=body.get("selected_edge"))
            elif route == "/biological-graph":
                self.respond_biological_graph(request_root, request_max_files)
            elif route == "/quration-handoff":
                self.respond_quration_handoff(request_root, request_max_files)
            elif route == "/methods-graph-substrate":
                self.respond_methods_graph_substrate()
            elif route == "/methods-graph-preflight":
                self.respond_methods_graph_preflight(request_root, request_max_files)
            elif route == "/llm-status":
                self.respond_llm_status(
                    provider_name=body.get("provider"),
                    cli_path=body.get("cli_path"),
                    model=body.get("model"),
                    timeout_seconds=int(body.get("timeout_seconds") or 0) or None,
                )
            elif route == "/agent-suggestion":
                self.respond_agent_suggestion(
                    request_root,
                    request_max_files,
                    instruction=body.get("instruction"),
                    use_llm=bool(body.get("use_llm")),
                    provider_name=body.get("provider"),
                    cli_path=body.get("cli_path"),
                    model=body.get("model"),
                    timeout_seconds=int(body.get("timeout_seconds") or 0) or None,
                    editor_context=body.get("editor_context") if isinstance(body.get("editor_context"), dict) else None,
                )
            elif route == "/execute":
                self.respond_execute(
                    request_root,
                    request_max_files,
                    command_id=body.get("command_id"),
                    timeout_seconds=int(body.get("timeout_seconds") or 30),
                    execute=bool(body.get("execute")),
                )
            elif route == "/patch-proposals":
                self.respond_patch_proposals(request_root, request_max_files)
            elif route == "/apply-patch":
                self.respond_apply_patch(
                    request_root,
                    request_max_files,
                    proposal_id=body.get("proposal_id"),
                    apply=bool(body.get("apply")),
                )
            elif route == "/trust":
                self.respond_write_trust(request_root, request_max_files, reason=body.get("reason"))

        def read_json_body(self) -> dict[str, Any] | None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length else b"{}"
            try:
                return json.loads(raw_body.decode("utf-8") or "{}")
            except json.JSONDecodeError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json", "message": error.msg})
                return None

        def respond_scan(self, workspace_root: Path, scan_max_files: int) -> None:
            try:
                result = scan_workspace(workspace_root, max_files=scan_max_files)
            except (FileNotFoundError, NotADirectoryError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_workspace", "message": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)

        def respond_run_plan(self, workspace_root: Path, scan_max_files: int) -> None:
            try:
                result = build_run_plan_for_workspace(workspace_root, max_files=scan_max_files)
            except (FileNotFoundError, NotADirectoryError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_workspace", "message": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)

        def respond_assistant_context(self, workspace_root: Path, scan_max_files: int) -> None:
            try:
                result = build_assistant_context(workspace_root, max_files=scan_max_files)
            except (FileNotFoundError, NotADirectoryError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_workspace", "message": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)

        def respond_guardrails(self, workspace_root: Path, scan_max_files: int) -> None:
            try:
                result = build_method_guardrails(workspace_root, max_files=scan_max_files)
            except (FileNotFoundError, NotADirectoryError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_workspace", "message": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)

        def respond_evidence_ledger(self, workspace_root: Path, scan_max_files: int) -> None:
            try:
                result = build_evidence_ledger(workspace_root, max_files=scan_max_files)
            except (FileNotFoundError, NotADirectoryError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_workspace", "message": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)

        def respond_edge_evaluation_plan(self, workspace_root: Path, scan_max_files: int, selected_edge: dict[str, Any] | None = None) -> None:
            try:
                result = build_edge_evaluation_plan(workspace_root, max_files=scan_max_files, selected_edge=selected_edge)
            except (FileNotFoundError, NotADirectoryError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_workspace", "message": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)

        def respond_biological_graph(self, workspace_root: Path, scan_max_files: int) -> None:
            try:
                result = build_biological_graph(workspace_root, max_files=scan_max_files)
            except (FileNotFoundError, NotADirectoryError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_workspace", "message": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)

        def respond_quration_handoff(self, workspace_root: Path, scan_max_files: int) -> None:
            try:
                result = build_quration_handoff(workspace_root, max_files=scan_max_files)
            except (FileNotFoundError, NotADirectoryError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_workspace", "message": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)

        def respond_methods_graph_substrate(self) -> None:
            self.send_json(HTTPStatus.OK, build_methods_graph_substrate())

        def respond_methods_graph_preflight(self, workspace_root: Path, scan_max_files: int) -> None:
            try:
                result = build_methods_graph_preflight(workspace_root, max_files=scan_max_files)
            except (FileNotFoundError, NotADirectoryError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_workspace", "message": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)

        def respond_llm_status(
            self,
            provider_name: str | None = None,
            cli_path: str | None = None,
            model: str | None = None,
            timeout_seconds: int | None = None,
        ) -> None:
            env = llm_env(
                provider_name=provider_name,
                cli_path=cli_path,
                model=model,
                timeout_seconds=timeout_seconds,
            )
            self.send_json(HTTPStatus.OK, build_llm_status(env=env))

        def respond_agent_suggestion(
            self,
            workspace_root: Path,
            scan_max_files: int,
            instruction: str | None = None,
            use_llm: bool = False,
            provider_name: str | None = None,
            cli_path: str | None = None,
            model: str | None = None,
            timeout_seconds: int | None = None,
            editor_context: dict[str, Any] | None = None,
        ) -> None:
            try:
                result = build_agent_suggestion(
                    workspace_root,
                    instruction=instruction,
                    max_files=scan_max_files,
                    use_llm=use_llm,
                    provider_name=provider_name,
                    cli_path=cli_path,
                    model=model,
                    timeout_seconds=timeout_seconds,
                    editor_context=editor_context,
                )
            except (FileNotFoundError, NotADirectoryError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_workspace", "message": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)

        def respond_execute(self, workspace_root: Path, scan_max_files: int, command_id: str | None, timeout_seconds: int, execute: bool) -> None:
            try:
                result = execute_command(
                    workspace_root,
                    command_id=command_id,
                    max_files=scan_max_files,
                    timeout_seconds=timeout_seconds,
                    execute=execute,
                )
            except (FileNotFoundError, NotADirectoryError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_workspace", "message": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)

        def respond_patch_proposals(self, workspace_root: Path, scan_max_files: int) -> None:
            try:
                result = build_patch_proposals(workspace_root, max_files=scan_max_files)
            except (FileNotFoundError, NotADirectoryError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_workspace", "message": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)

        def respond_apply_patch(self, workspace_root: Path, scan_max_files: int, proposal_id: str | None, apply: bool) -> None:
            try:
                result = apply_patch_proposal(workspace_root, proposal_id=proposal_id, max_files=scan_max_files, apply=apply)
            except (FileNotFoundError, NotADirectoryError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_workspace", "message": str(error)})
                return
            self.send_json(HTTPStatus.OK, result)

        def respond_trust(self, workspace_root: Path, scan_max_files: int) -> None:
            try:
                result = scan_workspace(workspace_root, max_files=scan_max_files)
            except (FileNotFoundError, NotADirectoryError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_workspace", "message": str(error)})
                return
            self.send_json(HTTPStatus.OK, {"service": "dogma-local-service", "root": str(workspace_root), "trust": result["trust"], "summary": result["summary"]})

        def respond_write_trust(self, workspace_root: Path, scan_max_files: int, reason: str | None) -> None:
            try:
                written = write_trust_policy(workspace_root, reason=reason)
                result = scan_workspace(workspace_root, max_files=scan_max_files)
            except (FileNotFoundError, NotADirectoryError) as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_workspace", "message": str(error)})
                return
            self.send_json(HTTPStatus.OK, {"service": "dogma-local-service", "root": str(workspace_root), "write": written, "trust": result["trust"], "summary": result["summary"]})

    return DogmaHandler


def make_server(root: str | Path, host: str = "127.0.0.1", port: int = 8765, max_files: int = 500) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(root, max_files=max_files))


def serve(root: str | Path, host: str = "127.0.0.1", port: int = 8765, max_files: int = 500) -> None:
    server = make_server(root, host=host, port=port, max_files=max_files)
    address, bound_port = server.server_address
    print(f"Dogma local service listening on http://{address}:{bound_port}")
    print(f"Workspace root: {Path(root).expanduser().resolve()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Dogma local service")
    finally:
        server.server_close()
