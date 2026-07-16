"""Conversational graph seeding: clarifying Q&A then an authored seed skeleton.

The skeleton is authored from the conversation (Model B) — no knowledge-graph
substrate. Two impls behind the SeedingService seam: a deterministic demo and an
LLM-backed one, swapped via DI like the hypothesis loop.
"""

import json
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from quration.hypothesis.graph import Edge, Node, NodeType


class ClarifyingQuestion(BaseModel):
    id: str
    prompt: str
    suggestions: list[str] = Field(default_factory=list)
    allow_free_text: bool = True


class SeedAnswer(BaseModel):
    question_id: str
    value: str


class SeedSkeleton(BaseModel):
    nodes: list[Node]
    edges: list[Edge]
    rationale: str


class ClarifyingStep(BaseModel):
    kind: Literal["questions"] = "questions"
    questions: list[ClarifyingQuestion]


class SeedStep(BaseModel):
    kind: Literal["seeds"] = "seeds"
    skeleton: SeedSkeleton


SeedingStep = ClarifyingStep | SeedStep


@runtime_checkable
class SeedingService(Protocol):
    """Given a query and the answers gathered so far, return the next step:
    more clarifying questions, or the authored seed skeleton."""

    def next_step(self, query: str, answers: list[SeedAnswer]) -> SeedingStep: ...


_DEMO_QUESTIONS = [
    ClarifyingQuestion(
        id="context",
        prompt="What disease context should we focus on?",
        suggestions=["lung", "colorectal", "melanoma"],
    ),
    ClarifyingQuestion(
        id="readout",
        prompt="What phenotype or readout matters most?",
        suggestions=["drug resistance", "proliferation", "apoptosis"],
    ),
]

_DEMO_SKELETON = SeedSkeleton(
    nodes=[
        Node(id="P00533", type=NodeType.TARGET, label="EGFR"),
        Node(id="P01116", type=NodeType.TARGET, label="KRAS"),
        Node(id="RESIST", type=NodeType.PHENOTYPE, label="drug resistance"),
    ],
    edges=[
        Edge(id="e-egfr-kras", source_id="P00533", target_id="P01116",
             relation="up-regulates activity", pending=True),
        Edge(id="e-kras-resist", source_id="P01116", target_id="RESIST",
             relation="drives", pending=True),
    ],
    rationale="EGFR signalling can sustain KRAS activity, a known driver of resistance.",
)


class DemoSeedingService:
    """Deterministic: one round of fixed questions, then the canned skeleton."""

    def next_step(self, query: str, answers: list[SeedAnswer]) -> SeedingStep:
        if not answers:
            return ClarifyingStep(questions=list(_DEMO_QUESTIONS))
        return SeedStep(skeleton=_DEMO_SKELETON.model_copy(deep=True))


_SEEDING_SYSTEM = """You are seeding a causal-hypothesis graph from a user's question.
Decide whether you need to ask clarifying questions or can propose a seed skeleton.

Reply with ONLY a JSON object, no prose, in one of two shapes:

1) {"kind":"questions","questions":[{"id":"<slug>","prompt":"<question>",
     "suggestions":["<chip>", ...]}]}  // 1-3 questions, only if genuinely ambiguous

2) {"kind":"seeds","skeleton":{
     "rationale":"<one sentence>",
     "nodes":[{"id":"<stable-id>","type":"<target|pathway|phenotype|cell_type|tissue|disease|compound|other>",
               "label":"<name>"}],
     "edges":[{"id":"<stable-id>","source_id":"<node-id>","target_id":"<node-id>",
               "relation":"<verb phrase>"}]}}

Once the user has answered, prefer proposing a skeleton. Keep skeletons small (3-6 nodes)."""

_AUTHOR_SYSTEM = """You author a small causal-hypothesis seed skeleton from a user's question.
Reply with ONLY a JSON object (no prose):
{"rationale":"<one sentence>",
 "nodes":[{"id":"<stable-id>","type":"<target|pathway|phenotype|cell_type|tissue|disease|compound|other>",
           "label":"<name>"}],
 "edges":[{"id":"<stable-id>","source_id":"<node-id>","target_id":"<node-id>",
           "relation":"<verb phrase>"}]}
Model the FULL mechanism: include the relevant compound/drug, phenotype, disease, and
pathway nodes (not just proteins) whenever the question implies them. Keep it focused
(6-12 nodes). Always propose a skeleton; never ask questions."""


def _strip_code_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.endswith("```"):
            t = t[: t.rfind("```")]
    return t.strip()


def _extract_json_object(text: str) -> str:
    """Best-effort extraction of a single JSON object from model output.

    Strips code fences first. Smaller/faster models (e.g. the ``fast`` seeding
    tier) sometimes prepend prose before the JSON object — fall back to the
    outermost brace-delimited substring so the payload still parses.
    """
    t = _strip_code_fences(text)
    try:
        json.loads(t)
        return t
    except json.JSONDecodeError:
        start, end = t.find("{"), t.rfind("}")
        if start != -1 and end > start:
            return t[start : end + 1]
        return t


class LlmSeedingService:
    """LLM-authored seeding via an LLMProvider returning structured JSON."""

    def __init__(self, provider, model: str):
        self._provider = provider
        self._model = model

    def next_step(self, query: str, answers: list[SeedAnswer]) -> SeedingStep:
        answer_lines = "\n".join(f"- {a.question_id}: {a.value}" for a in answers)
        user = f"Question: {query}\n\nAnswers so far:\n{answer_lines or '(none yet)'}"
        raw = self._provider.create_message(
            messages=[{"role": "user", "content": user}],
            model=self._model,
            system=_SEEDING_SYSTEM,
            temperature=0.2,
        )
        try:
            payload = json.loads(_extract_json_object(raw))
        except json.JSONDecodeError as exc:
            raise ValueError(f"seeding model returned non-JSON: {raw[:200]}") from exc

        kind = payload.get("kind")
        if kind == "questions":
            return ClarifyingStep.model_validate(payload)
        if kind == "seeds":
            step = SeedStep.model_validate(payload)
            for edge in step.skeleton.edges:
                edge.pending = True  # authored edges are untested candidates
            return step
        raise ValueError(f"seeding model returned unknown kind: {kind!r}")

    def author_skeleton(self, query: str) -> SeedSkeleton:
        """Author a seed skeleton directly (no clarifying questions). Used as the
        empty-KG fallback on the /start path."""
        raw = self._provider.create_message(
            messages=[{"role": "user", "content": f"Question: {query}"}],
            model=self._model,
            system=_AUTHOR_SYSTEM,
            temperature=0.2,
        )
        skeleton = SeedSkeleton.model_validate(json.loads(_extract_json_object(raw)))
        for edge in skeleton.edges:
            edge.pending = True  # authored edges are untested candidates
        return skeleton
