"""An edge must say who actually proposed it.

`Edge.proposal_source` defaulted to LLM, which claimed a model had proposed
every edge including ones no model had touched. Changing the default to SYSTEM
fixed that, and introduced the mirror-image error: `HypothesisLoop.start`'s
suggesters never stamped anything, so a graph freshly authored by a model came
back reporting `proposal_source: "system"` — "a derivation".

It errs safe, understating rather than overstating. But it erases the single
distinction the enum exists to make: a consumer could not tell a model's
hypothesis from a deterministic derivation, which is exactly what someone
deciding how much to trust an edge needs to know.

`build_from_skeleton` had the stamping logic inline and correct. That is *why*
this went unnoticed — one of the two entry points was right, so the field looked
implemented. The three sites now share one helper.
"""

from __future__ import annotations

import pytest

from quration.hypothesis.epistemics import EdgeValidationStatus, ProposalSource
from quration.hypothesis.graph import Edge, mark_llm_authored


def edge(**kw) -> Edge:
    return Edge(id=kw.pop("id", "e1"), source_id="a", target_id="b",
                relation="drives", **kw)


class TestTheHelper:
    def test_it_stamps_llm(self):
        assert mark_llm_authored([edge()])[0].proposal_source is ProposalSource.LLM

    def test_it_overwrites_the_system_default(self):
        """The default an unstamped edge carries, which is the bug's shape."""
        e = edge()
        assert e.proposal_source is ProposalSource.SYSTEM
        assert mark_llm_authored([e])[0].proposal_source is ProposalSource.LLM

    def test_a_fresh_seed_is_unvalidated(self):
        """However the skeleton arrived, a seed is a draft. Validation happens
        later against a KG, a dataset or the literature — never at seed time."""
        e = mark_llm_authored(
            [edge(validation_status=EdgeValidationStatus.KG_SUPPORTED_DIRECT)]
        )[0]
        assert e.validation_status is EdgeValidationStatus.UNVALIDATED
        assert e.validations == []

    def test_it_returns_the_same_objects(self):
        """Callers pass the list straight into SuggestionResult; a copy would
        stamp something the graph never sees."""
        given = [edge()]
        assert mark_llm_authored(given)[0] is given[0]

    def test_an_empty_list_is_fine(self):
        assert mark_llm_authored([]) == []


class _Skeleton:
    def __init__(self, edges):
        self.nodes = []
        self.edges = edges


class _Seeding:
    def __init__(self, edges):
        self._edges = edges

    def author_skeleton(self, query):
        return _Skeleton(self._edges)


class TestTheStartPathStampsWhatTheModelWrote:
    def test_the_authoring_suggester_stamps_llm(self):
        """The `/hypothesis/start` primary path. Returned SYSTEM before."""
        from quration.hypothesis.orchestrator.authoring_suggester import (
            LlmAuthoringSuggester,
        )

        result = LlmAuthoringSuggester(_Seeding([edge()])).expand([], query="does x?")
        assert result.edges[0].proposal_source is ProposalSource.LLM

    def test_the_empty_kg_fallback_stamps_llm(self):
        """The other `/start` path, which had the same gap."""
        from quration.hypothesis.orchestrator.real_pipeline import (
            _skeleton_to_suggestion,
        )

        result = _skeleton_to_suggestion(_Skeleton([edge()]))
        assert result.edges[0].proposal_source is ProposalSource.LLM


class TestOtherSourcesAreNotOverwritten:
    """The fix must not become the original bug again: stamping LLM everywhere
    is precisely what made demo content claim a model had run."""

    def test_demo_edges_still_report_demo(self):
        from quration.hypothesis.orchestrator.demo import build_demo_loop
        from quration.hypothesis.repository import InMemoryHypothesisRepository

        loop = build_demo_loop(repository=InMemoryHypothesisRepository())
        result = loop.start("does anything drive anything?")
        graph = loop.get_graph(result.graph_id)
        sources = {e.proposal_source for e in graph.edges}
        assert ProposalSource.LLM not in sources, (
            "demo content is claiming a model proposed it — the exact "
            "fabrication the DEMO source was added to prevent"
        )
        assert sources == {ProposalSource.DEMO}

    @pytest.mark.parametrize(
        "source", [ProposalSource.KG, ProposalSource.USER, ProposalSource.DEMO]
    )
    def test_the_helper_is_only_applied_where_a_model_authored(self, source):
        """Documents the contract: this helper is not a blanket normaliser. A KG
        or user edge passed through it would be mislabelled, so callers must only
        use it on output they got from a model."""
        e = mark_llm_authored([edge(proposal_source=source)])[0]
        assert e.proposal_source is ProposalSource.LLM
