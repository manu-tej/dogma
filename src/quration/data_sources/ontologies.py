"""Ontology mapping and lookup services."""

import time
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from quration.config import OntologyConfig, get_config
from quration.models.metadata import OntologyTerm


class OntologyMapper:
    """Maps terms to standard ontologies using OLS (Ontology Lookup Service)."""

    def __init__(self, config: OntologyConfig | None = None):
        """Initialize ontology mapper.

        Args:
            config: Ontology configuration, uses global config if not provided
        """
        if config is None:
            config = get_config().data_sources.ontologies

        self.config = config
        self.ols_base_url = config.ols_base_url
        self.ontologies = config.ontologies
        self.bioportal_api_key = config.bioportal_api_key

        # Rate limiting
        self._last_request_time = 0.0
        self._min_interval = 0.2  # 5 requests per second

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    def _make_request(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make rate-limited request to OLS API.

        Args:
            url: Request URL
            params: Query parameters

        Returns:
            JSON response
        """
        self._rate_limit()

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        return response.json()

    def search_term(
        self,
        query: str,
        ontologies: list[str] | None = None,
        exact: bool = False,
        limit: int = 5,
    ) -> list[OntologyTerm]:
        """Search for ontology terms matching query.

        Args:
            query: Search query
            ontologies: List of ontology IDs to search (defaults to configured ontologies)
            exact: Whether to require exact match
            limit: Maximum number of results

        Returns:
            List of matching ontology terms
        """
        if ontologies is None:
            ontologies = self.ontologies

        url = f"{self.ols_base_url}/search"
        params = {
            "q": query,
            "ontology": ",".join(ontologies),
            "exact": str(exact).lower(),
            "rows": limit,
            "format": "json",
        }

        try:
            response = self._make_request(url, params)

            terms = []
            if "response" in response and "docs" in response["response"]:
                for doc in response["response"]["docs"]:
                    term = OntologyTerm(
                        term=doc.get("label", query),
                        ontology_id=doc.get("short_form") or doc.get("obo_id"),
                        ontology_name=doc.get("ontology_name"),
                        iri=doc.get("iri"),
                        confidence=1.0 if exact else 0.8,  # Higher confidence for exact matches
                    )
                    terms.append(term)

            return terms

        except Exception:
            # Return empty list on failure rather than crashing
            return []

    def map_tissue(self, tissue_text: str) -> OntologyTerm | None:
        """Map tissue description to UBERON ontology.

        Args:
            tissue_text: Tissue description

        Returns:
            OntologyTerm if found, None otherwise
        """
        # Try exact match first
        results = self.search_term(tissue_text, ontologies=["uberon"], exact=True, limit=1)

        if results:
            return results[0]

        # Try fuzzy match
        results = self.search_term(tissue_text, ontologies=["uberon"], exact=False, limit=1)

        if results:
            results[0].confidence = 0.7  # Lower confidence for fuzzy match
            return results[0]

        return None

    def map_disease(self, disease_text: str) -> OntologyTerm | None:
        """Map disease description to MONDO or DOID ontology.

        Args:
            disease_text: Disease description

        Returns:
            OntologyTerm if found, None otherwise
        """
        # Prefer MONDO for disease terms
        results = self.search_term(disease_text, ontologies=["mondo", "doid"], exact=True, limit=1)

        if results:
            return results[0]

        # Try fuzzy match
        results = self.search_term(disease_text, ontologies=["mondo", "doid"], exact=False, limit=1)

        if results:
            results[0].confidence = 0.7
            return results[0]

        return None

    def map_cell_type(self, cell_type_text: str) -> OntologyTerm | None:
        """Map cell type description to CL (Cell Ontology).

        Args:
            cell_type_text: Cell type description

        Returns:
            OntologyTerm if found, None otherwise
        """
        results = self.search_term(cell_type_text, ontologies=["cl"], exact=True, limit=1)

        if results:
            return results[0]

        results = self.search_term(cell_type_text, ontologies=["cl"], exact=False, limit=1)

        if results:
            results[0].confidence = 0.7
            return results[0]

        return None

    def map_organism(self, organism_text: str) -> OntologyTerm | None:
        """Map organism to NCBITaxon.

        Args:
            organism_text: Organism name

        Returns:
            OntologyTerm if found, None otherwise
        """
        # NCBITaxon is typically available in OLS
        results = self.search_term(organism_text, ontologies=["ncbitaxon"], exact=True, limit=1)

        if results:
            return results[0]

        results = self.search_term(organism_text, ontologies=["ncbitaxon"], exact=False, limit=1)

        if results:
            results[0].confidence = 0.8
            return results[0]

        return None

    def map_development_stage(self, stage_text: str) -> OntologyTerm | None:
        """Map developmental stage to appropriate ontology.

        Args:
            stage_text: Development stage description

        Returns:
            OntologyTerm if found, None otherwise
        """
        # Use EFO which includes development stages
        results = self.search_term(stage_text, ontologies=["efo", "uberon"], exact=True, limit=1)

        if results:
            return results[0]

        results = self.search_term(stage_text, ontologies=["efo", "uberon"], exact=False, limit=1)

        if results:
            results[0].confidence = 0.7
            return results[0]

        return None

    def map_experimental_factor(self, factor_text: str) -> OntologyTerm | None:
        """Map experimental factor to EFO (Experimental Factor Ontology).

        Args:
            factor_text: Experimental factor description

        Returns:
            OntologyTerm if found, None otherwise
        """
        results = self.search_term(factor_text, ontologies=["efo"], exact=True, limit=1)

        if results:
            return results[0]

        results = self.search_term(factor_text, ontologies=["efo"], exact=False, limit=1)

        if results:
            results[0].confidence = 0.7
            return results[0]

        return None

    def batch_map_terms(
        self, terms: dict[str, str], field_types: dict[str, str] | None = None
    ) -> dict[str, OntologyTerm | None]:
        """Map multiple terms to ontologies in batch.

        Args:
            terms: Dictionary of {field_name: term_text}
            field_types: Optional mapping of {field_name: type} to guide ontology selection
                        Types: 'tissue', 'disease', 'cell_type', 'organism', 'development_stage'

        Returns:
            Dictionary of {field_name: OntologyTerm or None}
        """
        results = {}

        for field_name, term_text in terms.items():
            if not term_text:
                results[field_name] = None
                continue

            # Determine field type
            field_type = None
            if field_types and field_name in field_types:
                field_type = field_types[field_name]
            else:
                # Infer from field name
                field_name_lower = field_name.lower()
                if "tissue" in field_name_lower or "organ" in field_name_lower:
                    field_type = "tissue"
                elif "disease" in field_name_lower or "condition" in field_name_lower:
                    field_type = "disease"
                elif "cell" in field_name_lower:
                    field_type = "cell_type"
                elif "organism" in field_name_lower or "species" in field_name_lower:
                    field_type = "organism"
                elif "stage" in field_name_lower or "development" in field_name_lower:
                    field_type = "development_stage"

            # Map based on type
            if field_type == "tissue":
                results[field_name] = self.map_tissue(term_text)
            elif field_type == "disease":
                results[field_name] = self.map_disease(term_text)
            elif field_type == "cell_type":
                results[field_name] = self.map_cell_type(term_text)
            elif field_type == "organism":
                results[field_name] = self.map_organism(term_text)
            elif field_type == "development_stage":
                results[field_name] = self.map_development_stage(term_text)
            else:
                # Generic search across all ontologies
                terms_list = self.search_term(term_text, limit=1)
                results[field_name] = terms_list[0] if terms_list else None

        return results
