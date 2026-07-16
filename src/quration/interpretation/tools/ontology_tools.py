"""
Ontology mapping tools for LLM interpretation.

These tools wrap the existing OntologyMapper to provide LLM-callable interfaces
for mapping biological terms to standard ontologies (EFO, UBERON, MONDO, CL, etc.).
"""

import logging
from typing import Any, Literal

from quration.data_sources.ontologies import OntologyMapper
from quration.interpretation.tools.base import (
    BioinformaticsTool,
    ToolDefinition,
    ToolError,
)

logger = logging.getLogger(__name__)


# Ontology type mapping for validation and routing
ONTOLOGY_TYPE_MAP = {
    "tissue": ["uberon"],
    "disease": ["mondo", "doid"],
    "cell_type": ["cl"],
    "organism": ["ncbitaxon"],
    "experimental_factor": ["efo"],
    "development_stage": ["efo", "uberon"],
    "general": ["efo", "uberon", "cl", "doid", "mondo"],
}


class MapTermToOntologyTool(BioinformaticsTool):
    """Tool for mapping a term to standard ontology."""

    def __init__(self, mapper: OntologyMapper | None = None):
        """Initialize the tool.

        Args:
            mapper: OntologyMapper instance, creates one if not provided
        """
        self._mapper = mapper or OntologyMapper()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="map_term_to_ontology",
            description=(
                "Map a biological term to a standard ontology. Use this to get "
                "standardized identifiers for tissues, diseases, cell types, organisms, "
                "or experimental factors. Returns ontology ID, label, and IRI."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "term": {
                        "type": "string",
                        "description": "The biological term to map (e.g., 'lung', 'breast cancer', 'T cell')",
                    },
                    "ontology_type": {
                        "type": "string",
                        "description": "Type of ontology to search",
                        "enum": [
                            "tissue",
                            "disease",
                            "cell_type",
                            "organism",
                            "experimental_factor",
                            "development_stage",
                            "general",
                        ],
                        "default": "general",
                    },
                },
                "required": ["term"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "found": {"type": "boolean"},
                    "term": {"type": "string"},
                    "ontology_id": {"type": "string"},
                    "ontology_name": {"type": "string"},
                    "iri": {"type": "string"},
                    "confidence": {"type": "number"},
                },
            },
            category="ontology",
            rate_limit=5,
            cacheable=True,
            cache_ttl_seconds=86400,  # 24 hours - ontologies don't change often
            examples=[
                {
                    "input": {"term": "lung adenocarcinoma", "ontology_type": "disease"},
                    "output": {
                        "found": True,
                        "term": "lung adenocarcinoma",
                        "ontology_id": "MONDO:0005061",
                        "ontology_name": "mondo",
                        "iri": "http://purl.obolibrary.org/obo/MONDO_0005061",
                        "confidence": 1.0,
                    },
                }
            ],
        )

    async def execute(
        self,
        term: str,
        ontology_type: str = "general",
    ) -> dict[str, Any]:
        """Map a term to an ontology.

        Args:
            term: The term to map
            ontology_type: Type of ontology to search

        Returns:
            dict with mapping results
        """
        try:
            # Route to appropriate mapper method based on type
            result = None

            if ontology_type == "tissue":
                result = self._mapper.map_tissue(term)
            elif ontology_type == "disease":
                result = self._mapper.map_disease(term)
            elif ontology_type == "cell_type":
                result = self._mapper.map_cell_type(term)
            elif ontology_type == "organism":
                result = self._mapper.map_organism(term)
            elif ontology_type == "experimental_factor":
                result = self._mapper.map_experimental_factor(term)
            elif ontology_type == "development_stage":
                result = self._mapper.map_development_stage(term)
            else:
                # General search across all ontologies
                results = self._mapper.search_term(term, limit=1)
                result = results[0] if results else None

            if result:
                return {
                    "found": True,
                    "term": result.term,
                    "ontology_id": result.ontology_id,
                    "ontology_name": result.ontology_name,
                    "iri": result.iri,
                    "confidence": result.confidence,
                }
            else:
                return {
                    "found": False,
                    "term": term,
                    "ontology_id": None,
                    "ontology_name": None,
                    "iri": None,
                    "confidence": 0.0,
                    "message": f"No ontology mapping found for '{term}'",
                }

        except Exception as e:
            raise ToolError(f"Ontology mapping failed for '{term}': {e}") from e


class SearchOntologyTool(BioinformaticsTool):
    """Tool for searching ontology terms."""

    def __init__(self, mapper: OntologyMapper | None = None):
        """Initialize the tool.

        Args:
            mapper: OntologyMapper instance, creates one if not provided
        """
        self._mapper = mapper or OntologyMapper()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_ontology",
            description=(
                "Search for ontology terms matching a query. Returns multiple matches "
                "with their IDs and confidence scores. Use this when you need to find "
                "multiple possible mappings or explore related terms."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for ontology terms",
                    },
                    "ontology": {
                        "type": "string",
                        "description": (
                            "Specific ontology to search (e.g., 'efo', 'uberon', 'mondo', "
                            "'cl', 'doid', 'ncbitaxon'). Leave empty to search all."
                        ),
                        "default": None,
                    },
                    "exact_match": {
                        "type": "boolean",
                        "description": "Require exact match only",
                        "default": False,
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": ["query"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "term": {"type": "string"},
                                "ontology_id": {"type": "string"},
                                "ontology_name": {"type": "string"},
                                "iri": {"type": "string"},
                                "confidence": {"type": "number"},
                            },
                        },
                    },
                    "total_found": {"type": "integer"},
                },
            },
            category="ontology",
            rate_limit=5,
            cacheable=True,
            cache_ttl_seconds=86400,
        )

    async def execute(
        self,
        query: str,
        ontology: str | None = None,
        exact_match: bool = False,
        max_results: int = 5,
    ) -> dict[str, Any]:
        """Search for ontology terms.

        Args:
            query: Search query
            ontology: Specific ontology to search
            exact_match: Require exact matches only
            max_results: Maximum results to return

        Returns:
            dict with search results
        """
        try:
            ontologies = [ontology] if ontology else None

            results = self._mapper.search_term(
                query=query,
                ontologies=ontologies,
                exact=exact_match,
                limit=max_results,
            )

            return {
                "results": [
                    {
                        "term": r.term,
                        "ontology_id": r.ontology_id,
                        "ontology_name": r.ontology_name,
                        "iri": r.iri,
                        "confidence": r.confidence,
                    }
                    for r in results
                ],
                "total_found": len(results),
            }

        except Exception as e:
            raise ToolError(f"Ontology search failed for '{query}': {e}") from e


class GetOntologyTermDetailsTool(BioinformaticsTool):
    """Tool for getting details about a specific ontology term."""

    def __init__(self, mapper: OntologyMapper | None = None):
        """Initialize the tool.

        Args:
            mapper: OntologyMapper instance, creates one if not provided
        """
        self._mapper = mapper or OntologyMapper()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="get_ontology_term_details",
            description=(
                "Get detailed information about a specific ontology term by its ID. "
                "Returns the term label, definition, synonyms, and related terms. "
                "Use this to understand what an ontology term means."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "term_id": {
                        "type": "string",
                        "description": (
                            "Ontology term ID (e.g., 'UBERON:0002048', 'MONDO:0005061', "
                            "'CL:0000084')"
                        ),
                    },
                },
                "required": ["term_id"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "found": {"type": "boolean"},
                    "term_id": {"type": "string"},
                    "label": {"type": "string"},
                    "definition": {"type": "string"},
                    "synonyms": {"type": "array", "items": {"type": "string"}},
                    "ontology": {"type": "string"},
                    "iri": {"type": "string"},
                },
            },
            category="ontology",
            rate_limit=5,
            cacheable=True,
            cache_ttl_seconds=86400,
        )

    async def execute(self, term_id: str) -> dict[str, Any]:
        """Get details for an ontology term.

        Args:
            term_id: Ontology term ID

        Returns:
            dict with term details
        """
        try:
            import requests

            # Parse ontology from term ID (e.g., UBERON:0002048 -> uberon)
            if ":" in term_id:
                ontology = term_id.split(":")[0].lower()
            else:
                ontology = None

            # Convert term ID to OLS format
            # UBERON:0002048 -> UBERON_0002048
            term_iri_fragment = term_id.replace(":", "_")

            # Try to fetch from OLS
            url = f"{self._mapper.ols_base_url}/ontologies/{ontology}/terms"
            params = {"short_form": term_iri_fragment}

            self._mapper._rate_limit()
            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()
                terms = data.get("_embedded", {}).get("terms", [])

                if terms:
                    term_data = terms[0]
                    return {
                        "found": True,
                        "term_id": term_id,
                        "label": term_data.get("label", ""),
                        "definition": term_data.get("description", [""])[0]
                        if term_data.get("description")
                        else "",
                        "synonyms": term_data.get("synonyms", []),
                        "ontology": term_data.get("ontology_name", ontology),
                        "iri": term_data.get("iri", ""),
                    }

            # Term not found
            return {
                "found": False,
                "term_id": term_id,
                "label": None,
                "definition": None,
                "synonyms": [],
                "ontology": ontology,
                "iri": None,
                "message": f"Term '{term_id}' not found in ontology",
            }

        except Exception as e:
            raise ToolError(f"Failed to get details for '{term_id}': {e}") from e


class BatchMapOntologyTermsTool(BioinformaticsTool):
    """Tool for batch mapping multiple terms to ontologies."""

    def __init__(self, mapper: OntologyMapper | None = None):
        """Initialize the tool.

        Args:
            mapper: OntologyMapper instance, creates one if not provided
        """
        self._mapper = mapper or OntologyMapper()

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="batch_map_ontology_terms",
            description=(
                "Map multiple biological terms to ontologies in a single call. "
                "Useful when you have multiple terms from different categories "
                "(tissues, diseases, cell types) that need standardization."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "terms": {
                        "type": "object",
                        "description": (
                            "Dictionary of {field_name: term_text} pairs. "
                            "Example: {'tissue': 'lung', 'disease': 'cancer', 'cell_type': 'T cell'}"
                        ),
                        "additionalProperties": {"type": "string"},
                    },
                    "field_types": {
                        "type": "object",
                        "description": (
                            "Optional mapping of {field_name: type} to guide ontology selection. "
                            "Types: 'tissue', 'disease', 'cell_type', 'organism', 'development_stage'"
                        ),
                        "additionalProperties": {"type": "string"},
                        "default": None,
                    },
                },
                "required": ["terms"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "mappings": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "found": {"type": "boolean"},
                                "ontology_id": {"type": "string"},
                                "ontology_name": {"type": "string"},
                            },
                        },
                    },
                    "success_count": {"type": "integer"},
                    "total_count": {"type": "integer"},
                },
            },
            category="ontology",
            rate_limit=2,  # Lower rate limit for batch operations
            cacheable=True,
            cache_ttl_seconds=86400,
        )

    async def execute(
        self,
        terms: dict[str, str],
        field_types: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Batch map terms to ontologies.

        Args:
            terms: Dictionary of field_name -> term_text
            field_types: Optional dictionary of field_name -> type hint

        Returns:
            dict with mapping results
        """
        try:
            results = self._mapper.batch_map_terms(terms, field_types)

            mappings = {}
            success_count = 0

            for field_name, result in results.items():
                if result:
                    mappings[field_name] = {
                        "found": True,
                        "input_term": terms[field_name],
                        "term": result.term,
                        "ontology_id": result.ontology_id,
                        "ontology_name": result.ontology_name,
                        "iri": result.iri,
                        "confidence": result.confidence,
                    }
                    success_count += 1
                else:
                    mappings[field_name] = {
                        "found": False,
                        "input_term": terms[field_name],
                        "term": None,
                        "ontology_id": None,
                        "ontology_name": None,
                        "iri": None,
                        "confidence": 0.0,
                    }

            return {
                "mappings": mappings,
                "success_count": success_count,
                "total_count": len(terms),
            }

        except Exception as e:
            raise ToolError(f"Batch ontology mapping failed: {e}") from e


# Factory function to create all ontology tools
def create_ontology_tools(
    mapper: OntologyMapper | None = None,
) -> list[BioinformaticsTool]:
    """Create all ontology tools with a shared mapper.

    Args:
        mapper: Optional OntologyMapper instance to share

    Returns:
        list of BioinformaticsTool instances
    """
    if mapper is None:
        mapper = OntologyMapper()

    return [
        MapTermToOntologyTool(mapper),
        SearchOntologyTool(mapper),
        GetOntologyTermDetailsTool(mapper),
        BatchMapOntologyTermsTool(mapper),
    ]
