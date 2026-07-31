"""Review-first patch proposals for Dogma findings."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

from .indexer import scan_workspace

SAMPLE_TUPLE_PATTERN = ".map { row -> tuple(row.sample_id, [file(row.fastq_1), file(row.fastq_2)]) }"
SAMPLE_ID_POLICY = "Sample identifiers must be unique, stable, and de-identified before local analysis."

SAMPLE_VALIDATION_HELPER = """def validateSampleRow(row) {
  def required = ["sample_id", "fastq_1", "fastq_2", "strandedness"]
  required.each { key ->
    if (!row[key]) {
      throw new IllegalArgumentException("sample sheet missing " + key + " for row: " + row)
    }
  }
  return row
}

"""


def build_unified_diff(file_path: str, before: str, after: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
    )


def apply_sample_validation_text(text: str) -> tuple[bool, str, str]:
    if "def validateSampleRow" in text:
        return False, text, "already-present"
    if "workflow {" not in text or SAMPLE_TUPLE_PATTERN not in text:
        return False, text, "pattern-not-found"

    patched = text.replace("workflow {", SAMPLE_VALIDATION_HELPER + "workflow {", 1).replace(
        SAMPLE_TUPLE_PATTERN,
        ".map { row -> validateSampleRow(row) }\n    .map { row -> tuple(row.sample_id, [file(row.fastq_1), file(row.fastq_2)]) }",
        1,
    )
    return patched != text, patched, "patched" if patched != text else "pattern-not-found"


def issue_codes(scan_result: dict[str, Any]) -> set[str]:
    return {issue.get("code", "") for issue in scan_result.get("issues", [])}


def nextflow_validation_proposals(root: Path, scan_result: dict[str, Any]) -> list[dict[str, Any]]:
    if "nextflow.sample_sheet_validation" not in issue_codes(scan_result):
        return []

    proposals = []
    for workflow_file in scan_result.get("context", {}).get("workflow_files", []):
        if not workflow_file.lower().endswith(".nf"):
            continue
        target = root / workflow_file
        if not target.exists() or not target.is_file():
            continue
        before = target.read_text(encoding="utf-8", errors="replace")
        changed, after, reason = apply_sample_validation_text(before)
        if not changed:
            continue
        proposals.append(
            {
                "id": f"nextflow-sample-validation-{len(proposals) + 1}",
                "kind": "nextflow.sample_sheet_validation",
                "title": f"Add sample sheet row validation to {workflow_file}",
                "target_file": workflow_file,
                "severity": "warning",
                "reason": reason,
                "rationale": (
                    "The workflow reads sample-sheet rows into file tuples without validating required fields. "
                    "This proposal adds a small validateSampleRow helper before tuple creation."
                ),
                "safety": {
                    "requires_review": True,
                    "auto_apply": False,
                    "scope": "single-file Nextflow text edit",
                },
                "before": before,
                "after": after,
                "diff": build_unified_diff(workflow_file, before, after),
            }
        )
    return proposals


def metadata_sample_policy_text(text: str) -> tuple[bool, str, str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return False, text, "invalid-json"

    if not isinstance(data, dict):
        return False, text, "metadata-not-object"

    samples = data.get("samples")
    if not isinstance(samples, dict):
        samples = {}
        data["samples"] = samples
    if samples.get("sample_id_policy"):
        return False, text, "already-present"

    samples["sample_id_policy"] = SAMPLE_ID_POLICY
    patched = json.dumps(data, indent=2, sort_keys=False) + "\n"
    return patched != text, patched, "patched" if patched != text else "already-present"


def metadata_sample_policy_proposals(root: Path, scan_result: dict[str, Any]) -> list[dict[str, Any]]:
    if "metadata.missing_sample_id_policy" not in issue_codes(scan_result):
        return []

    proposals = []
    for metadata_file in scan_result.get("context", {}).get("metadata_files", []):
        target = root / metadata_file
        if not target.exists() or not target.is_file():
            continue
        before = target.read_text(encoding="utf-8", errors="replace")
        changed, after, reason = metadata_sample_policy_text(before)
        if not changed:
            continue
        proposals.append(
            {
                "id": f"metadata-sample-id-policy-{len(proposals) + 1}",
                "kind": "metadata.missing_sample_id_policy",
                "title": f"Add sample identifier policy to {metadata_file}",
                "target_file": metadata_file,
                "severity": "warning",
                "reason": reason,
                "rationale": (
                    "The project metadata does not declare how sample identifiers are handled. "
                    "This proposal adds a conservative policy requiring unique, stable, de-identified identifiers."
                ),
                "safety": {
                    "requires_review": True,
                    "auto_apply": False,
                    "scope": "single-file metadata JSON edit",
                },
                "before": before,
                "after": after,
                "diff": build_unified_diff(metadata_file, before, after),
            }
        )
    return proposals


def build_patch_proposals(
    root: str | Path,
    max_files: int = 500,
    *,
    methods_graph_preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root_path = Path(root).expanduser().resolve()
    scan_result = scan_workspace(root_path, max_files=max_files)
    from .methods_graph_preflight import build_methods_graph_preflight

    methods_graph = methods_graph_preflight or build_methods_graph_preflight(root_path, max_files=max_files)
    proposals = [
        *nextflow_validation_proposals(root_path, scan_result),
        *metadata_sample_policy_proposals(root_path, scan_result),
    ]
    return {
        "service": "dogma-local-service",
        "root": str(root_path),
        "proposal_count": len(proposals),
        "proposals": proposals,
        "scan_summary": scan_result.get("summary", {}),
        "trust": scan_result.get("trust", {}),
        "issues": scan_result.get("issues", []),
        "methods_graph_preflight": methods_graph,
    }


def apply_patch_proposal(root: str | Path, proposal_id: str | None = None, max_files: int = 500, apply: bool = False) -> dict[str, Any]:
    result = build_patch_proposals(root, max_files=max_files)
    proposals = result["proposals"]
    selected = proposals[0] if proposals and proposal_id is None else next((item for item in proposals if item["id"] == proposal_id), None)

    if selected is None:
        return {
            "status": "no_proposal",
            "applied": False,
            "message": "No matching Dogma patch proposal is available.",
            "methods_graph_preflight": result.get("methods_graph_preflight", {}),
            "proposal_result": result,
        }

    if not apply:
        return {
            "status": "preview",
            "applied": False,
            "message": "Patch was not applied. Send apply=true after review to apply this proposal.",
            "proposal": selected,
            "methods_graph_preflight": result.get("methods_graph_preflight", {}),
            "proposal_result": result,
        }

    trust = result.get("trust", {})
    if trust.get("trusted") is False:
        return {
            "status": "blocked",
            "applied": False,
            "message": "Patch application is blocked by workspace trust policy.",
            "trust": trust,
            "proposal": selected,
            "methods_graph_preflight": result.get("methods_graph_preflight", {}),
            "proposal_result": result,
        }

    target = Path(root).expanduser().resolve() / selected["target_file"]
    current = target.read_text(encoding="utf-8", errors="replace")
    if current != selected["before"]:
        return {
            "status": "conflict",
            "applied": False,
            "message": "Target file changed after proposal generation; regenerate proposals before applying.",
            "proposal": selected,
            "methods_graph_preflight": result.get("methods_graph_preflight", {}),
            "proposal_result": result,
        }

    target.write_text(selected["after"], encoding="utf-8")
    return {
        "status": "applied",
        "applied": True,
        "message": f"Applied {selected['id']} to {selected['target_file']}.",
        "proposal": selected,
        "methods_graph_preflight": result.get("methods_graph_preflight", {}),
        "proposal_result": result,
    }
