from quration.hypothesis.orchestrator.seeding import (
    ClarifyingStep,
    DemoSeedingService,
    SeedAnswer,
    SeedStep,
    SeedingService,
)


def test_demo_asks_questions_when_no_answers():
    svc = DemoSeedingService()
    step = svc.next_step("does EGFR drive resistance?", [])
    assert isinstance(step, ClarifyingStep)
    assert step.kind == "questions"
    assert len(step.questions) >= 1
    q = step.questions[0]
    assert q.id and q.prompt and isinstance(q.suggestions, list)


def test_demo_returns_skeleton_once_answered():
    svc = DemoSeedingService()
    answers = [SeedAnswer(question_id="context", value="lung")]
    step = svc.next_step("does EGFR drive resistance?", answers)
    assert isinstance(step, SeedStep)
    assert step.kind == "seeds"
    node_labels = {n.label for n in step.skeleton.nodes}
    assert {"EGFR", "KRAS", "drug resistance"} <= node_labels
    assert len(step.skeleton.edges) >= 2
    assert all(e.pending for e in step.skeleton.edges)
    assert step.skeleton.rationale


def test_demo_satisfies_protocol():
    assert isinstance(DemoSeedingService(), SeedingService)


import json

from quration.hypothesis.orchestrator.seeding import LlmSeedingService


class _FakeProvider:
    """Stands in for an LLMProvider; returns a canned JSON string."""

    def __init__(self, payload: dict):
        self._payload = payload
        self.last_messages = None
        self.last_system = None

    def create_message(self, messages, model, max_tokens=4096, temperature=1.0,
                       system=None, **kwargs):
        self.last_messages = messages
        self.last_system = system
        return json.dumps(self._payload)


def test_llm_parses_questions_payload():
    provider = _FakeProvider({
        "kind": "questions",
        "questions": [{"id": "context", "prompt": "Which cancer?",
                       "suggestions": ["lung", "colorectal"]}],
    })
    svc = LlmSeedingService(provider=provider, model="m")
    step = svc.next_step("does EGFR drive resistance?", [])
    assert step.kind == "questions"
    assert step.questions[0].id == "context"
    assert "EGFR" in json.dumps(provider.last_messages)


def test_llm_parses_skeleton_payload():
    provider = _FakeProvider({
        "kind": "seeds",
        "skeleton": {
            "rationale": "because",
            "nodes": [
                {"id": "P00533", "type": "target", "label": "EGFR"},
                {"id": "RESIST", "type": "phenotype", "label": "drug resistance"},
            ],
            "edges": [
                {"id": "e1", "source_id": "P00533", "target_id": "RESIST",
                 "relation": "drives"},
            ],
        },
    })
    svc = LlmSeedingService(provider=provider, model="m")
    step = svc.next_step("q", [])
    assert step.kind == "seeds"
    assert {n.label for n in step.skeleton.nodes} == {"EGFR", "drug resistance"}
    assert step.skeleton.edges[0].pending is True


def test_llm_raises_on_unparseable_output():
    provider = _FakeProvider({})  # missing 'kind'
    svc = LlmSeedingService(provider=provider, model="m")
    import pytest
    with pytest.raises(ValueError):
        svc.next_step("q", [])


def test_llm_extracts_json_from_prose_preamble():
    """Smaller/faster models sometimes prepend prose before the JSON object;
    the parser must still recover the payload (regression for the 'fast' tier)."""
    payload = {
        "kind": "questions",
        "questions": [{"id": "context", "prompt": "Which cancer?",
                       "suggestions": ["lung", "colorectal"]}],
    }
    raw = "Based on your question, I can propose a plan.\n" + json.dumps(payload)

    class _ProsePrefixProvider(_FakeProvider):
        def create_message(self, messages, model, max_tokens=4096, temperature=1.0,
                           system=None, **kwargs):
            self.last_messages = messages
            return raw

    svc = LlmSeedingService(provider=_ProsePrefixProvider(payload), model="m")
    step = svc.next_step("does EGFR drive resistance?", [])
    assert step.kind == "questions"
    assert step.questions[0].id == "context"
