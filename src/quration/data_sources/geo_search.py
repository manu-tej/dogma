"""Main GEO search functionality matching the original spec."""

from collections import defaultdict
from typing import List

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


def search_geo(
    spec: QuerySpec,
    max_results: int = 50,
    fetch_samples: bool = False,
    max_samples_per_dataset: int = 50,
    parse_design: bool = True,
) -> List[GeoDatasetCandidate]:
    """
    Search GEO for datasets matching the QuerySpec.

    Overall flow:
    1. Call build_geo_queries_with_llm(spec) to get GEO query strings
    2. For each query string, call run_geo_query() to get GSE IDs
    3. Deduplicate GSE IDs across queries, track which queries matched which GSE
    4. Call fetch_geo_metadata() for all unique GSE IDs
    5. For each raw metadata entry:
        - Extract title, summary, n_samples, platforms, PMIDs, design text
        - Choose the first PMID (if multiple) as primary_pmid
        - Call parse_experimental_design_with_llm(design_text)
        - Call detect_maybe_has_survival_data() for the heuristic flag
        - Construct a list of 'match_reasons' explaining why this dataset was returned
    6. Return a list of GeoDatasetCandidate objects, truncated to max_results

    Args:
        spec: QuerySpec describing the search requirements
        max_results: Maximum number of results to return
        fetch_samples: Whether to fetch GSM sample records for each dataset
        max_samples_per_dataset: Maximum number of GSM samples to fetch per dataset

    Returns:
        List of GeoDatasetCandidate objects
    """
    # Initialize components
    query_generator = GEOQueryGenerator()
    design_parser = ExperimentalDesignParser() if parse_design else None
    geo_fetcher = GEOFetcher()

    # Step 1: Generate queries using LLM
    queries = query_generator.generate_queries(
        disease_terms=spec.disease_terms,
        therapy_class=spec.therapy_class,
        therapy_scope=spec.therapy_scope,
        targets_or_genes=spec.targets_or_genes,
        study_keywords=spec.study_keywords,
        must_have_clinical=spec.must_have_clinical,
    )

    # Step 2 & 3: Run queries and deduplicate
    gse_to_queries = defaultdict(list)

    for query in queries:
        gse_ids = geo_fetcher.search_datasets(query, limit=max_results)

        for gse_id in gse_ids:
            gse_to_queries[gse_id].append(query)

    unique_gse_ids = list(gse_to_queries.keys())

    if not unique_gse_ids:
        return []

    # Step 4 & 5: Fetch and process metadata
    candidates = []

    for gse_id in unique_gse_ids:
        try:
            # Fetch summary metadata
            summary = geo_fetcher.fetch_dataset_summary(gse_id)

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

            # Parse experimental design (optional — skipped to avoid the per-candidate
            # LLM call when the caller does not need the structured design).
            if design_parser is not None:
                design_dict = design_parser.parse_design(overall_design)
                experimental_design = _dict_to_experimental_design(design_dict)
            else:
                experimental_design = ExperimentalDesign(
                    conditions=None,
                    design_type=None,
                    tech=None,
                    notes=overall_design or "",
                    is_partial=True,
                )

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

    # Filter by min_samples if specified
    if spec.min_samples:
        candidates = [c for c in candidates if c.n_samples and c.n_samples >= spec.min_samples]

    # Sort by number of matched queries (most relevant first)
    candidates.sort(key=lambda c: len(c.matched_queries), reverse=True)

    # Step 6: Truncate to max_results
    return candidates[:max_results]


def _extract_sample_count(summary: dict) -> int | None:
    """Extract sample count from summary metadata."""
    # Try exact field name first
    n_samples = summary.get("n_samples")
    if n_samples:
        try:
            return int(n_samples)
        except (ValueError, TypeError):
            pass

    # NCBI GEO uses these field names (case-sensitive)
    for key in ["n_samples", "Samples", "SampleCount", "sample_count", "SAMPLE_COUNT"]:
        if key in summary:
            try:
                return int(summary[key])
            except (ValueError, TypeError):
                pass

    # Try extracting from nested structures
    if isinstance(summary.get("ExtRelations"), dict):
        ext_relations = summary.get("ExtRelations", {})
        if "Samples" in ext_relations:
            try:
                return int(ext_relations["Samples"])
            except (ValueError, TypeError):
                pass

    return None


def _extract_platforms(summary: dict) -> List[str]:
    """Extract platform IDs from summary metadata."""
    platforms = []

    # Try different possible field names
    if "GPL" in summary:
        gpl = summary["GPL"]
        if isinstance(gpl, list):
            for p in gpl:
                # Ensure GPL prefix
                if p and not str(p).startswith("GPL"):
                    platforms.append(f"GPL{p}")
                elif p:
                    platforms.append(str(p))
        elif gpl:
            # Ensure GPL prefix
            if not str(gpl).startswith("GPL"):
                platforms.append(f"GPL{gpl}")
            else:
                platforms.append(str(gpl))

    # Also check for platform field (used in some NCBI responses)
    if "Platform" in summary and not platforms:
        plat = summary["Platform"]
        if isinstance(plat, list):
            for p in plat:
                if p and not str(p).startswith("GPL"):
                    platforms.append(f"GPL{p}")
                elif p:
                    platforms.append(str(p))
        elif plat:
            if not str(plat).startswith("GPL"):
                platforms.append(f"GPL{plat}")
            else:
                platforms.append(str(plat))

    return platforms


def _extract_pmids(summary: dict) -> List[str]:
    """Extract PubMed IDs from summary metadata."""
    pmids = []

    if "PubMedIds" in summary:
        pm = summary["PubMedIds"]
        if isinstance(pm, list):
            pmids.extend(str(p) for p in pm if p)
        elif pm:
            pmids.append(str(pm))

    return pmids


def _extract_organism(summary: dict) -> str | None:
    """Extract organism name from summary metadata."""
    # Try different field names used by NCBI
    organism_fields = [
        "taxon",           # Common NCBI field
        "Organism",        # Capital O
        "organism",        # Lowercase
        "TAXON",          # All caps
        "Taxon"           # Capitalized
    ]

    for field in organism_fields:
        if field in summary:
            organism = summary[field]
            if organism:
                # Handle both string and nested dict structures
                if isinstance(organism, str):
                    return organism
                elif isinstance(organism, dict) and "ScientificName" in organism:
                    return organism["ScientificName"]
                elif isinstance(organism, dict) and "name" in organism:
                    return organism["name"]

    # Try extracting from nested ExtRelations or other structures
    if isinstance(summary.get("ExtRelations"), dict):
        ext_rel = summary.get("ExtRelations", {})
        for field in organism_fields:
            if field in ext_rel:
                organism = ext_rel[field]
                if isinstance(organism, str) and organism:
                    return organism

    return None


def _dict_to_experimental_design(design_dict: dict) -> ExperimentalDesign:
    """Convert design parser dict output to ExperimentalDesign dataclass."""
    conditions = None
    if design_dict.get("conditions"):
        conditions = [
            Condition(name=c["name"], n=c.get("n"))
            for c in design_dict["conditions"]
        ]

    return ExperimentalDesign(
        conditions=conditions,
        design_type=design_dict.get("design_type"),
        tech=design_dict.get("tech"),
        notes=design_dict.get("notes", ""),
        is_partial=design_dict.get("is_partial", True),
    )


def _build_match_reasons(
    spec: QuerySpec,
    title: str,
    summary: str,
    overall_design: str,
) -> List[str]:
    """Build a list of match reasons based on string matches."""
    reasons = []
    combined_text = f"{title} {summary} {overall_design}".lower()

    # Check disease terms
    matched_diseases = [
        term for term in spec.disease_terms if term.lower() in combined_text
    ]
    if matched_diseases:
        reasons.append(f"Matches disease terms: {', '.join(matched_diseases)}")

    # Check therapy class
    if spec.therapy_class and spec.therapy_class.lower() in combined_text:
        reasons.append(f"Mentions therapy: {spec.therapy_class}")

    # Check genes
    matched_genes = [
        gene for gene in spec.targets_or_genes if gene.lower() in combined_text
    ]
    if matched_genes:
        reasons.append(f"Mentions genes/targets: {', '.join(matched_genes)}")

    # Check keywords
    matched_keywords = [
        kw for kw in spec.study_keywords if kw.lower() in combined_text
    ]
    if matched_keywords:
        reasons.append(f"Matches keywords: {', '.join(matched_keywords)}")

    # Check for clinical/survival if required
    if spec.must_have_clinical:
        clinical_terms = ["survival", "prognosis", "clinical", "outcome"]
        matched_clinical = [
            term for term in clinical_terms if term in combined_text
        ]
        if matched_clinical:
            reasons.append(f"Contains clinical terms: {', '.join(matched_clinical)}")

    if not reasons:
        reasons.append("Matched via GEO query expansion")

    return reasons
