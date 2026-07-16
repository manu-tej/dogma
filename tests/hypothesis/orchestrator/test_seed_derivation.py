# tests/hypothesis/orchestrator/test_seed_derivation.py
"""Tests for query->accession seed derivation."""

from quration.hypothesis.orchestrator.checkpoint import QueryKind
from quration.hypothesis.orchestrator.seed_derivation import (
    LiveSeedSupervisor,
    LlmSeedDeriver,
)


class FakeProvider:
    def __init__(self, response):
        self.response = response

    def create_message(self, **kwargs):
        return self.response


class _Hit:
    def __init__(self, accession):
        self.uniprot_id = accession


class FakeUniProt:
    """Maps a `gene_exact:SYMBOL ...` query to a canned accession."""

    def __init__(self, mapping):
        self.mapping = mapping

    def search(self, query, organism=None, limit=10):
        symbol = query.split("gene_exact:")[1].split(" ")[0]
        accession = self.mapping.get(symbol)
        return [_Hit(accession)] if accession else []


def _deriver(response, mapping):
    return LlmSeedDeriver(FakeProvider(response), "model", FakeUniProt(mapping))


def test_derive_maps_symbols_to_accessions():
    d = _deriver('["EGFR","KRAS"]', {"EGFR": "P00533", "KRAS": "P01116"})
    assert d.derive("does EGFR drive KRAS resistance?") == ["P00533", "P01116"]


def test_derive_handles_code_fenced_json():
    d = _deriver('```json\n["EGFR"]\n```', {"EGFR": "P00533"})
    assert d.derive("egfr?") == ["P00533"]


def test_derive_dedupes_and_skips_unmapped():
    d = _deriver('["EGFR","EGFR","NOTAGENE"]', {"EGFR": "P00533"})
    assert d.derive("q") == ["P00533"]


def test_derive_returns_empty_on_llm_failure():
    class Boom:
        def create_message(self, **kwargs):
            raise RuntimeError("down")

    d = LlmSeedDeriver(Boom(), "model", FakeUniProt({}))
    assert d.derive("q") == []


def test_live_seed_supervisor_uses_deriver_and_keeps_demo_triage():
    d = _deriver('["EGFR"]', {"EGFR": "P00533"})
    sup = LiveSeedSupervisor(d)
    assert sup.seeds_for("q") == ["P00533"]
    assert sup.triage("q") == QueryKind.INVESTIGATIVE


def test_derive_skips_symbol_on_uniprot_failure():
    class BoomUniProt:
        def search(self, *args, **kwargs):
            raise OSError("timeout")

    d = LlmSeedDeriver(FakeProvider('["EGFR"]'), "model", BoomUniProt())
    assert d.derive("q") == []
