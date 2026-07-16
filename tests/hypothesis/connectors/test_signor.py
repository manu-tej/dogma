"""Tests for the SIGNOR client (parsing raw rows into normalized records)."""

import pytest

from quration.hypothesis.connectors.base import SignorConnectorError
from quration.hypothesis.connectors.signor import SignorClient, SignorEdgeSuggester, SignorRecord
from quration.hypothesis.graph import EdgeState, NodeType

# Raw rows keyed by SIGNOR flat-file column names. Two valid protein->protein
# rows plus one non-protein row that must be skipped.
_RAW = [
    {
        "ENTITYA": "EGFR", "TYPEA": "protein", "IDA": "P00533",
        "ENTITYB": "KRAS", "TYPEB": "protein", "IDB": "P01116",
        "EFFECT": "up-regulates activity", "MECHANISM": "phosphorylation",
        "SIGNOR_ID": "SIGNOR-100", "PMID": "12345678",
    },
    {
        "ENTITYA": "EGFR", "TYPEA": "protein", "IDA": "P00533",
        "ENTITYB": "GRB2", "TYPEB": "protein", "IDB": "P62993",
        "EFFECT": "down-regulates", "MECHANISM": "binding",
        "SIGNOR_ID": "SIGNOR-101", "PMID": "",
    },
    {
        "ENTITYA": "EGFR", "TYPEA": "protein", "IDA": "P00533",
        "ENTITYB": "ATP", "TYPEB": "chemical", "IDB": "CHEBI:15422",
        "EFFECT": "binds", "MECHANISM": "", "SIGNOR_ID": "SIGNOR-102", "PMID": "",
    },
]


def _client(rows):
    return SignorClient(raw_fetch=lambda entity: rows)


def test_fetch_parses_protein_rows_into_records():
    records = _client(_RAW).fetch_interactions("EGFR")
    # the chemical row is skipped -> 2 protein->protein records
    assert len(records) == 2
    assert all(isinstance(r, SignorRecord) for r in records)
    first = records[0]
    assert first.regulator_id == "P00533"
    assert first.regulator_label == "EGFR"
    assert first.target_id == "P01116"
    assert first.target_label == "KRAS"
    assert first.effect == "up-regulates activity"
    assert first.signor_id == "SIGNOR-100"
    assert first.pmid == "12345678"


def test_empty_pmid_becomes_none():
    records = _client(_RAW).fetch_interactions("EGFR")
    grb2 = next(r for r in records if r.target_id == "P62993")
    assert grb2.pmid is None


def test_no_interactions_returns_empty_list():
    assert _client([]).fetch_interactions("NOBODY") == []


def test_fetch_failure_raises_connector_error():
    def boom(entity):
        raise RuntimeError("network down")

    client = SignorClient(raw_fetch=boom)
    with pytest.raises(SignorConnectorError, match="SIGNOR fetch failed"):
        client.fetch_interactions("EGFR")


def test_expand_maps_records_to_nodes_and_edges():
    suggester = SignorEdgeSuggester(_client(_RAW))
    result = suggester.expand(["EGFR"])

    # 2 protein edges (SIGNOR-100, SIGNOR-101); nodes deduped (EGFR shared) -> 3 nodes
    assert {e.id for e in result.edges} == {"SIGNOR-100", "SIGNOR-101"}
    assert {n.id for n in result.nodes} == {"P00533", "P01116", "P62993"}

    edge = next(e for e in result.edges if e.id == "SIGNOR-100")
    assert edge.source_id == "P00533"
    assert edge.target_id == "P01116"
    assert edge.relation == "up-regulates activity"
    assert edge.state == EdgeState.UNTESTED
    assert edge.confidence == 0.0
    assert edge.pending is True
    assert edge.suggested_by[0].source == "signor"
    assert edge.suggested_by[0].reference == "SIGNOR-100"

    egfr = next(n for n in result.nodes if n.id == "P00533")
    assert egfr.type == NodeType.TARGET
    assert egfr.label == "EGFR"
    assert egfr.grounding.ontology == "UniProt"
    assert egfr.grounding.term_id == "P00533"


def test_expand_dedupes_across_multiple_seeds():
    suggester = SignorEdgeSuggester(_client(_RAW))
    result = suggester.expand(["EGFR", "EGFR"])  # same rows returned twice
    assert len(result.edges) == 2
    assert len(result.nodes) == 3


def test_expand_never_sets_confidence():
    result = SignorEdgeSuggester(_client(_RAW)).expand(["EGFR"])
    assert all(e.confidence == 0.0 and e.state == EdgeState.UNTESTED for e in result.edges)


def test_check_pair_returns_edge_on_hit():
    suggester = SignorEdgeSuggester(_client(_RAW))
    edge = suggester.check_pair("EGFR", "P01116")  # EGFR -> KRAS
    assert edge is not None
    assert edge.id == "SIGNOR-100"
    assert edge.source_id == "P00533"
    assert edge.target_id == "P01116"


def test_check_pair_returns_none_on_miss():
    suggester = SignorEdgeSuggester(_client(_RAW))
    assert suggester.check_pair("EGFR", "P99999") is None


def test_default_fetch_is_wired_as_a_callable():
    from quration.hypothesis.connectors.signor import default_signor_fetch

    assert callable(default_signor_fetch)


def test_check_pair_ignores_rows_where_source_is_not_regulator():
    # Row GRB2 -> KRAS; the queried source (EGFR) is NOT the regulator.
    # check_pair must NOT return this edge even though the fake client returns it.
    rows = [
        {
            "ENTITYA": "GRB2", "TYPEA": "protein", "IDA": "P62993",
            "ENTITYB": "KRAS", "TYPEB": "protein", "IDB": "P01116",
            "EFFECT": "binds", "MECHANISM": "", "SIGNOR_ID": "SIGNOR-200", "PMID": "",
        }
    ]
    suggester = SignorEdgeSuggester(_client(rows))
    assert suggester.check_pair("EGFR", "P01116") is None
