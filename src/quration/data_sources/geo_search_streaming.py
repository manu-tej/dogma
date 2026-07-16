"""Streaming version of GEO search with progress tracking."""

import time
from collections import defaultdict
from typing import Callable, List, Optional

from quration.data_sources.geo import GEOFetcher
from quration.data_sources.geo_design_parser import ExperimentalDesignParser
from quration.data_sources.geo_query_generator import GEOQueryGenerator
from quration.data_sources.geo_survival_detector import detect_survival_data
from quration.models.geo_search import (
    Condition,
    ExperimentalDesign,
    GeoDatasetCandidate,
    GsmSample,
    QuerySpec,
)

# Import helper functions from original module
from quration.data_sources.geo_search import (
    _build_match_reasons,
    _dict_to_experimental_design,
    _extract_platforms,
    _extract_pmids,
    _extract_sample_count,
)


class ProgressCallback:
    """Simple progress callback interface for emitting events."""

    def __init__(self, emit_fn: Optional[Callable] = None):
        self.emit_fn = emit_fn or (lambda *args, **kwargs: None)

    def emit(self, step: str, status: str, message: str, **kwargs):
        """Emit a progress event."""
        self.emit_fn(
            step=step, status=status, message=message, **kwargs
        )


def search_geo_with_progress(
    spec: QuerySpec,
    progress: ProgressCallback,
    max_results: int = 50,
    fetch_samples: bool = False,
    max_samples_per_dataset: int = 50,
) -> List[GeoDatasetCandidate]:
    """
    Search GEO for datasets with real-time progress tracking.

    This is a wrapper around the original search_geo that emits progress
    events at each major step.

    Args:
        spec: QuerySpec describing the search requirements
        progress: ProgressCallback for emitting progress events
        max_results: Maximum number of results to return
        fetch_samples: Whether to fetch GSM sample records
        max_samples_per_dataset: Maximum number of GSM samples per dataset

    Returns:
        List of GeoDatasetCandidate objects
    """
    start_time = time.time()

    # Initialize components
    query_generator = GEOQueryGenerator()
    design_parser = ExperimentalDesignParser()
    geo_fetcher = GEOFetcher()

    # Step 1: Generate queries using LLM
    progress.emit(
        "query_generation",
        "running",
        "Generating optimized search queries with LLM"
    )

    queries = query_generator.generate_queries(
        disease_terms=spec.disease_terms,
        therapy_class=spec.therapy_class,
        therapy_scope=spec.therapy_scope,
        targets_or_genes=spec.targets_or_genes,
        study_keywords=spec.study_keywords,
        must_have_clinical=spec.must_have_clinical,
    )

    progress.emit(
        "query_generation",
        "complete",
        f"Generated {len(queries)} search queries",
        data={"query_count": len(queries)}
    )

    # Step 2: Search NCBI
    progress.emit(
        "ncbi_search",
        "running",
        f"Searching NCBI GEO with {len(queries)} queries",
        total=len(queries)
    )

    gse_to_queries = defaultdict(list)
    for idx, query in enumerate(queries, 1):
        # Show detailed progress if taking >10 seconds
        if time.time() - start_time > 10:
            progress.emit(
                "ncbi_search",
                "running",
                f"Processing query {idx}/{len(queries)}",
                progress=idx,
                total=len(queries)
            )

        gse_ids = geo_fetcher.search_datasets(query, limit=max_results)

        for gse_id in gse_ids:
            gse_to_queries[gse_id].append(query)

    unique_gse_ids = list(gse_to_queries.keys())

    progress.emit(
        "ncbi_search",
        "complete",
        f"Found {len(unique_gse_ids)} unique datasets",
        data={"dataset_count": len(unique_gse_ids)}
    )

    if not unique_gse_ids:
        progress.emit(
            "complete",
            "complete",
            "No datasets found matching your query"
        )
        return []

    # Step 3: Fetch metadata and parse
    progress.emit(
        "metadata_fetch",
        "running",
        f"Fetching metadata for {len(unique_gse_ids)} datasets",
        total=len(unique_gse_ids)
    )

    candidates = []
    processed_count = 0

    for gse_id in unique_gse_ids:
        try:
            processed_count += 1

            # Show detailed progress if taking >10 seconds
            if time.time() - start_time > 10:
                progress.emit(
                    "metadata_fetch",
                    "running",
                    f"Fetching dataset {processed_count}/{len(unique_gse_ids)}",
                    progress=processed_count,
                    total=len(unique_gse_ids)
                )

            # Fetch summary metadata
            summary = geo_fetcher.fetch_dataset_summary(gse_id)

            if not summary or "Accession" not in summary:
                continue

            # Extract basic fields
            gse_accession = summary.get("Accession", "")
            title = summary.get("title", "")
            summary_text = summary.get("summary", "")
            n_samples = _extract_sample_count(summary)
            platforms = _extract_platforms(summary)
            pmids = _extract_pmids(summary)
            primary_pmid = pmids[0] if pmids else None
            overall_design = summary.get("Overall Design", "")

            # Parse experimental design
            design_dict = design_parser.parse_design(overall_design)
            experimental_design = _dict_to_experimental_design(design_dict)

            # Detect survival data
            maybe_has_survival_data = detect_survival_data(
                title=title,
                summary=summary_text,
                overall_design=overall_design,
                metadata=summary,
            )

            # Build match reasons
            match_reasons = _build_match_reasons(
                spec=spec,
                title=title,
                summary=summary_text,
                overall_design=overall_design,
            )

            # Fetch GSM samples if requested
            samples = []
            samples_fetched = False
            if fetch_samples:
                try:
                    gsm_data = geo_fetcher.fetch_gse_samples(
                        gse_accession, limit=max_samples_per_dataset
                    )
                    for gsm in gsm_data:
                        sample = GsmSample(
                            gsm_id=gsm.get("gsm_id", ""),
                            title=gsm.get("title", ""),
                            sample_type=gsm.get("type"),
                            raw_metadata=gsm.get("summary"),
                        )
                        samples.append(sample)
                    samples_fetched = True
                except Exception as e:
                    print(f"Warning: Could not fetch samples for {gse_accession}: {e}")

            # Create GeoDatasetCandidate
            candidate = GeoDatasetCandidate(
                gse_id=gse_accession,
                title=title,
                summary=summary_text,
                experimental_design=experimental_design,
                n_samples=n_samples,
                platforms=platforms,
                primary_pmid=primary_pmid,
                maybe_has_survival_data=maybe_has_survival_data,
                match_reasons=match_reasons,
                raw_metadata=summary,
                matched_queries=gse_to_queries[gse_id],
                samples=samples,
                samples_fetched=samples_fetched,
            )

            candidates.append(candidate)

        except Exception as e:
            print(f"Error processing dataset {gse_id}: {e}")
            continue

    progress.emit(
        "metadata_fetch",
        "complete",
        f"Processed {len(candidates)} datasets",
        data={"processed_count": len(candidates)}
    )

    # Step 4: Filtering
    progress.emit(
        "filtering",
        "running",
        "Applying quality filters and ranking results"
    )

    # Filter by min_samples if specified
    if spec.min_samples:
        before_count = len(candidates)
        candidates = [c for c in candidates if c.n_samples and c.n_samples >= spec.min_samples]
        filtered_count = before_count - len(candidates)
        if filtered_count > 0:
            progress.emit(
                "filtering",
                "running",
                f"Filtered out {filtered_count} datasets with <{spec.min_samples} samples"
            )

    # Sort by number of matched queries (most relevant first)
    candidates.sort(key=lambda c: len(c.matched_queries), reverse=True)

    # Truncate to max_results
    final_candidates = candidates[:max_results]

    progress.emit(
        "filtering",
        "complete",
        f"Ranked and filtered to top {len(final_candidates)} results"
    )

    # Final completion
    elapsed = time.time() - start_time
    progress.emit(
        "results",
        "complete",
        f"Found {len(final_candidates)} datasets in {elapsed:.1f}s",
        data={
            "total_results": len(final_candidates),
            "elapsed_seconds": elapsed
        }
    )

    return final_candidates
