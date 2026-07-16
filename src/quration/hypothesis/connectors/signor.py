"""SIGNOR connector: fetch + parse directed causal relations into graph suggestions.

Raw-row parsing is isolated here behind an injectable `raw_fetch` callable so the
rest of the connector is tested deterministically. The real HTTP+cache fetch is
provided by `default_signor_fetch` (Task 5).

SIGNOR flat-file columns used (confirmed against live sample — Task 5):
  ENTITYA/IDA/TYPEA, ENTITYB/IDB/TYPEB, EFFECT, MECHANISM, SIGNOR_ID, PMID.

Live endpoint (confirmed Task 5):
  GET https://signor.uniroma2.it/getData.php?organism=9606&id=<UniProt_accession>
  Returns headerless TSV (29 columns). `default_signor_fetch` injects fieldnames.
"""

import csv
import io
from collections.abc import Callable

import requests
from pydantic import BaseModel

from quration.hypothesis.connectors.base import SignorConnectorError, SuggestionResult
from quration.hypothesis.graph import Edge, Node, NodeType
from quration.hypothesis.provenance import KGEdgeProvenance, OntologyTermProvenance

RawFetch = Callable[[str], list[dict]]


class SignorRecord(BaseModel):
    """A normalized SIGNOR protein->protein directed relation."""

    regulator_id: str
    regulator_label: str
    regulator_type: str
    target_id: str
    target_label: str
    target_type: str
    effect: str
    mechanism: str | None = None
    signor_id: str
    pmid: str | None = None


def _row_to_record(row: dict) -> SignorRecord:
    def clean(key: str) -> str | None:
        value = (row.get(key) or "").strip()
        return value or None

    return SignorRecord(
        regulator_id=row["IDA"],
        regulator_label=row["ENTITYA"],
        regulator_type=row["TYPEA"],
        target_id=row["IDB"],
        target_label=row["ENTITYB"],
        target_type=row["TYPEB"],
        effect=row["EFFECT"],
        mechanism=clean("MECHANISM"),
        signor_id=row["SIGNOR_ID"],
        pmid=clean("PMID"),
    )


class SignorClient:
    """Fetches and parses SIGNOR relations for an entity.

    `raw_fetch(entity) -> list[dict]` returns raw SIGNOR rows keyed by column name;
    inject a fake in tests, or `default_signor_fetch` (Task 5) for live+cache.
    """

    def __init__(self, raw_fetch: RawFetch):
        self._raw_fetch = raw_fetch

    def fetch_interactions(self, entity: str) -> list[SignorRecord]:
        try:
            rows = self._raw_fetch(entity)
            # v1: protein->protein relations only (so IDA/IDB are UniProt accessions)
            return [
                _row_to_record(row)
                for row in rows
                if row.get("TYPEA") == "protein" and row.get("TYPEB") == "protein"
            ]
        except Exception as exc:  # noqa: BLE001 - surfaced as a connector error
            raise SignorConnectorError(f"SIGNOR fetch failed for {entity}") from exc


def _record_to_node(entity_id: str, label: str) -> Node:
    return Node(
        id=entity_id,
        type=NodeType.TARGET,
        label=label,
        grounding=OntologyTermProvenance(ontology="UniProt", term_id=entity_id),
    )


def _record_to_edge(record: SignorRecord) -> Edge:
    return Edge(
        id=record.signor_id,
        source_id=record.regulator_id,
        target_id=record.target_id,
        relation=record.effect,
        pending=True,
        suggested_by=[
            KGEdgeProvenance(source="signor", reference=record.signor_id)
        ],
    )


class SignorEdgeSuggester:
    """Suggests candidate directed edges from SIGNOR (an EdgeSuggester)."""

    def __init__(self, client: SignorClient):
        self._client = client

    def check_pair(self, source: str, target: str) -> Edge | None:
        """Return the SIGNOR edge between source and target, or None.

        source and target are UniProt accessions for the live fetch (gene
        symbols only work with a custom raw_fetch).
        """
        for record in self._client.fetch_interactions(source):
            is_source = source in (record.regulator_id, record.regulator_label)
            is_target = target in (record.target_id, record.target_label)
            if is_source and is_target:
                return _record_to_edge(record)
        return None

    def expand(self, seeds: list[str], query: str | None = None) -> SuggestionResult:
        """Expand a list of seeds into SIGNOR-derived nodes and edges.

        seeds are UniProt accessions for the live fetch (gene symbols only
        work with a custom raw_fetch).
        """
        nodes: dict[str, Node] = {}
        edges: dict[str, Edge] = {}
        for seed in seeds:
            for record in self._client.fetch_interactions(seed):
                nodes.setdefault(
                    record.regulator_id,
                    _record_to_node(record.regulator_id, record.regulator_label),
                )
                nodes.setdefault(
                    record.target_id,
                    _record_to_node(record.target_id, record.target_label),
                )
                edges.setdefault(record.signor_id, _record_to_edge(record))
        return SuggestionResult(nodes=list(nodes.values()), edges=list(edges.values()))


# ---------------------------------------------------------------------------
# Live HTTP fetch
# ---------------------------------------------------------------------------

SIGNOR_GETDATA_URL = "https://signor.uniroma2.it/getData.php"
_SIGNOR_TIMEOUT_S = 30

# SIGNOR's getData.php endpoint returns a headerless TSV with 29 columns.
# Column order confirmed against live data (Task 5, 2026-06-07).
# Positions: 0=ENTITYA, 1=TYPEA, 2=IDA, 3=DB_IDA,
#            4=ENTITYB, 5=TYPEB, 6=IDB, 7=DB_IDB,
#            8=EFFECT, 9=MECHANISM, 10=RESIDUE, 11=SEQUENCE,
#            12=TAX_ID, 13=CELL_DATA, 14=TISSUE_DATA,
#            15=MODULATOR_COMPLEX, 16=TARGET_COMPLEX,
#            17=MODIFICATIONA, 18=MODIFICATIONB,
#            19=ANNOTATOR, 20=NOTES_EXTRA,
#            21=PMID, 22=DIRECT, 23=NOTES,
#            24=ANNOTATOR2, 25=SENTENCE, 26=SIGNOR_ID,
#            27=SCORE, 28=(trailing empty)
_SIGNOR_FIELDNAMES = [
    "ENTITYA", "TYPEA", "IDA", "DB_IDA",
    "ENTITYB", "TYPEB", "IDB", "DB_IDB",
    "EFFECT", "MECHANISM", "RESIDUE", "SEQUENCE",
    "TAX_ID", "CELL_DATA", "TISSUE_DATA",
    "MODULATOR_COMPLEX", "TARGET_COMPLEX",
    "MODIFICATIONA", "MODIFICATIONB",
    "ANNOTATOR", "NOTES_EXTRA",
    "PMID", "DIRECT", "NOTES",
    "ANNOTATOR2", "SENTENCE", "SIGNOR_ID",
    "SCORE", "TRAILING",
]


def default_signor_fetch(entity: str) -> list[dict]:
    """Live SIGNOR fetch (headerless TSV) -> list of column-keyed dict rows.

    Queries the SIGNOR getData endpoint for human (organism=9606) interactions
    involving the given UniProt accession. The response has no header row;
    fieldnames are injected from ``_SIGNOR_FIELDNAMES``.

    Caching is layered by the caller (wrap this callable with the project cache
    utility). Raises on transport errors; the SignorClient converts those into
    SignorConnectorError.
    """
    response = requests.get(
        SIGNOR_GETDATA_URL,
        params={"organism": "9606", "id": entity},
        timeout=_SIGNOR_TIMEOUT_S,
    )
    response.raise_for_status()
    reader = csv.DictReader(
        io.StringIO(response.text),
        fieldnames=_SIGNOR_FIELDNAMES,
        delimiter="\t",
        restval="",
    )
    return list(reader)


# ---------------------------------------------------------------------------
# License + cached fetch
# ---------------------------------------------------------------------------

# SIGNOR's DATABASE is licensed CC BY-NC 4.0 (non-commercial) — distinct from the
# CC BY journal articles. Gated for commercial builds by QURATION_ALLOW_NONCOMMERCIAL_KG
# (see quration.hypothesis.orchestrator.real_pipeline.build_real_loop).
SIGNOR_LICENSE = "CC BY-NC 4.0 (non-commercial)"

# Process-wide memo: SIGNOR data is static-ish, and Redis may be degraded, so a
# plain in-process dict is the resilient cache. Successful results (incl. empty,
# a valid "no interactions" answer) are cached; errors propagate uncached so a
# transient failure can be retried.
_SIGNOR_CACHE: dict[str, list[dict]] = {}


def cached_signor_fetch(entity: str) -> list[dict]:
    """`default_signor_fetch` with a best-effort in-process memo keyed by accession."""
    if entity in _SIGNOR_CACHE:
        return _SIGNOR_CACHE[entity]
    rows = default_signor_fetch(entity)
    _SIGNOR_CACHE[entity] = rows
    return rows
