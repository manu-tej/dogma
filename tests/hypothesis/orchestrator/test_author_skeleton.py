# tests/hypothesis/orchestrator/test_author_skeleton.py
"""Tests for forced skeleton authoring (the empty-KG fallback)."""

from quration.hypothesis.orchestrator.seeding import LlmSeedingService


class FakeProvider:
    def __init__(self, response):
        self.response = response

    def create_message(self, **kwargs):
        return self.response


def test_author_skeleton_returns_pending_skeleton():
    resp = (
        '{"rationale":"EGFR drives resistance",'
        '"nodes":[{"id":"egfr","type":"target","label":"EGFR"},'
        '{"id":"res","type":"phenotype","label":"resistance"}],'
        '"edges":[{"id":"e1","source_id":"egfr","target_id":"res","relation":"drives"}]}'
    )
    svc = LlmSeedingService(FakeProvider(resp), "model")
    sk = svc.author_skeleton("does EGFR drive resistance?")
    assert [n.id for n in sk.nodes] == ["egfr", "res"]
    assert sk.edges[0].relation == "drives"
    assert sk.edges[0].pending is True


def test_author_skeleton_tolerates_code_fences():
    resp = (
        '```json\n{"rationale":"r","nodes":[{"id":"a","type":"target","label":"A"}]'
        ',"edges":[]}\n```'
    )
    svc = LlmSeedingService(FakeProvider(resp), "model")
    sk = svc.author_skeleton("q")
    assert [n.id for n in sk.nodes] == ["a"]
