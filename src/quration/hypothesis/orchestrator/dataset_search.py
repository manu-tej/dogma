"""Per-edge dataset discovery (GEO) producing attach-ready candidates.

An edge is the unit you test. "Find datasets" maps the edge's endpoints into a
GEO (transcriptomics) search, unifies the hits into ``DatasetCandidate``s with a
suggested nf-core pipeline, and ranks them. Picking one attaches it to
``edge.proposed_test`` via the existing ``SetTest`` edit.

GEO only: edge execution currently grounds against the methods graph (real
pipeline execution lands in slice 2) and PRIDE proteomics datasets are not yet
attachable, so surfacing PRIDE hits would only ever be un-attachable noise (PRIDE
re-enable is a later task). The real service wraps the existing ``search_geo``
pipeline (injectable for tests); the demo service returns canned candidates offline.
"""

from __future__ import annotations

import functools
import logging
from typing import Literal, Protocol

from pydantic import BaseModel

from quration.hypothesis.graph import CausalGraph, Edge, NodeType
from quration.models.geo_search import GeoDatasetCandidate, QuerySpec

logger = logging.getLogger(__name__)


class DatasetCandidate(BaseModel):
    source: Literal["geo", "pride"]
    accession: str
    title: str
    summary: str = ""
    n_samples: int | None = None
    organism: str | None = None
    assay: str | None = None
    primary_pmid: str | None = None
    match_reasons: list[str] = []
    suggested_pipeline: str | None = None


class DatasetSearchService(Protocol):
    def find(self, graph: CausalGraph, edge_id: str) -> list[DatasetCandidate]: ...
    def find_multi(self, graph: CausalGraph, edge_id: str) -> list[DatasetCandidate]: ...


def suggest_pipeline(source: str, assay: str | None) -> str:
    """Map a dataset's source/assay to the nf-core pipeline that tests a causal claim."""
    if source == "pride":
        return "nf-core/proteomicslfq"
    # GEO: a quantitative causal-claim test wants differential abundance, not bare
    # alignment. Defer to the registry only for clearly non-RNA strategies.
    if assay:
        try:
            from quration.analysis.pipeline_registry import (
                PipelineRegistry,
                normalize_library_strategy,
            )

            match = PipelineRegistry.get_pipeline_for_strategy(normalize_library_strategy(assay))
            if match and match.name and "rnaseq" not in match.name:
                return match.name
        except Exception:  # registry shape drift shouldn't break discovery
            pass
    return "nf-core/differentialabundance"


def _endpoint_nodes(graph: CausalGraph, edge: Edge):
    return [n for n in (graph.get_node(edge.source_id), graph.get_node(edge.target_id)) if n]


def _query_spec_from_edge(graph: CausalGraph, edge: Edge) -> QuerySpec:
    nodes = _endpoint_nodes(graph, edge)
    genes = [n.label for n in nodes if n.type == NodeType.TARGET]
    diseases = [n.label for n in nodes if n.type in (NodeType.DISEASE, NodeType.PHENOTYPE)]
    other = [n.label for n in nodes if n.type not in
             (NodeType.TARGET, NodeType.DISEASE, NodeType.PHENOTYPE)]
    return QuerySpec(
        disease_terms=diseases,
        therapy_class=None,
        therapy_scope="broad",
        targets_or_genes=genes,
        study_keywords=[graph.query, *other],
        must_have_clinical=False,
    )


def _from_geo(c: GeoDatasetCandidate) -> DatasetCandidate:
    assay = c.experimental_design.tech if c.experimental_design else None
    if not assay and c.platforms:
        assay = c.platforms[0]
    return DatasetCandidate(
        source="geo", accession=c.gse_id, title=c.title, summary=c.summary or "",
        n_samples=c.n_samples, organism=c.organism, assay=assay, primary_pmid=c.primary_pmid,
        match_reasons=list(c.match_reasons), suggested_pipeline=suggest_pipeline("geo", assay),
    )


def _rank_key(c: DatasetCandidate):
    return (len(c.match_reasons), c.n_samples or 0)


def _pride_candidates(graph: CausalGraph, edge: Edge) -> list[DatasetCandidate]:
    """Build PRIDE DatasetCandidates for an edge.  Best-effort: caller catches all exceptions."""
    from quration.data_sources.proteomics_search import search_proteomics
    from quration.models.proteomics_search import ProteomicsQuerySpec

    nodes = _endpoint_nodes(graph, edge)
    genes = [n.label for n in nodes if n.type == NodeType.TARGET]
    diseases = [n.label for n in nodes if n.type in (NodeType.DISEASE, NodeType.PHENOTYPE)]
    other = [n.label for n in nodes if n.type not in
             (NodeType.TARGET, NodeType.DISEASE, NodeType.PHENOTYPE)]
    spec = ProteomicsQuerySpec(
        disease_terms=diseases,
        therapy_class=None,
        therapy_scope="broad",
        targets_or_proteins=genes,
        study_keywords=[graph.query, *other],
        must_have_quantification=False,
        organism="Homo sapiens",
    )
    result = search_proteomics(spec, max_results=8)
    pride = []
    for c in result.candidates:
        assay = c.experiment_types[0] if c.experiment_types else "proteomics"
        pride.append(DatasetCandidate(
            source="pride",
            accession=c.accession,
            title=c.title,
            summary=c.description,
            n_samples=c.n_assays,
            organism=c.organism,
            assay=assay,
            primary_pmid=c.primary_pmid,
            match_reasons=list(c.match_reasons),
            suggested_pipeline=suggest_pipeline("pride", assay),
        ))
    return pride


class RealDatasetSearchService:
    """Searches GEO via the existing pipeline; best-effort (failure yields no hits)."""

    def __init__(self, geo_search_fn=None, proteomics_search_fn=None, max_results: int = 8):
        if geo_search_fn is None:
            from quration.data_sources.geo_search import search_geo

            geo_search_fn = functools.partial(search_geo, parse_design=False)
        self._geo = geo_search_fn
        self._proteomics = proteomics_search_fn
        self._max = max_results

    def find(self, graph: CausalGraph, edge_id: str) -> list[DatasetCandidate]:
        # GEO only: edge execution currently grounds against the methods graph
        # (real pipeline execution / GSE matrices is pending, slice 2) and PRIDE
        # proteomics datasets are not yet attachable, so surfacing PRIDE hits here
        # would only ever be un-attachable noise (PRIDE re-enable is a later task).
        edge = graph.get_edge(edge_id)
        if edge is None:
            return []
        geo: list[DatasetCandidate] = []
        try:
            hits = self._geo(_query_spec_from_edge(graph, edge), max_results=self._max)
            geo = [_from_geo(c) for c in hits]
        except Exception as exc:
            logger.warning("GEO search failed for edge %s: %s", edge_id, exc)
        geo.sort(key=_rank_key, reverse=True)
        return geo[: self._max]

    def find_multi(self, graph: CausalGraph, edge_id: str) -> list[DatasetCandidate]:
        """GEO + best-effort PRIDE for the resolver path.

        The existing ``find`` (GEO-only) is unchanged so ``/find-data`` is unaffected.
        PRIDE failures are caught and logged; GEO-only results are returned in that case.
        """
        geo = self.find(graph, edge_id)
        edge = graph.get_edge(edge_id)
        if edge is None:
            return geo
        pride: list[DatasetCandidate] = []
        try:
            if self._proteomics is not None:
                # Injected fn (tests / custom callers) — mirrors geo_search_fn injection.
                from quration.models.proteomics_search import ProteomicsQuerySpec

                nodes = _endpoint_nodes(graph, edge)
                genes = [n.label for n in nodes if n.type == NodeType.TARGET]
                diseases = [n.label for n in nodes if n.type in (NodeType.DISEASE, NodeType.PHENOTYPE)]
                other = [n.label for n in nodes if n.type not in
                         (NodeType.TARGET, NodeType.DISEASE, NodeType.PHENOTYPE)]
                spec = ProteomicsQuerySpec(
                    disease_terms=diseases,
                    therapy_class=None,
                    therapy_scope="broad",
                    targets_or_proteins=genes,
                    study_keywords=[graph.query, *other],
                    must_have_quantification=False,
                    organism="Homo sapiens",
                )
                result = self._proteomics(spec, max_results=self._max)
                for c in result.candidates:
                    assay = c.experiment_types[0] if c.experiment_types else "proteomics"
                    pride.append(DatasetCandidate(
                        source="pride",
                        accession=c.accession,
                        title=c.title,
                        summary=c.description,
                        n_samples=c.n_assays,
                        organism=c.organism,
                        assay=assay,
                        primary_pmid=c.primary_pmid,
                        match_reasons=list(c.match_reasons),
                        suggested_pipeline=suggest_pipeline("pride", assay),
                    ))
            else:
                pride = _pride_candidates(graph, edge)
        except Exception as exc:
            logger.warning("PRIDE search failed for edge %s: %s", edge_id, exc)
        return geo + pride


class DemoDatasetSearchService:
    """Deterministic synthetic candidate for an explicitly offline demo seam."""

    def find(self, graph: CausalGraph, edge_id: str) -> list[DatasetCandidate]:
        return [
            DatasetCandidate(
                source="geo", accession="GSE-DEMO",
                title="Synthetic offline dataset candidate (not a GEO result)",
                summary="Placeholder used only to demonstrate the review workflow.",
                n_samples=None, organism=None, assay="RNA-Seq", primary_pmid=None,
                match_reasons=["synthetic demo; not returned by a live GEO search"],
                suggested_pipeline="nf-core/differentialabundance",
            ),
        ]

    def find_multi(self, graph: CausalGraph, edge_id: str) -> list[DatasetCandidate]:
        """Delegates to find(); demo mode adds no PRIDE candidates (offline seam)."""
        return self.find(graph, edge_id)
