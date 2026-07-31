"""Workspace trust policy for privacy-sensitive Dogma operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRUST_RELATIVE_PATH = Path(".dogma") / "trust.json"


def trust_policy_path(root: str | Path) -> Path:
    return Path(root).expanduser().resolve() / TRUST_RELATIVE_PATH


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return {"_invalid": True}


def human_data_detected(scan_result: dict[str, Any]) -> bool:
    summary = scan_result.get("summary", {})
    context = scan_result.get("context", {})
    privacy = context.get("privacy", {})
    return bool(summary.get("human_data") or privacy.get("human_data") or privacy.get("contains_human_data"))


def policy_allows_human_data(policy: dict[str, Any] | None) -> bool:
    if not policy or policy.get("_invalid"):
        return False
    if policy.get("trusted") is not True:
        return False
    if policy.get("allow_local_operations") is True:
        return True
    allowed_classes = policy.get("allowed_data_classes", [])
    return isinstance(allowed_classes, list) and "human_data" in allowed_classes


def evaluate_trust(root: str | Path, scan_result: dict[str, Any]) -> dict[str, Any]:
    path = trust_policy_path(root)
    policy = read_json(path)
    has_human_data = human_data_detected(scan_result)
    blockers: list[str] = []

    if policy and policy.get("_invalid"):
        blockers.append("Trust policy exists but is not valid JSON.")
    if has_human_data and not policy_allows_human_data(policy):
        blockers.append("Human data is detected, but .dogma/trust.json does not explicitly allow local operations.")

    status = "not_required"
    if has_human_data:
        status = "trusted" if not blockers else "untrusted"

    return {
        "status": status,
        "trusted": not blockers,
        "human_data": has_human_data,
        "policy_path": str(path),
        "policy_present": policy is not None and not policy.get("_invalid", False),
        "policy": None if policy is None or policy.get("_invalid") else policy,
        "blockers": blockers,
        "required_for": [
            "local workflow dry-run/stub-run execution",
            "local service patch application",
        ],
    }


def default_trust_policy(reason: str = "User explicitly trusted this workspace for local Dogma operations.") -> dict[str, Any]:
    return {
        "version": "0.1.0",
        "trusted": True,
        "allow_local_operations": True,
        "allowed_data_classes": ["human_data"],
        "created_by": "Dogma",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "scope": "current workspace only",
    }


def write_trust_policy(root: str | Path, reason: str | None = None) -> dict[str, Any]:
    path = trust_policy_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    policy = default_trust_policy(reason or "User explicitly trusted this workspace for local Dogma operations.")
    path.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "status": "written",
        "policy_path": str(path),
        "policy": policy,
    }
