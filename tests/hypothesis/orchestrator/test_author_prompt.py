"""The /start author prompt targets the full mechanism at a relaxed node cap."""

from quration.hypothesis.orchestrator.seeding import _AUTHOR_SYSTEM


def test_author_prompt_relaxed_cap_and_full_mechanism():
    assert "6-12 nodes" in _AUTHOR_SYSTEM
    assert "3-6 nodes" not in _AUTHOR_SYSTEM
    for kind in ("compound", "phenotype", "disease"):
        assert kind in _AUTHOR_SYSTEM
