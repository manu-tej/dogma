"""Data sources for fetching metadata."""

from quration.data_sources.base import DataConnector, DataSourceType, ExportFormat
from quration.data_sources.factory import (
    get_data_connector,
    list_available_connectors,
    register_connector,
)
from quration.data_sources.geo import GEOFetcher
from quration.data_sources.geo_connector import GEOConnector
from quration.data_sources.geo_design_parser import (
    ExperimentalDesignParser,
    parse_experimental_design_with_llm,
)
from quration.data_sources.geo_matrix import GEOMatrixDownloader
from quration.data_sources.geo_query_generator import (
    GEOQueryGenerator,
    build_geo_queries_with_llm,
)
from quration.data_sources.geo_search import search_geo
from quration.data_sources.geo_survival_detector import (
    detect_maybe_has_survival_data,
    detect_survival_data,
    extract_survival_keywords,
)
from quration.data_sources.ontologies import OntologyMapper
from quration.data_sources.proteomics import ProteomicsFetcher
from quration.data_sources.proteomics_parser import ProteomicsMetadataParser
from quration.data_sources.proteomics_search import (
    ProteomicsSearchOrchestrator,
    search_proteomics,
)

__all__ = [
    # Base classes and types
    "DataConnector",
    "DataSourceType",
    "ExportFormat",
    # Factory functions
    "get_data_connector",
    "list_available_connectors",
    "register_connector",
    # GEO connectors
    "GEOFetcher",  # Legacy
    "GEOConnector",  # New unified interface
    "GEOMatrixDownloader",
    # Other components
    "OntologyMapper",
    "GEOQueryGenerator",
    "ExperimentalDesignParser",
    "detect_survival_data",
    "detect_maybe_has_survival_data",
    "extract_survival_keywords",
    "search_geo",
    "build_geo_queries_with_llm",
    "parse_experimental_design_with_llm",
    "ProteomicsFetcher",
    "ProteomicsMetadataParser",
    "ProteomicsSearchOrchestrator",
    "search_proteomics",
]
