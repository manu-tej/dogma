# tests/hypothesis/connectors/test_collectri.py
"""Tests for the CollecTRI connector (parsing OmniPath rows into signed edges)."""

from quration.hypothesis.connectors.collectri import CollecTRIClient, CollecTRIEdgeSuggester
from quration.hypothesis.graph import EdgeState, NodeType

_COLS = [
    "source", "target", "source_genesymbol", "target_genesymbol", "is_directed",
    "is_stimulation", "is_inhibition", "consensus_direction", "consensus_stimulation",
    "consensus_inhibition", "sources", "references",
]
_ROWS = [
    # JUN -> ESR1, activating, two PMIDs
    [
        "P05412", "P03372", "JUN", "ESR1",
        "True", "True", "False", "True", "True", "False",
        "CollecTRI", "11pmid;22pmid",
    ],
    # FOS -> KRAS, inhibiting
    [
        "P01100", "P01116", "FOS", "KRAS",
        "True", "False", "True", "True", "False", "True",
        "CollecTRI", "33pmid",
    ],
    # complex TF (underscore) -> must be skipped in v1
    [
        "P15407_P17275", "P03372", "FOSL1_JUNB", "ESR1",
        "True", "True", "False", "True", "True", "False",
        "CollecTRI", "44pmid",
    ],
]
_TSV = "\t".join(_COLS) + "\n" + "\n".join("\t".join(r) for r in _ROWS) + "\n"


def _suggester(tsv=_TSV):
    return CollecTRIEdgeSuggester(CollecTRIClient(fetch=lambda: tsv))


def test_expand_builds_signed_activating_edge_with_pmid():
    result = _suggester().expand(["P05412"])
    assert len(result.edges) == 1
    e = result.edges[0]
    assert e.id == "collectri-P05412-P03372"
    assert e.source_id == "P05412" and e.target_id == "P03372"
    assert e.relation == "activates"
    assert e.pending is True and e.state == EdgeState.UNTESTED
    assert e.suggested_by[0].source == "collectri"
    assert e.suggested_by[0].reference == "11pmid"  # first PMID only
    jun = next(n for n in result.nodes if n.id == "P05412")
    assert jun.label == "JUN" and jun.type == NodeType.TARGET
    assert jun.grounding.ontology == "UniProt" and jun.grounding.term_id == "P05412"


def test_inhibition_maps_to_inhibits():
    result = _suggester().expand(["P01100"])
    assert result.edges[0].relation == "inhibits"


def test_complex_rows_are_skipped():
    result = _suggester().expand(["P15407_P17275"])
    assert result.edges == []


def test_expand_matches_seed_as_target_too():
    result = _suggester().expand(["P03372"])  # ESR1 appears as a target of JUN
    assert {e.id for e in result.edges} == {"collectri-P05412-P03372"}


def test_load_failure_yields_empty():
    def boom():
        raise RuntimeError("omnipath down")

    s = CollecTRIEdgeSuggester(CollecTRIClient(fetch=boom))
    assert s.expand(["P05412"]).edges == []


def test_check_pair_returns_signed_edge_on_hit():
    edge = _suggester().check_pair("P05412", "P03372")
    assert edge is not None and edge.relation == "activates"
    assert _suggester().check_pair("P05412", "P99999") is None


def test_dual_sign_row_prefers_activates():
    cols = "\t".join(_COLS)
    row = "\t".join(["P05412", "P03372", "JUN", "ESR1", "True", "True", "True",
                     "True", "True", "True", "CollecTRI", "55pmid"])
    tsv = cols + "\n" + row + "\n"
    result = _suggester(tsv).expand(["P05412"])
    assert result.edges[0].relation == "activates"


def test_disk_cached_fetch_writes_then_reads(tmp_path):
    from quration.hypothesis.connectors.collectri import disk_cached_fetch

    calls = []

    def fake():
        calls.append(1)
        return _TSV

    path = str(tmp_path / "out.tsv")
    r1 = disk_cached_fetch(cache_path=path, fetch=fake)
    r2 = disk_cached_fetch(cache_path=path, fetch=fake)  # served from disk; no 2nd fetch
    assert r1 == r2 == _TSV
    assert len(calls) == 1


def test_license_constant_declared():
    from quration.hypothesis.connectors.collectri import COLLECTRI_LICENSE

    assert "commercial" in COLLECTRI_LICENSE
