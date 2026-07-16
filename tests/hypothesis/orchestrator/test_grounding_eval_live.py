import os
import pytest

pytest.importorskip("methods_graph")


@pytest.mark.skipif(not os.environ.get("QURATION_METHODS_GRAPH_DB"), reason="no methods-graph DB")
def test_live_grounding_returns_assumptions_for_rnaseq():
    from pathlib import Path
    from methods_graph.provider.quration_provider import KuzuMethodsGraphProvider
    from quration.hypothesis.orchestrator.grounding_eval import ground_edge

    provider = KuzuMethodsGraphProvider(Path(os.environ["QURATION_METHODS_GRAPH_DB"]))
    res = ground_edge(provider, "up-regulates")
    assert res.verdict in ("GROUNDED", "PARTIALLY_GROUNDED", "COVERAGE_GAP")
