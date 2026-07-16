# tests/hypothesis/connectors/test_network.py
"""Tests for the Network adapters (connectors as a traversable directed graph)."""

from quration.hypothesis.connectors.collectri import CollecTRIClient
from quration.hypothesis.connectors.network import (
    CollecTRINetwork,
    CombinedNetwork,
    SignorNetwork,
)
from quration.hypothesis.connectors.signor import SignorClient

_SIGNOR_ROWS = [
    {"ENTITYA": "EGFR", "TYPEA": "protein", "IDA": "P00533",
     "ENTITYB": "KRAS", "TYPEB": "protein", "IDB": "P01116",
     "EFFECT": "up-regulates", "MECHANISM": "", "SIGNOR_ID": "SIG-1", "PMID": "111"},
    {"ENTITYA": "USP8", "TYPEA": "protein", "IDA": "P40818",
     "ENTITYB": "EGFR", "TYPEB": "protein", "IDB": "P00533",
     "EFFECT": "down-regulates", "MECHANISM": "", "SIGNOR_ID": "SIG-2", "PMID": "222"},
]


def _signor_net(rows):
    # getData.php returns ALL rows touching the queried id; our fake returns the
    # rows whose IDA or IDB equals the entity.
    def fetch(entity):
        return [r for r in rows if entity in (r["IDA"], r["IDB"])]
    return SignorNetwork(SignorClient(raw_fetch=fetch))


def test_signor_out_and_in_from_one_fetch():
    net = _signor_net(_SIGNOR_ROWS)
    out = net.out_edges("P00533")   # EGFR as regulator -> KRAS
    assert [(n.node_id, n.label) for n in out] == [("P01116", "KRAS")]
    assert out[0].edge.source_id == "P00533" and out[0].edge.target_id == "P01116"
    inc = net.in_edges("P00533")    # USP8 -> EGFR
    assert [(n.node_id, n.label) for n in inc] == [("P40818", "USP8")]
    assert inc[0].edge.target_id == "P00533"


def test_signor_label_memoized_and_fallback():
    net = _signor_net(_SIGNOR_ROWS)
    net.out_edges("P00533")
    assert net.label("P01116") == "KRAS"
    assert net.label("UNKNOWN") == "UNKNOWN"   # falls back to the id


def test_signor_fetch_failure_yields_empty():
    def boom(entity):
        raise RuntimeError("net down")
    net = SignorNetwork(SignorClient(raw_fetch=boom))
    assert net.out_edges("P00533") == [] and net.in_edges("P00533") == []


_COLLECTRI_TSV = "\t".join(
    ["source", "target", "source_genesymbol", "target_genesymbol", "is_directed",
     "is_stimulation", "is_inhibition", "consensus_direction", "consensus_stimulation",
     "consensus_inhibition", "sources", "references"]) + "\n" + "\n".join([
    "\t".join(["P01116", "P09619", "KRAS", "PDGFRB", "True", "True", "False",
               "True", "True", "False", "CollecTRI", "333"]),
])


def _collectri_net(tsv=_COLLECTRI_TSV):
    return CollecTRINetwork(CollecTRIClient(fetch=lambda: tsv))


def test_collectri_out_in_and_label():
    net = _collectri_net()
    out = net.out_edges("P01116")   # KRAS -> PDGFRB
    assert [(n.node_id, n.label) for n in out] == [("P09619", "PDGFRB")]
    assert out[0].edge.relation == "activates"
    inc = net.in_edges("P09619")
    assert [n.node_id for n in inc] == ["P01116"]
    assert net.label("P01116") == "KRAS"


def test_combined_merges_both_sources():
    combined = CombinedNetwork([_signor_net(_SIGNOR_ROWS), _collectri_net()])
    # EGFR(P00533) out -> KRAS via SIGNOR; KRAS(P01116) out -> PDGFRB via CollecTRI
    assert {n.node_id for n in combined.out_edges("P00533")} == {"P01116"}
    assert {n.node_id for n in combined.out_edges("P01116")} == {"P09619"}
    assert combined.label("P09619") == "PDGFRB"


def test_collectri_fetch_failure_yields_empty():
    def boom():
        raise RuntimeError("omnipath down")

    net = CollecTRINetwork(CollecTRIClient(fetch=boom))
    assert net.out_edges("P01116") == [] and net.in_edges("P09619") == []


def test_combined_in_edges_from_both_sources():
    combined = CombinedNetwork([_signor_net(_SIGNOR_ROWS), _collectri_net()])
    assert {n.node_id for n in combined.in_edges("P01116")} == {"P00533"}   # EGFR->KRAS
    assert {n.node_id for n in combined.in_edges("P09619")} == {"P01116"}   # KRAS->PDGFRB


def test_combined_dedupes_identical_edges():
    net = _signor_net(_SIGNOR_ROWS)
    combined = CombinedNetwork([net, net])   # same edges twice
    assert len(combined.out_edges("P00533")) == 1   # deduped by (source, target, relation)
