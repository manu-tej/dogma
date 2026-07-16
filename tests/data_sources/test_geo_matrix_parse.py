"""Regression test for series-matrix parsing: quoted ID_REF header + table_end + platform id."""

import gzip

from quration.data_sources.geo_matrix import GEOMatrixDownloader

# A minimal GEO series matrix: metadata (! lines, one with many tab fields), a
# quoted "ID_REF" header, two probe rows, then the table-end marker.
_SERIES = (
    '!Series_title\t"Demo"\n'
    '!Series_platform_id\t"GPL570"\n'
    '!Sample_geo_accession\t"GSM1"\t"GSM2"\t"GSM3"\n'
    '!series_matrix_table_begin\n'
    '"ID_REF"\t"GSM1"\t"GSM2"\t"GSM3"\n'
    '"1007_s_at"\t1.0\t2.0\t3.0\n'
    '"1053_at"\t3.0\t2.0\t1.0\n'
    '!series_matrix_table_end\n'
)


def test_parse_series_matrix_handles_quoted_header_and_platform():
    content = gzip.compress(_SERIES.encode("utf-8"))
    # _parse_series_matrix takes raw (uncompressed) bytes.
    matrix = GEOMatrixDownloader()._parse_series_matrix(
        _SERIES.encode("utf-8"), "GSE1", "http://x")
    assert matrix.platform_id == "GPL570"
    assert matrix.gene_ids == ["1007_s_at", "1053_at"]
    assert matrix.sample_ids == ["GSM1", "GSM2", "GSM3"]
    assert list(matrix.matrix_data.loc["1007_s_at"]) == [1.0, 2.0, 3.0]
    # the table-end marker is not parsed as a data row
    assert "!series_matrix_table_end" not in matrix.gene_ids
    assert content  # (compression sanity; raw path is what the parser consumes)
