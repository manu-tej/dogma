"""Grounding backed by the locally-cached OptimusKG node tables.

Type-agnostic: a node is probed against the gene / disease / drug tables in an
order seeded by its NodeType, but the gene table is always a fallback — so a
protein mistyped as a compound still resolves to its UniProt id. Best-effort:
any miss returns found=False rather than fabricating an id.
"""

from __future__ import annotations

import logging

import polars as pl

from quration.hypothesis.graph import Node, NodeType
from quration.hypothesis.orchestrator.edge_chat import SetGrounding
from quration.hypothesis.orchestrator.grounding import GroundingProposal

logger = logging.getLogger(__name__)

_GENE = "nodes/gene.parquet"
_DISEASE = "nodes/disease.parquet"
_DRUG = "nodes/drug.parquet"

# Probe order per node type; gene is always present as a universal fallback.
_PROBE_ORDER: dict[NodeType, list[str]] = {
    NodeType.TARGET: [_GENE],
    NodeType.DISEASE: [_DISEASE, _GENE],
    NodeType.PHENOTYPE: [_DISEASE, _GENE],
    NodeType.COMPOUND: [_DRUG, _GENE],
    # Pathways have no node table here; don't gene-fallback (that pins a pathway
    # to a single protein). Miss -> a chained ontology backend grounds it to GO.
    NodeType.PATHWAY: [],
}
_DEFAULT_ORDER = [_GENE, _DISEASE, _DRUG]


# Label normalization is shared (polars-free) with the OLS-ontology backend.
from quration.hypothesis.orchestrator.labels import candidate_labels, clean_label  # noqa: E402,F401


def _default_loader(path: str) -> pl.DataFrame:
    import optimuskg

    return optimuskg.load_parquet(path)


class OptimusKGGroundingService:
    """Grounds nodes against OptimusKG's gene/disease/drug node tables."""

    def __init__(self, loader=None):
        self._loader = loader or _default_loader
        self._cache: dict[str, pl.DataFrame] = {}

    def _table(self, path: str) -> pl.DataFrame:
        if path not in self._cache:
            self._cache[path] = self._loader(path)
        return self._cache[path]

    def ground(self, node: Node) -> GroundingProposal:
        candidates = candidate_labels(node.label, node.type)
        if not candidates:
            return GroundingProposal(found=False, summary="Node has no label to ground.")

        order = _PROBE_ORDER.get(node.type, _DEFAULT_ORDER)
        # Candidate-major: give the most specific label its full probe order before
        # falling back to rescued/leading-symbol candidates. First hit wins.
        for cand in candidates:
            for path in order:
                edit = self._probe(path, cand, node.id)
                if edit is not None:
                    return GroundingProposal(
                        found=True,
                        summary=f"Matched '{node.label}' to {edit.ontology}:{edit.term_id} via OptimusKG.",
                        proposed_edit=edit,
                    )
        return GroundingProposal(
            found=False,
            summary=f"No OptimusKG match for '{node.label}'.",
        )

    def _probe(self, path: str, name: str, node_id: str) -> SetGrounding | None:
        # Best-effort end to end: a missing table, a schema mismatch, or a null in
        # `properties` must skip the probe, never raise (grounding never 500s).
        try:
            table = self._table(path)
            row = _match_row(table, name, path)
            if row is None:
                return None
            return _to_edit(path, row, node_id)
        except Exception as exc:
            logger.warning("OptimusKG probe %s failed: %s", path, exc)
            return None


def _synonym_strings(table: pl.DataFrame, field: str):
    """A polars expr yielding a node's lowercased synonyms for ``field``, or None
    if the field is absent or carries no string-bearing elements.

    Handles both shapes the tables use: a plain ``list[str]`` and the real
    ``list[struct{label, source}]`` (where the synonym text is the ``label``).
    """
    props_dtype = table.schema.get("properties")
    if not isinstance(props_dtype, pl.Struct):
        return None
    field_dtype = next((f.dtype for f in props_dtype.fields if f.name == field), None)
    if not isinstance(field_dtype, pl.List):
        return None
    inner = field_dtype.inner
    col = pl.col("properties").struct.field(field)
    if isinstance(inner, pl.Struct):
        return col.list.eval(pl.element().struct.field("label").str.to_lowercase())
    if inner in (pl.String, pl.Utf8):
        return col.list.eval(pl.element().str.to_lowercase())
    return None  # e.g. List(Null) for an always-empty column — nothing to match


def _match_row(table: pl.DataFrame, name: str, path: str) -> dict | None:
    props = pl.col("properties").struct
    primary = "symbol" if path == _GENE else "name"
    syn_fields = (
        ["symbol_synonyms", "synonyms"] if path == _GENE else ["synonyms"]
    )
    lname = name.lower()

    hit = table.filter(props.field(primary).str.to_lowercase() == lname)
    if hit.height == 0:
        for syn in syn_fields:
            syn_expr = _synonym_strings(table, syn)
            if syn_expr is None:
                continue
            hit = table.filter(syn_expr.list.contains(lname))
            if hit.height:
                break
    return hit.row(0, named=True) if hit.height else None


def _to_edit(path: str, row: dict, node_id: str) -> SetGrounding | None:
    props = row["properties"]
    if path == _GENE:
        swissprot = next(
            (a["id"] for a in (props.get("associated_proteins") or [])
             if a.get("source") == "uniprot_swissprot"),
            None,
        )
        if not swissprot:
            return None  # no canonical protein id -> don't fabricate one
        return SetGrounding(node_id=node_id, ontology="UniProt", term_id=swissprot,
                            label=props.get("name"))
    if path == _DRUG:
        return SetGrounding(node_id=node_id, ontology="ChEMBL", term_id=row["id"],
                            label=props.get("name"))
    # disease: id like "EFO_0020001" / "DOID_10113" -> ontology / term_id
    ontology, sep, term = row["id"].partition("_")
    if not sep or not ontology or not term:
        logger.warning("OptimusKG disease id has unexpected format: %s", row["id"])
        return None  # don't emit a grounding with an empty/garbage ontology
    return SetGrounding(node_id=node_id, ontology=ontology, term_id=term,
                        label=props.get("name"))
