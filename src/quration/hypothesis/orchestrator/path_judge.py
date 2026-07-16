# src/quration/hypothesis/orchestrator/path_judge.py
"""LLM judge that picks the most query-relevant candidate path per seed pair.

One batched create_message call. An enhancer, not a dependency: any failure or
unparseable / out-of-range output falls back to the first (shortest) candidate.
"""

import json
import logging

from quration.hypothesis.graph import Edge

logger = logging.getLogger(__name__)

_JUDGE_SYSTEM = """You pick the most biologically relevant causal path for a research question.
For each numbered pair you are given several candidate paths (also numbered). Choose the path that
best explains the question's mechanism — prefer specific signaling over generic hubs (ubiquitin,
common cofactors). Reply with ONLY a JSON object mapping each pair index (string) to the chosen
path index (integer), e.g. {"0": 1, "1": 0}. No prose."""


def _render_path(path: list[Edge], labels: dict[str, str]) -> str:
    def lbl(node_id: str) -> str:
        return labels.get(node_id, node_id)
    parts = [lbl(path[0].source_id)]
    for e in path:
        parts.append(f"→{e.relation}→ {lbl(e.target_id)}")
    return " ".join(parts)


def _extract_json_object(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.endswith("```"):
            t = t[: t.rfind("```")]
        t = t.strip()
    try:
        json.loads(t)
        return t
    except json.JSONDecodeError:
        start, end = t.find("{"), t.rfind("}")
        return t[start : end + 1] if start != -1 and end > start else t


class PathJudge:
    def __init__(self, provider, model: str):
        self._provider = provider
        self._model = model

    def select(self, query, candidates, labels):
        # Drop pairs with no candidates; index the rest for the prompt.
        pairs = [(pair, cands) for pair, cands in candidates.items() if cands]
        if not pairs:
            return {}
        chosen = {pair: cands[0] for pair, cands in pairs}  # default: shortest
        picks = self._ask(query, pairs, labels)
        for i, (pair, cands) in enumerate(pairs):
            j = picks.get(str(i))
            if isinstance(j, int) and 0 <= j < len(cands):
                chosen[pair] = cands[j]
        return chosen

    def _ask(self, query, pairs, labels):
        lines = [f"Question: {query}", ""]
        for i, (_pair, cands) in enumerate(pairs):
            lines.append(f"Pair {i}:")
            for j, path in enumerate(cands):
                lines.append(f"  [{j}] {_render_path(path, labels)}")
        try:
            raw = self._provider.create_message(
                messages=[{"role": "user", "content": "\n".join(lines)}],
                model=self._model, system=_JUDGE_SYSTEM, temperature=0.0,
            )
            return json.loads(_extract_json_object(raw))
        except Exception:
            logger.warning("path judge failed; using shortest candidates", exc_info=True)
            return {}
