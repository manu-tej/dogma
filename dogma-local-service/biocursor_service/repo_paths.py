"""Repository path helpers for Dogma's local service."""

from __future__ import annotations

import os
from pathlib import Path


def dogma_repo_root() -> str:
    for name in ("DOGMA_REPO", "QURATION_REPO"):
        value = os.environ.get(name)
        if value:
            return str(Path(value).expanduser().resolve())

    for parent in Path(__file__).resolve().parents:
        if (parent / "frontend").exists() and (parent / "src").exists():
            return str(parent)

    return str(Path(__file__).resolve().parents[2])


def methods_graph_repo_root() -> str:
    value = os.environ.get("DOGMA_METHODS_GRAPH_REPO") or os.environ.get("METHODS_GRAPH_REPO")
    if value:
        return str(Path(value).expanduser().resolve())
    return str((Path(dogma_repo_root()).parent / "methods-graph").resolve())
