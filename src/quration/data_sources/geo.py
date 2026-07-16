"""GEO (Gene Expression Omnibus) data fetcher."""

import time
import xml.etree.ElementTree as ET
from typing import Any, Literal
from urllib.parse import urlencode

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from quration.config import GEOConfig, get_config


class GEOFetcher:
    """Fetches metadata from NCBI GEO using E-utilities."""

    def __init__(self, config: GEOConfig | None = None):
        """Initialize GEO fetcher.

        Args:
            config: GEO configuration, uses global config if not provided
        """
        if config is None:
            config = get_config().data_sources.geo

        self.config = config
        self.base_url = config.base_url
        self.tool = config.tool
        self.email = config.email
        self.api_key = config.api_key
        # Use effective rate limit (10 req/sec with API key, 3 without)
        self.rate_limit = config.get_effective_rate_limit()

        # Rate limiting
        self._last_request_time = 0.0
        self._min_interval = 1.0 / self.rate_limit

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _make_request(self, endpoint: str, params: dict[str, Any]) -> requests.Response:
        """Make rate-limited request to E-utilities.

        Args:
            endpoint: E-utilities endpoint (e.g., 'esearch.fcgi')
            params: Query parameters

        Returns:
            Response object
        """
        self._rate_limit()

        # Add required NCBI identification parameters
        params["tool"] = self.tool  # Required by NCBI to identify the application
        if self.email:
            params["email"] = self.email  # Strongly recommended to avoid 403 errors
        if self.api_key:
            params["api_key"] = self.api_key

        url = f"{self.base_url}/{endpoint}"
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        return response

    def search_datasets(
        self,
        query: str,
        limit: int = 10,
        experiment_type: str | None = None,
        entry_types: list[str] | None = None,
    ) -> list[str]:
        """Search for GEO datasets matching query.

        Args:
            query: Search query (natural language or structured)
            limit: Maximum number of results
            experiment_type: Filter by experiment type (e.g., "Expression profiling by high throughput sequencing")
            entry_types: Filter by entry types (e.g., ["gse", "gds"]). Defaults to ["gse"] only.

        Returns:
            List of GEO dataset IDs
        """
        # Default to GSE (Series) only
        if entry_types is None:
            entry_types = ["gse"]

        # Build query - let NCBI's search parser handle natural language queries
        # Don't wrap entire query in [All Fields] as it makes it too restrictive
        search_query = query

        # Add experiment type filter if provided
        if experiment_type:
            search_query += f' AND "{experiment_type}"[DataSet Type]'

        # Add entry type filter using proper [ETYP] field tag
        if entry_types:
            etyp_query = " OR ".join(f'{et}[ETYP]' for et in entry_types)
            search_query += f' AND ({etyp_query})'

        params = {
            "db": "gds",  # GEO DataSets database
            "term": search_query,
            "retmax": limit,
            "retmode": "xml",
            "usehistory": "y",
        }

        response = self._make_request("esearch.fcgi", params)

        # Parse XML response
        root = ET.fromstring(response.content)
        id_list = root.find("IdList")

        if id_list is None:
            return []

        geo_ids = [id_elem.text for id_elem in id_list.findall("Id") if id_elem.text]

        return geo_ids

    def fetch_dataset_summary(self, dataset_id: str) -> dict[str, Any]:
        """Fetch summary information for a GEO dataset.

        Args:
            dataset_id: GEO dataset ID (numeric ID from search)

        Returns:
            Dictionary containing dataset summary
        """
        params = {
            "db": "gds",
            "id": dataset_id,
            "retmode": "xml",
            "version": "2.0",  # Use version 2.0 per NCBI documentation
        }

        response = self._make_request("esummary.fcgi", params)

        # Parse XML response
        root = ET.fromstring(response.content)
        doc_sum = root.find(".//DocumentSummary")

        if doc_sum is None:
            return {}

        summary = {}

        # Extract key fields
        for elem in doc_sum:
            tag = elem.tag
            if elem.text:
                summary[tag] = elem.text
            elif len(elem) > 0:
                # Handle nested elements
                summary[tag] = {child.tag: child.text for child in elem if child.text}

        return summary

    def fetch_dataset_full(self, gse_accession: str) -> dict[str, Any]:
        """Fetch full metadata for a GEO dataset using SOFT format.

        Args:
            gse_accession: GEO series accession (e.g., 'GSE123456')

        Returns:
            Dictionary containing parsed dataset metadata
        """
        # Fetch SOFT format data
        url = f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi"
        params = {
            "acc": gse_accession,
            "targ": "self",
            "form": "text",
            "view": "full",
        }

        self._rate_limit()
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()

        # Parse SOFT format
        metadata = self._parse_soft(response.text)

        return metadata

    def _parse_soft(self, soft_text: str) -> dict[str, Any]:
        """Parse SOFT format text into structured metadata.

        Args:
            soft_text: SOFT format text

        Returns:
            Parsed metadata dictionary
        """
        metadata: dict[str, Any] = {
            "series": {},
            "samples": [],
            "platforms": [],
        }

        current_section = None
        current_item: dict[str, Any] = {}

        for line in soft_text.split("\n"):
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            # Section markers
            if line.startswith("^SERIES"):
                if current_item and current_section == "series":
                    metadata["series"] = current_item
                current_section = "series"
                current_item = {}

            elif line.startswith("^SAMPLE"):
                if current_item and current_section == "sample":
                    metadata["samples"].append(current_item)
                current_section = "sample"
                current_item = {}

            elif line.startswith("^PLATFORM"):
                if current_item and current_section == "platform":
                    metadata["platforms"].append(current_item)
                current_section = "platform"
                current_item = {}

            # Data lines
            elif " = " in line:
                key, value = line.split(" = ", 1)
                key = key.lstrip("!").strip()
                value = value.strip()

                # Handle multiple values for same key
                if key in current_item:
                    if isinstance(current_item[key], list):
                        current_item[key].append(value)
                    else:
                        current_item[key] = [current_item[key], value]
                else:
                    current_item[key] = value

        # Add final item
        if current_item:
            if current_section == "series":
                metadata["series"] = current_item
            elif current_section == "sample":
                metadata["samples"].append(current_item)
            elif current_section == "platform":
                metadata["platforms"].append(current_item)

        return metadata

    def extract_sample_characteristics(self, sample_metadata: dict[str, Any]) -> dict[str, str]:
        """Extract sample characteristics from SOFT metadata.

        Args:
            sample_metadata: Sample metadata from SOFT parsing

        Returns:
            Dictionary of characteristics
        """
        characteristics = {}

        # Look for characteristic fields
        for key, value in sample_metadata.items():
            if key.startswith("Sample_characteristics"):
                # Parse "key: value" format
                if isinstance(value, list):
                    for item in value:
                        if ": " in item:
                            char_key, char_value = item.split(": ", 1)
                            characteristics[char_key.strip()] = char_value.strip()
                elif isinstance(value, str) and ": " in value:
                    char_key, char_value = value.split(": ", 1)
                    characteristics[char_key.strip()] = char_value.strip()

        # Also extract other relevant fields
        for field in ["Sample_organism", "Sample_source_name", "Sample_title"]:
            clean_field = field.replace("Sample_", "")
            if field in sample_metadata:
                value = sample_metadata[field]
                if isinstance(value, list):
                    value = value[0] if value else ""
                characteristics[clean_field] = value

        return characteristics

    def fetch_datasets_from_query(
        self, query: str, limit: int = 10, include_full_metadata: bool = True
    ) -> list[dict[str, Any]]:
        """End-to-end: Search and fetch full metadata for datasets.

        Args:
            query: Search query
            limit: Maximum number of datasets
            include_full_metadata: Whether to fetch full SOFT metadata (slower)

        Returns:
            List of dataset metadata dictionaries
        """
        # Search for datasets
        dataset_ids = self.search_datasets(query, limit=limit)

        if not dataset_ids:
            return []

        datasets = []

        for dataset_id in dataset_ids:
            # Get summary to extract GSE accession
            summary = self.fetch_dataset_summary(dataset_id)

            if "Accession" in summary:
                gse_accession = summary["Accession"]

                dataset_info = {"id": dataset_id, "accession": gse_accession, "summary": summary}

                # Fetch full metadata if requested
                if include_full_metadata:
                    try:
                        full_metadata = self.fetch_dataset_full(gse_accession)
                        dataset_info["full_metadata"] = full_metadata

                        # SOFT format often doesn't include samples, fetch them separately
                        if not full_metadata.get("samples"):
                            gsm_samples = self.fetch_gse_samples(gse_accession, limit=100)
                            # Convert GSM summaries to SOFT-like format
                            converted_samples = []
                            for gsm in gsm_samples:
                                sample_data = {
                                    "Sample_geo_accession": gsm.get("gsm_id", ""),
                                    "Sample_title": gsm.get("title", ""),
                                    "Sample_type": gsm.get("type", ""),
                                    **gsm.get("summary", {})
                                }
                                converted_samples.append(sample_data)
                            full_metadata["samples"] = converted_samples
                    except Exception as e:
                        # Continue even if full fetch fails
                        dataset_info["fetch_error"] = str(e)

                datasets.append(dataset_info)

        return datasets

    def fetch_gse_samples(self, gse_accession: str, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch GSM (sample) records for a given GSE accession.

        Args:
            gse_accession: GSE accession (e.g., 'GSE12345')
            limit: Maximum number of samples to retrieve

        Returns:
            List of sample metadata dictionaries
        """
        # Search for GSM samples linked to this GSE
        search_query = f'{gse_accession}[Accession] AND gsm[ETYP]'

        params = {
            "db": "gds",
            "term": search_query,
            "retmax": limit,
            "retmode": "xml",
            "usehistory": "y",
        }

        try:
            response = self._make_request("esearch.fcgi", params)
            root = ET.fromstring(response.content)
            id_list = root.find("IdList")

            if id_list is None:
                return []

            gsm_ids = [id_elem.text for id_elem in id_list.findall("Id") if id_elem.text]

            if not gsm_ids:
                return []

            # Fetch summaries for all GSM samples
            samples = []
            for gsm_id in gsm_ids:
                summary = self.fetch_dataset_summary(gsm_id)
                if summary:
                    # Extract sample characteristics if available
                    sample_data = {
                        "gsm_id": summary.get("Accession", gsm_id),
                        "title": summary.get("title", ""),
                        "type": summary.get("type", ""),
                        "summary": summary,
                    }
                    samples.append(sample_data)

            return samples

        except Exception as e:
            print(f"Error fetching GSM samples for {gse_accession}: {e}")
            return []

    def smart_search(
        self,
        disease_terms: list[str],
        therapy_class: str | None = None,
        therapy_scope: Literal["specific", "broad"] = "specific",
        targets_or_genes: list[str] | None = None,
        study_keywords: list[str] | None = None,
        must_have_clinical: bool = False,
        max_results: int = 50,
        include_survival_detection: bool = True,
        include_design_parsing: bool = False,
    ) -> list[dict[str, Any]]:
        """Perform LLM-assisted smart search for GEO datasets.

        This method uses LLM to generate optimized queries and optionally
        detects survival data and parses experimental designs.

        Args:
            disease_terms: List of disease terms (e.g., ["lung cancer", "NSCLC"])
            therapy_class: Therapy class (e.g., "EGFR-TKI")
            therapy_scope: "specific" or "broad" (expand therapy to specific drugs)
            targets_or_genes: Target genes or proteins
            study_keywords: Additional keywords
            must_have_clinical: Emphasize clinical/survival data
            max_results: Maximum number of results
            include_survival_detection: Detect potential survival data
            include_design_parsing: Parse experimental designs with LLM

        Returns:
            List of dataset dictionaries with enriched metadata
        """
        # Import here to avoid circular dependency
        from quration.data_sources.geo_query_generator import GEOQueryGenerator

        # Generate queries using LLM
        query_generator = GEOQueryGenerator()
        queries = query_generator.generate_queries(
            disease_terms=disease_terms,
            therapy_class=therapy_class,
            therapy_scope=therapy_scope,
            targets_or_genes=targets_or_genes or [],
            study_keywords=study_keywords or [],
            must_have_clinical=must_have_clinical,
        )

        # Search using each query and deduplicate
        seen_ids = set()
        dataset_id_to_queries = {}

        for query in queries:
            dataset_ids = self.search_datasets(query, limit=max_results)

            for dataset_id in dataset_ids:
                if dataset_id not in seen_ids:
                    seen_ids.add(dataset_id)
                    dataset_id_to_queries[dataset_id] = [query]
                else:
                    dataset_id_to_queries[dataset_id].append(query)

        # Fetch metadata for all unique datasets
        datasets = []

        for dataset_id in seen_ids:
            try:
                summary = self.fetch_dataset_summary(dataset_id)

                if "Accession" in summary:
                    gse_accession = summary["Accession"]
                    dataset_info = {
                        "id": dataset_id,
                        "accession": gse_accession,
                        "summary": summary,
                        "matched_queries": dataset_id_to_queries[dataset_id],
                    }

                    # Add survival detection if requested
                    if include_survival_detection:
                        has_survival = detect_survival_data(
                            title=summary.get("title"),
                            summary=summary.get("summary"),
                            overall_design=summary.get("Overall Design"),
                            metadata=summary,
                        )
                        dataset_info["maybe_has_survival_data"] = has_survival

                        if has_survival:
                            dataset_info["survival_keywords"] = extract_survival_keywords(
                                title=summary.get("title"),
                                summary=summary.get("summary"),
                                overall_design=summary.get("Overall Design"),
                            )

                    # Add design parsing if requested
                    if include_design_parsing:
                        from quration.data_sources.geo_design_parser import (
                            ExperimentalDesignParser,
                        )

                        parser = ExperimentalDesignParser()
                        design_text = summary.get("Overall Design", "")
                        dataset_info["parsed_design"] = parser.parse_design(design_text)

                    datasets.append(dataset_info)

            except Exception as e:
                print(f"Error fetching dataset {dataset_id}: {e}")
                continue

        # Sort by number of matched queries (most relevant first)
        datasets.sort(key=lambda d: len(d.get("matched_queries", [])), reverse=True)

        return datasets[:max_results]
