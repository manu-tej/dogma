"""Proteomics dataset search orchestration with LLM-powered query generation."""

import time
from typing import List, Optional

from quration.config import get_config
from quration.data_sources.proteomics import ProteomicsFetcher
from quration.data_sources.proteomics_parser import ProteomicsMetadataParser
from quration.models.proteomics_search import (
    ProteomicsDatasetCandidate,
    ProteomicsExperimentalDesign,
    ProteomicsQuerySpec,
    ProteomicsSearchResult,
)


class ProteomicsSearchOrchestrator:
    """Orchestrates intelligent proteomics dataset search using LLM-powered query generation."""

    def __init__(
        self,
        fetcher: Optional[ProteomicsFetcher] = None,
        parser: Optional[ProteomicsMetadataParser] = None,
    ):
        """Initialize search orchestrator.

        Args:
            fetcher: ProteomicsFetcher instance (creates one if not provided)
            parser: ProteomicsMetadataParser instance (creates one if not provided)
        """
        self.fetcher = fetcher or ProteomicsFetcher()
        self.parser = parser or ProteomicsMetadataParser()
        self.config = get_config()
        # Honor the configured provider (e.g. claude_subscription) and never crash on
        # construction when no provider is available — basic (rule-based) query
        # generation still works without an LLM.
        try:
            from quration.llm.providers import get_provider_from_config

            self.llm = get_provider_from_config()
        except Exception:
            self.llm = None

    def search(
        self,
        query_spec: ProteomicsQuerySpec,
        max_results: int = 50,
        use_llm_query_generation: bool = True,
    ) -> ProteomicsSearchResult:
        """Execute proteomics dataset search.

        Args:
            query_spec: Search specification
            max_results: Maximum number of results to return
            use_llm_query_generation: Use LLM to generate optimized queries

        Returns:
            ProteomicsSearchResult with matching datasets
        """
        start_time = time.time()

        # Generate search queries
        if use_llm_query_generation:
            queries = self._generate_smart_queries(query_spec)
        else:
            queries = self._generate_basic_queries(query_spec)

        # Execute searches
        all_accessions = set()
        for query in queries:
            try:
                accessions = self.fetcher.search_datasets(
                    query=query,
                    limit=max_results,
                    organism=query_spec.organism,
                )
                all_accessions.update(accessions)
            except Exception as e:
                print(f"Warning: Query failed: {query}. Error: {e}")
                continue

        # Fetch metadata for unique accessions
        candidates = []
        for accession in list(all_accessions)[:max_results]:
            try:
                metadata = self.fetcher.fetch_dataset_metadata(accession)
                candidate = self._create_candidate(metadata, query_spec, queries)
                candidates.append(candidate)
            except Exception as e:
                print(f"Warning: Failed to fetch metadata for {accession}: {e}")
                continue

        # Rank candidates by relevance
        ranked_candidates = self._rank_candidates(candidates, query_spec)

        search_time = time.time() - start_time

        return ProteomicsSearchResult(
            query_spec=query_spec,
            candidates=ranked_candidates[:max_results],
            total_found=len(all_accessions),
            search_time_seconds=search_time,
            queries_executed=queries,
        )

    def _generate_smart_queries(self, query_spec: ProteomicsQuerySpec) -> List[str]:
        """Generate optimized search queries using LLM.

        Args:
            query_spec: Search specification

        Returns:
            List of optimized search queries
        """
        if self.llm is None:  # no provider available -> deterministic rule-based queries
            return self._generate_basic_queries(query_spec)
        # Construct prompt for LLM
        prompt = f"""Generate optimized search queries for proteomics datasets in PRIDE Archive.

Search Requirements:
- Disease/Condition: {', '.join(query_spec.disease_terms)}
- Therapy/Drug Class: {query_spec.therapy_class or 'Not specified'}
- Target Proteins/Genes: {', '.join(query_spec.targets_or_proteins) if query_spec.targets_or_proteins else 'Not specified'}
- Study Keywords: {', '.join(query_spec.study_keywords) if query_spec.study_keywords else 'Not specified'}
- Organism: {query_spec.organism or 'Any'}
- Quantification Required: {'Yes' if query_spec.must_have_quantification else 'No'}

Generate 3-5 diverse search queries that would find relevant proteomics datasets.
Consider:
1. Disease names, synonyms, and related terms
2. Protein names, gene symbols, and pathways
3. Experimental techniques (TMT, iTRAQ, label-free, etc.)
4. Treatment/drug names
5. Tissue/cell type terms

Return only the queries, one per line, without numbering or explanation.
"""

        try:
            # Use fast model for query generation
            response = self.llm.generate(
                prompt=prompt,
                system_prompt="You are a proteomics search expert. Generate precise search queries for PRIDE Archive.",
                model="fast",
                max_tokens=500,
                temperature=0.3,
            )

            # Parse queries from response
            queries = [q.strip() for q in response.strip().split('\n') if q.strip()]

            # Fallback to basic queries if LLM fails
            if not queries:
                return self._generate_basic_queries(query_spec)

            return queries[:5]  # Limit to 5 queries

        except Exception as e:
            print(f"Warning: LLM query generation failed: {e}. Using basic queries.")
            return self._generate_basic_queries(query_spec)

    def _generate_basic_queries(self, query_spec: ProteomicsQuerySpec) -> List[str]:
        """Generate basic search queries without LLM.

        Args:
            query_spec: Search specification

        Returns:
            List of basic search queries
        """
        queries = []

        # Disease-focused query
        if query_spec.disease_terms:
            disease_query = " OR ".join(query_spec.disease_terms)
            queries.append(disease_query)

        # Protein/gene-focused query
        if query_spec.targets_or_proteins:
            protein_query = " OR ".join(query_spec.targets_or_proteins)
            queries.append(protein_query)

        # Combined disease + protein query
        if query_spec.disease_terms and query_spec.targets_or_proteins:
            combined = f"({query_spec.disease_terms[0]}) AND ({query_spec.targets_or_proteins[0]})"
            queries.append(combined)

        # Therapy-focused query
        if query_spec.therapy_class:
            queries.append(query_spec.therapy_class)

        # Keyword query
        if query_spec.study_keywords:
            keyword_query = " OR ".join(query_spec.study_keywords)
            queries.append(keyword_query)

        # Fallback to simple disease query if nothing else
        if not queries and query_spec.disease_terms:
            queries.append(query_spec.disease_terms[0])

        return queries if queries else ["proteomics"]

    def _create_candidate(
        self,
        metadata: dict,
        query_spec: ProteomicsQuerySpec,
        queries: List[str],
    ) -> ProteomicsDatasetCandidate:
        """Create ProteomicsDatasetCandidate from metadata.

        Args:
            metadata: Parsed PRIDE metadata
            query_spec: Original query specification
            queries: Executed queries

        Returns:
            ProteomicsDatasetCandidate object
        """
        # Extract basic info
        accession = metadata.get("accession", "")
        title = metadata.get("title", "")
        description = metadata.get("description", "")

        # Extract organisms
        organisms = metadata.get("organisms", [])
        organism = None
        if organisms:
            org = organisms[0]
            if isinstance(org, dict):
                organism = org.get("name", "")
            else:
                organism = str(org)

        # Extract instruments
        instruments_data = metadata.get("instruments", [])
        instruments = []
        for inst in instruments_data:
            if isinstance(inst, dict):
                instruments.append(inst.get("name", ""))
            else:
                instruments.append(str(inst))

        # Extract experiment types
        exp_types_data = metadata.get("experiment_types", [])
        experiment_types = []
        for et in exp_types_data:
            if isinstance(et, dict):
                experiment_types.append(et.get("name", ""))
            else:
                experiment_types.append(str(et))

        # Extract quantification methods
        quant_data = metadata.get("quantification_methods", [])
        quant_methods = []
        for qm in quant_data:
            if isinstance(qm, dict):
                quant_methods.append(qm.get("name", ""))
            else:
                quant_methods.append(str(qm))

        # Extract sample characteristics
        tissues_data = metadata.get("tissues", [])
        tissues = [t.get("name", "") if isinstance(t, dict) else str(t) for t in tissues_data]

        diseases_data = metadata.get("diseases", [])
        diseases = [d.get("name", "") if isinstance(d, dict) else str(d) for d in diseases_data]

        cell_types_data = metadata.get("cell_types", [])
        cell_types = [c.get("name", "") if isinstance(c, dict) else str(c) for c in cell_types_data]

        # Extract publication info
        references = metadata.get("references", [])
        primary_doi = metadata.get("doi", None)
        primary_pmid = None
        if references and len(references) > 0:
            primary_pmid = references[0].get("pubmed_id", None)

        # Data availability (simplified - would need file analysis for full details)
        num_assays = metadata.get("num_assays", 0)
        has_protein_data = num_assays > 0
        has_peptide_data = num_assays > 0
        has_quantification_data = len(quant_methods) > 0

        # Generate match reasons
        match_reasons = self._generate_match_reasons(
            metadata, query_spec, title, description
        )

        # Create experimental design
        experimental_design = ProteomicsExperimentalDesign(
            conditions=None,  # Would need detailed analysis
            design_type=None,  # Could infer from metadata
            instrument=instruments[0] if instruments else None,
            quantification_method=quant_methods[0] if quant_methods else None,
            acquisition_strategy=None,  # Would need to parse from experiment types
            notes=description[:200] if description else "",
            is_partial=True,
        )

        return ProteomicsDatasetCandidate(
            accession=accession,
            title=title,
            description=description,
            experimental_design=experimental_design,
            n_assays=num_assays,
            organism=organism,
            instruments=instruments,
            experiment_types=experiment_types,
            quantification_methods=quant_methods,
            tissues=tissues,
            diseases=diseases,
            cell_types=cell_types,
            primary_doi=primary_doi,
            primary_pmid=primary_pmid,
            has_protein_data=has_protein_data,
            has_peptide_data=has_peptide_data,
            has_quantification_data=has_quantification_data,
            match_reasons=match_reasons,
            matched_queries=queries,
            raw_metadata=metadata,
        )

    def _generate_match_reasons(
        self,
        metadata: dict,
        query_spec: ProteomicsQuerySpec,
        title: str,
        description: str,
    ) -> List[str]:
        """Generate reasons why this dataset matches the query.

        Args:
            metadata: Dataset metadata
            query_spec: Query specification
            title: Dataset title
            description: Dataset description

        Returns:
            List of match reasons
        """
        reasons = []
        text_to_search = f"{title} {description}".lower()

        # Check disease matches
        for disease in query_spec.disease_terms:
            if disease.lower() in text_to_search:
                reasons.append(f"Disease term '{disease}' found in dataset")

        # Check protein/gene matches
        for protein in query_spec.targets_or_proteins:
            if protein.lower() in text_to_search:
                reasons.append(f"Protein/gene '{protein}' mentioned")

        # Check therapy matches
        if query_spec.therapy_class and query_spec.therapy_class.lower() in text_to_search:
            reasons.append(f"Therapy '{query_spec.therapy_class}' mentioned")

        # Check quantification requirement
        if query_spec.must_have_quantification:
            quant_methods = metadata.get("quantification_methods", [])
            if quant_methods:
                reasons.append("Has quantification data")

        # Check organism match
        if query_spec.organism:
            organisms = metadata.get("organisms", [])
            for org in organisms:
                org_name = org.get("name", "") if isinstance(org, dict) else str(org)
                if query_spec.organism.lower() in org_name.lower():
                    reasons.append(f"Organism matches ({query_spec.organism})")

        return reasons if reasons else ["General relevance to query"]

    def _rank_candidates(
        self,
        candidates: List[ProteomicsDatasetCandidate],
        query_spec: ProteomicsQuerySpec,
    ) -> List[ProteomicsDatasetCandidate]:
        """Rank candidates by relevance to query.

        Args:
            candidates: List of dataset candidates
            query_spec: Query specification

        Returns:
            Ranked list of candidates
        """
        def score_candidate(candidate: ProteomicsDatasetCandidate) -> float:
            score = 0.0

            # Match reasons count
            score += len(candidate.match_reasons) * 10

            # Has quantification data (if required)
            if query_spec.must_have_quantification and candidate.has_quantification_data:
                score += 20

            # Organism match
            if query_spec.organism and candidate.organism:
                if query_spec.organism.lower() in candidate.organism.lower():
                    score += 15

            # Number of assays (more is better, up to a point)
            if candidate.n_assays:
                score += min(candidate.n_assays, 50) * 0.5

            # Has publication
            if candidate.primary_doi or candidate.primary_pmid:
                score += 10

            # Has disease annotation
            if candidate.diseases:
                score += 10

            # Has tissue annotation
            if candidate.tissues:
                score += 5

            return score

        # Sort by score (descending)
        return sorted(candidates, key=score_candidate, reverse=True)


def search_proteomics(
    spec: ProteomicsQuerySpec,
    max_results: int = 50,
    use_llm: bool = True,
) -> ProteomicsSearchResult:
    """Convenience function to search proteomics datasets.

    Args:
        spec: Query specification
        max_results: Maximum number of results
        use_llm: Use LLM for query generation

    Returns:
        ProteomicsSearchResult
    """
    orchestrator = ProteomicsSearchOrchestrator()
    return orchestrator.search(spec, max_results=max_results, use_llm_query_generation=use_llm)
