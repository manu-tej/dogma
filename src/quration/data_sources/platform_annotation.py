"""GEO platform (GPL) annotation: probe id -> gene symbol.

GEO series matrices are usually indexed by platform probe ids (e.g. ``1007_s_at``).
To correlate genes by symbol we need the platform's probe->symbol table, served as
a SOFT document with a ``!platform_table_begin``/``!platform_table_end`` block.
"""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

# Candidate header names for the gene-symbol column, in preference order.
_SYMBOL_COLUMNS = ("gene symbol", "gene_symbol", "symbol", "genesymbol")
_SOFT_URL = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi"


def parse_platform_table(soft_text: str) -> dict[str, str]:
    """Parse a GPL SOFT document into a ``probe_id -> gene_symbol`` mapping."""
    lines = soft_text.splitlines()
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == "!platform_table_begin")
    except StopIteration:
        return {}
    header = lines[start + 1].split("\t")
    lower = [h.strip().lower() for h in header]
    if "id" not in lower:
        return {}
    id_idx = lower.index("id")
    sym_idx = next((lower.index(c) for c in _SYMBOL_COLUMNS if c in lower), None)
    if sym_idx is None:
        return {}

    mapping: dict[str, str] = {}
    for ln in lines[start + 2:]:
        if ln.strip() == "!platform_table_end":
            break
        cols = ln.split("\t")
        if len(cols) <= max(id_idx, sym_idx):
            continue
        probe = cols[id_idx].strip()
        # Symbols can be "A /// B" (multi-mapping probes); keep the first.
        symbol = cols[sym_idx].strip().split(" /// ")[0].strip()
        if probe and symbol:
            mapping[probe] = symbol
    return mapping


def _default_fetch(gpl_id: str) -> str:
    # view=full returns the complete probe table; view=quick truncates it to a preview.
    resp = requests.get(
        _SOFT_URL,
        params={"acc": gpl_id, "targ": "self", "form": "text", "view": "full"},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.text


_CACHE: dict[str, dict[str, str]] = {}


def fetch_platform_annotation(gpl_id: str, fetch_fn=None) -> dict[str, str]:
    """Fetch + parse a platform's probe->symbol map. Best-effort: {} on any failure.

    The default (network) fetch is cached per platform — annotation tables are
    large (~10MB) and stable, so repeated approves don't re-download.
    """
    if fetch_fn is None and gpl_id in _CACHE:
        return _CACHE[gpl_id]
    try:
        mapping = parse_platform_table((fetch_fn or _default_fetch)(gpl_id))
    except Exception as exc:
        logger.warning("platform annotation fetch failed for %s: %s", gpl_id, exc)
        mapping = {}
    if fetch_fn is None and mapping:
        _CACHE[gpl_id] = mapping
    return mapping
