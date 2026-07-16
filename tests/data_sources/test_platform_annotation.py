"""Tests for GEO platform (GPL) probe -> gene-symbol annotation parsing."""

from quration.data_sources.platform_annotation import (
    fetch_platform_annotation,
    parse_platform_table,
)

_SOFT = """^PLATFORM = GPL96
!Platform_title = Affymetrix Human Genome U133A Array
!platform_table_begin
ID\tGB_ACC\tGene Title\tGene Symbol\tENTREZ_GENE_ID
1007_s_at\tU48705\tdiscoidin domain receptor\tDDR1\t780
1053_at\tM87338\treplication factor C\tRFC2\t5982
117_at\tX51757\theat shock protein\tHSPA6\t3310
nosymbol_at\tZZZ\t\t\t
!platform_table_end
"""


def test_parse_platform_table_maps_probe_to_symbol():
    mapping = parse_platform_table(_SOFT)
    assert mapping["1007_s_at"] == "DDR1"
    assert mapping["1053_at"] == "RFC2"
    assert mapping["117_at"] == "HSPA6"
    # rows with an empty symbol are dropped
    assert "nosymbol_at" not in mapping


def test_parse_platform_table_handles_alternate_symbol_header():
    soft = _SOFT.replace("Gene Symbol", "GENE_SYMBOL")
    assert parse_platform_table(soft)["1007_s_at"] == "DDR1"


def test_parse_platform_table_no_symbol_column_is_empty():
    soft = _SOFT.replace("Gene Symbol", "Something Else")
    assert parse_platform_table(soft) == {}


def test_fetch_platform_annotation_uses_injected_fetcher():
    calls = {}
    def fake_fetch(gpl_id):
        calls["gpl"] = gpl_id
        return _SOFT
    mapping = fetch_platform_annotation("GPL96", fetch_fn=fake_fetch)
    assert calls["gpl"] == "GPL96"
    assert mapping["1053_at"] == "RFC2"


def test_fetch_platform_annotation_failure_returns_empty():
    def boom(gpl_id):
        raise RuntimeError("network down")
    assert fetch_platform_annotation("GPL96", fetch_fn=boom) == {}
