# src/quration/hypothesis/connectors/collectri.py
"""CollecTRI connector: signed TF->gene regulatory edges via the OmniPath REST API.

OmniPath serves CollecTRI (saezlab) with UniProt-accession-keyed source/target,
is_stimulation/is_inhibition sign, and per-edge PMID references. The commercial
subset equals the academic one (verified 2026-06-16), so we always request
license=commercial. v1: single-protein endpoints only (complex rows like
"P15407_P17275" are skipped, mirroring SIGNOR's protein-only v1 filter).
"""

import csv
import io
import logging
import os
from collections.abc import Callable

import requests

from quration.hypothesis.connectors.base import SuggestionResult
from quration.hypothesis.graph import Edge, Node, NodeType
from quration.hypothesis.provenance import KGEdgeProvenance, OntologyTermProvenance

logger = logging.getLogger(__name__)

COLLECTRI_URL = "https://omnipathdb.org/interactions"
COLLECTRI_LICENSE = "commercial subset (license=commercial)"
_TIMEOUT_S = 120
_DEFAULT_CACHE_PATH = "./data/collectri_commercial.tsv"

TsvFetch = Callable[[], str]


def default_collectri_fetch() -> str:
    """Fetch the full CollecTRI commercial interaction table (TSV text) from OmniPath."""
    response = requests.get(
        COLLECTRI_URL,
        params={
            "datasets": "collectri",
            "license": "commercial",
            "genesymbols": "1",
            "fields": "sources,references",
        },
        timeout=_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.text


def disk_cached_fetch(
    cache_path: str = _DEFAULT_CACHE_PATH, fetch: TsvFetch = default_collectri_fetch
) -> str:
    """Return the CollecTRI TSV from disk if present, else fetch once and persist it."""
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as fh:
            return fh.read()
    text = fetch()
    try:
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    except OSError:
        logger.warning("could not persist CollecTRI cache to %s", cache_path, exc_info=True)
    return text


def _default_fetch() -> str:
    """Zero-arg TsvFetch: the disk-cached OmniPath fetch with default paths."""
    return disk_cached_fetch()


class CollecTRIClient:
    """Loads + indexes CollecTRI rows by endpoint accession (in-process memoized)."""

    def __init__(self, fetch: TsvFetch | None = None):
        self._fetch = fetch or _default_fetch
        self._index: dict[str, list[dict]] | None = None

    def index(self) -> dict[str, list[dict]]:
        if self._index is None:
            self._index = self._build_index(self._fetch())
        return self._index

    @staticmethod
    def _build_index(tsv_text: str) -> dict[str, list[dict]]:
        reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")
        index: dict[str, list[dict]] = {}
        for row in reader:
            source, target = row.get("source", ""), row.get("target", "")
            # v1: single-protein endpoints only (skip TF complexes "P1_P2").
            if not source or not target or "_" in source or "_" in target:
                continue
            index.setdefault(source, []).append(row)
            if target != source:
                index.setdefault(target, []).append(row)
        return index


def _relation(row: dict) -> str:
    # When a row carries both signs (context-dependent regulators), stimulation
    # takes priority (v1 approximation).
    if row.get("is_stimulation") == "True":
        return "activates"
    if row.get("is_inhibition") == "True":
        return "inhibits"
    return "regulates"


def _row_to_node(accession: str, label: str) -> Node:
    return Node(
        id=accession,
        type=NodeType.TARGET,
        label=label or accession,
        grounding=OntologyTermProvenance(ontology="UniProt", term_id=accession),
    )


def _row_to_edge(row: dict) -> Edge:
    source, target = row["source"], row["target"]
    pmid = (row.get("references", "") or "").split(";")[0].strip()
    return Edge(
        id=f"collectri-{source}-{target}",
        source_id=source,
        target_id=target,
        relation=_relation(row),
        pending=True,
        suggested_by=[KGEdgeProvenance(source="collectri", reference=pmid or "collectri")],
    )


class CollecTRIEdgeSuggester:
    """Suggests signed TF->gene edges from CollecTRI (an EdgeSuggester)."""

    def __init__(self, client: CollecTRIClient | None = None):
        self._client = client or CollecTRIClient()

    def _index(self) -> dict[str, list[dict]]:
        try:
            return self._client.index()
        except Exception:
            logger.warning("CollecTRI load failed; contributing no edges", exc_info=True)
            return {}

    def expand(self, seeds: list[str], query: str | None = None) -> SuggestionResult:
        index = self._index()
        nodes: dict[str, Node] = {}
        edges: dict[str, Edge] = {}
        for seed in seeds:
            for row in index.get(seed, []):
                src, tgt = row["source"], row["target"]
                nodes.setdefault(src, _row_to_node(src, row.get("source_genesymbol", "")))
                nodes.setdefault(tgt, _row_to_node(tgt, row.get("target_genesymbol", "")))
                edge = _row_to_edge(row)
                edges.setdefault(edge.id, edge)
        return SuggestionResult(nodes=list(nodes.values()), edges=list(edges.values()))

    def check_pair(self, source: str, target: str) -> Edge | None:
        for row in self._index().get(source, []):
            if row["source"] == source and row["target"] == target:
                return _row_to_edge(row)
        return None
