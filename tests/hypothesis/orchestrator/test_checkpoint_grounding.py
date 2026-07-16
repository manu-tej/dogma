from quration.hypothesis.orchestrator.checkpoint import MethodChoice


def _choice(**kw):
    base = dict(method_id="m", name="m", score=0.5, source="structural",
                rationale="r")
    base.update(kw)
    return MethodChoice(**base)


def test_grounding_defaults_to_none():
    assert _choice().grounding is None


def test_grounding_is_settable():
    assert _choice(grounding="# ctx").grounding == "# ctx"
