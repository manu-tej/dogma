"""Async streaming version of GEO search for SSE support."""

import asyncio
import time
from collections import defaultdict
from typing import AsyncGenerator, Callable, List, Optional

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
    _extract_organism,
    _extract_platforms,
    _extract_pmids,
    _extract_sample_count,
)


async def search_geo_with_progress_async(
    spec: QuerySpec,
    progress_callback: Callable,
    max_results: int = 50,
    fetch_samples: bool = False,
    max_samples_per_dataset: int = 50,
) -> AsyncGenerator[tuple[str, str, str, dict], List[GeoDatasetCandidate]]:
    """
    Search GEO for datasets with real-time async progress tracking.

    This async generator yields progress events and returns final results.

    Args:
        spec: QuerySpec describing the search requirements
        progress_callback: Async callback for emitting progress events
        max_results: Maximum number of results to return
        fetch_samples: Whether to fetch GSM sample records
        max_samples_per_dataset: Maximum number of GSM samples per dataset

    Yields:
        Progress tuples: (step, status, message, data)

    Returns:
        List of GeoDatasetCandidate objects
    """
    start_time = time.time()

    # Initialize components
    query_generator = GEOQueryGenerator()
    design_parser = ExperimentalDesignParser()
    geo_fetcher = GEOFetcher()

    # Step 1: Generate queries using LLM
    await progress_callback(
        step="query_generation",
        status="running",
        message="Generating optimized search queries with LLM",
    )

    # Run synchronous code in executor
    loop = asyncio.get_event_loop()
    queries = await loop.run_in_executor(
        None,
        lambda: query_generator.generate_queries(
            disease_terms=spec.disease_terms,
            therapy_class=spec.therapy_class,
            therapy_scope=spec.therapy_scope,
            targets_or_genes=spec.targets_or_genes,
            study_keywords=spec.study_keywords,
            must_have_clinical=spec.must_have_clinical,
        ),
    )

    await progress_callback(
        step="query_generation",
        status="complete",
        message=f"Generated {len(queries)} search queries",
        data={"query_count": len(queries), "queries": queries},
    )

    # Step 2: Search NCBI
    await progress_callback(
        step="ncbi_search",
        status="running",
        message=f"Searching NCBI GEO with {len(queries)} queries",
        total=len(queries),
    )

    gse_to_queries = defaultdict(list)
    for idx, query in enumerate(queries, 1):
        # Show detailed progress if taking >10 seconds
        if time.time() - start_time > 10:
            await progress_callback(
                step="ncbi_search",
                status="running",
                message=f"Processing query {idx}/{len(queries)}",
                progress=idx,
                total=len(queries),
            )

        gse_ids = await loop.run_in_executor(
            None, lambda q=query: geo_fetcher.search_datasets(q, limit=max_results)
        )

        for gse_id in gse_ids:
            gse_to_queries[gse_id].append(query)

    unique_gse_ids = list(gse_to_queries.keys())

    await progress_callback(
        step="ncbi_search",
        status="complete",
        message=f"Found {len(unique_gse_ids)} unique datasets",
        data={"dataset_count": len(unique_gse_ids), "sample_ids": unique_gse_ids[:15]},
    )

    if not unique_gse_ids:
        await progress_callback(
            step="complete", status="complete", message="No datasets found matching your query"
        )
        return []

    # Step 3: Fetch metadata and parse
    await progress_callback(
        step="metadata_fetch",
        status="running",
        message=f"Fetching metadata for {len(unique_gse_ids)} datasets",
        total=len(unique_gse_ids),
    )

    candidates = []
    processed_count = 0

    for gse_id in unique_gse_ids:
        try:
            processed_count += 1

            # Show detailed progress if taking >10 seconds
            if time.time() - start_time > 10:
                await progress_callback(
                    step="metadata_fetch",
                    status="running",
                    message=f"Fetching dataset {processed_count}/{len(unique_gse_ids)}",
                    progress=processed_count,
                    total=len(unique_gse_ids),
                )

            # Fetch summary metadata
            summary = await loop.run_in_executor(
                None, lambda: geo_fetcher.fetch_dataset_summary(gse_id)
            )

            if not summary or "Accession" not in summary:
                continue

            # Extract basic fields
            gse_accession = summary.get("Accession", "")
            title = summary.get("title", "")
            summary_text = summary.get("summary", "")
            n_samples = _extract_sample_count(summary)
            organism = _extract_organism(summary)
            platforms = _extract_platforms(summary)
            pmids = _extract_pmids(summary)
            primary_pmid = pmids[0] if pmids else None
            overall_design = summary.get("Overall Design", "")

            # Parse experimental design
            design_dict = await loop.run_in_executor(
                None, lambda: design_parser.parse_design(overall_design)
            )
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
                    gsm_data = await loop.run_in_executor(
                        None,
                        lambda: geo_fetcher.fetch_gse_samples(
                            gse_accession, limit=max_samples_per_dataset
                        ),
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
                organism=organism,
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

    await progress_callback(
        step="metadata_fetch",
        status="complete",
        message=f"Processed {len(candidates)} datasets",
        data={"processed_count": len(candidates)},
    )

    # Step 4: Filtering
    await progress_callback(
        step="filtering", status="running", message="Applying quality filters and ranking results"
    )

    before_filtering_count = len(candidates)
    filter_criteria = []

    # Filter by min_samples if specified
    if spec.min_samples:
        before_count = len(candidates)
        candidates = [c for c in candidates if c.n_samples and c.n_samples >= spec.min_samples]
        filtered_count = before_count - len(candidates)
        if filtered_count > 0:
            filter_criteria.append(f"Minimum {spec.min_samples} samples")
            await progress_callback(
                step="filtering",
                status="running",
                message=f"Filtered out {filtered_count} datasets with <{spec.min_samples} samples",
            )

    # Sort by number of matched queries (most relevant first)
    candidates.sort(key=lambda c: len(c.matched_queries), reverse=True)
    filter_criteria.append("Ranked by query relevance")

    # Truncate to max_results
    final_candidates = candidates[:max_results]
    if len(candidates) > max_results:
        filter_criteria.append(f"Limited to top {max_results} results")

    await progress_callback(
        step="filtering",
        status="complete",
        message=f"Ranked and filtered to top {len(final_candidates)} results",
        data={
            "before_count": before_filtering_count,
            "after_count": len(final_candidates),
            "criteria": filter_criteria
        },
    )

    # Final completion
    elapsed = time.time() - start_time
    await progress_callback(
        step="results",
        status="complete",
        message=f"Found {len(final_candidates)} datasets in {elapsed:.1f}s",
        data={"total_results": len(final_candidates), "elapsed_seconds": elapsed},
    )

    return final_candidates
