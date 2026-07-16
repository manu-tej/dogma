"""Proteomics data fetcher for PRIDE Archive, ProteomeXchange, and related databases."""

import time
from typing import Any, Literal
from datetime import datetime
from urllib.parse import urlencode

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from quration.config import ProteomicsConfig, get_config


class ProteomicsFetcher:
    """Fetches proteomics metadata from PRIDE Archive and ProteomeXchange databases.

    Supports multiple proteomics repositories:
    - PRIDE Archive (primary)
    - ProteomeXchange Central
    - MassIVE (UCSD)
    - jPOST (Japan)
    - PeptideAtlas

    Provides standardized access to proteomics datasets with:
    - Dataset search and filtering
    - Metadata extraction (species, tissue, disease, treatment)
    - Experimental details (instrument, quantification method)
    - File listing and data access
    """

    def __init__(self, config: ProteomicsConfig | None = None):
        """Initialize proteomics fetcher.

        Args:
            config: Proteomics configuration, uses global config if not provided
        """
        if config is None:
            config = get_config().data_sources.proteomics

        self.config = config
        self.pride_base_url = config.pride_base_url
        self.px_base_url = config.px_base_url
        self.massive_base_url = config.massive_base_url
        self.jpost_base_url = config.jpost_base_url
        self.peptide_atlas_base_url = config.peptide_atlas_base_url
        self.tool = config.tool
        self.email = config.email
        self.api_key = config.pride_api_key
        self.rate_limit = config.rate_limit

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
    def _make_request(
        self, url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None
    ) -> requests.Response:
        """Make rate-limited request with retry logic.

        Args:
            url: Full URL to request
            params: Query parameters
            headers: Request headers

        Returns:
            Response object
        """
        self._rate_limit()

        # Add API key to headers if available
        if headers is None:
            headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        return response

    def search_datasets(
        self,
        query: str,
        limit: int = 10,
        organism: str | None = None,
        disease: str | None = None,
        tissue: str | None = None,
        instrument: str | None = None,
        experiment_type: str | None = None,
        publication_date_from: str | None = None,
        publication_date_to: str | None = None,
    ) -> list[str]:
        """Search for proteomics datasets in PRIDE Archive.

        Args:
            query: Search query (natural language or keywords)
            limit: Maximum number of results (default: 10, max: 100)
            organism: Filter by organism (e.g., "Homo sapiens", "Mus musculus")
            disease: Filter by disease term (e.g., "cancer", "diabetes")
            tissue: Filter by tissue type (e.g., "liver", "brain", "blood")
            instrument: Filter by mass spectrometry instrument (e.g., "Orbitrap", "Q Exactive")
            experiment_type: Filter by experiment type (e.g., "TMT", "label-free")
            publication_date_from: Filter by publication date from (YYYY-MM-DD)
            publication_date_to: Filter by publication date to (YYYY-MM-DD)

        Returns:
            List of PRIDE/ProteomeXchange accession IDs (e.g., ['PXD012345', 'PXD067890'])
        """
        # PRIDE Archive search endpoint
        url = f"{self.pride_base_url}/search/projects"

        # Build query parameters
        params: dict[str, Any] = {
            "query": query,
            "pageSize": min(limit, 100),  # PRIDE API max is typically 100
            "page": 0,
            "sortDirection": "DESC",
            "sortFields": "submission_date",  # Sort by most recent
        }

        # Add filters
        if organism:
            params["species"] = organism
        if disease:
            params["disease"] = disease
        if tissue:
            params["tissue"] = tissue
        if instrument:
            params["instrument"] = instrument
        if experiment_type:
            params["experimentType"] = experiment_type
        if publication_date_from:
            params["publicationDateFrom"] = publication_date_from
        if publication_date_to:
            params["publicationDateTo"] = publication_date_to

        response = self._make_request(url, params)
        data = response.json()

        # The PRIDE v2 search endpoint returns a top-level list of projects; older
        # HAL-style responses nested them under _embedded.projects. Handle both.
        if isinstance(data, list):
            projects = data
        else:
            projects = data.get("_embedded", {}).get("projects", [])

        accessions = []
        for project in projects:
            accession = project.get("accession")
            if accession:
                accessions.append(accession)

        return accessions

    def fetch_dataset_metadata(self, accession: str) -> dict[str, Any]:
        """Fetch full metadata for a proteomics dataset.

        Args:
            accession: PRIDE/ProteomeXchange accession (e.g., 'PXD012345')

        Returns:
            Dictionary containing comprehensive dataset metadata including:
            - Basic info: title, description, accession
            - Sample characteristics: species, tissue, disease, cell type
            - Experimental details: instrument, quantification method, protocol
            - Publication info: DOI, authors, journal
            - Data availability: file types, sizes, download links
        """
        # PRIDE Archive project endpoint
        url = f"{self.pride_base_url}/projects/{accession}"
        response = self._make_request(url)
        data = response.json()

        # Parse and structure the metadata
        metadata = self._parse_pride_metadata(data)

        return metadata

    def _parse_pride_metadata(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Parse raw PRIDE API response into structured metadata.

        Args:
            raw_data: Raw JSON response from PRIDE API

        Returns:
            Structured metadata dictionary
        """
        # Extract basic information
        accession = raw_data.get("accession", "")
        title = raw_data.get("title", "")
        description = raw_data.get("projectDescription", "")

        # Sample metadata
        organisms = raw_data.get("organisms", [])
        organism_parts = raw_data.get("organismParts", [])  # Tissues
        diseases = raw_data.get("diseases", [])
        cell_types = raw_data.get("cellTypes", [])

        # Experimental details
        instruments = raw_data.get("instruments", [])
        experiment_types = raw_data.get("experimentTypes", [])
        ptms = raw_data.get("ptmNames", [])  # Post-translational modifications
        quantification_methods = raw_data.get("quantificationMethods", [])

        # Sample processing
        sample_processing_protocol = raw_data.get("sampleProcessingProtocol", "")
        data_processing_protocol = raw_data.get("dataProcessingProtocol", "")

        # Publication information
        publication_date = raw_data.get("publicationDate", "")
        submission_date = raw_data.get("submissionDate", "")
        references = raw_data.get("references", [])

        # Submitter information
        submitters = raw_data.get("submitters", [])
        lab_head = raw_data.get("labHead", {})

        # Data files
        num_assays = raw_data.get("numAssays", 0)

        # Keywords and identifiers
        keywords = raw_data.get("keywords", [])
        doi = raw_data.get("doi", "")

        # Ontology terms (CV params)
        sample_attributes = raw_data.get("sampleAttributes", [])

        # Construct structured metadata
        metadata = {
            "accession": accession,
            "title": title,
            "description": description,
            "source_database": "PRIDE",

            # Sample characteristics
            "organisms": [self._parse_cv_param(org) for org in organisms] if organisms else [],
            "tissues": [self._parse_cv_param(tissue) for tissue in organism_parts] if organism_parts else [],
            "diseases": [self._parse_cv_param(disease) for disease in diseases] if diseases else [],
            "cell_types": [self._parse_cv_param(ct) for ct in cell_types] if cell_types else [],

            # Experimental protocol
            "instruments": [self._parse_cv_param(inst) for inst in instruments] if instruments else [],
            "experiment_types": [self._parse_cv_param(et) for et in experiment_types] if experiment_types else [],
            "quantification_methods": [
                self._parse_cv_param(qm) for qm in quantification_methods
            ] if quantification_methods else [],
            "ptms": [self._parse_cv_param(ptm) for ptm in ptms] if ptms else [],

            # Protocols
            "sample_processing_protocol": sample_processing_protocol,
            "data_processing_protocol": data_processing_protocol,

            # Publication
            "publication_date": publication_date,
            "submission_date": submission_date,
            "references": self._parse_references(references),
            "doi": doi,

            # Submitters
            "submitters": submitters,
            "lab_head": lab_head,

            # Data summary
            "num_assays": num_assays,
            "keywords": keywords,
            "sample_attributes": [self._parse_cv_param(attr) for attr in sample_attributes],

            # Raw data for reference
            "_raw": raw_data,
        }

        return metadata

    def _parse_cv_param(self, cv_param: dict[str, Any] | str) -> dict[str, Any]:
        """Parse controlled vocabulary parameter.

        PRIDE uses CV params with ontology terms. This extracts:
        - name: Human-readable term
        - accession: Ontology accession (e.g., "NCBITAXON:9606")
        - cv_label: Ontology name (e.g., "NCBITAXON", "EFO", "UBERON")
        - value: Associated value if present

        Args:
            cv_param: CV parameter object or string

        Returns:
            Structured CV parameter dict
        """
        if isinstance(cv_param, str):
            return {"name": cv_param, "accession": None, "cv_label": None, "value": None}

        return {
            "name": cv_param.get("name", ""),
            "accession": cv_param.get("accession", ""),
            "cv_label": cv_param.get("cvLabel", ""),
            "value": cv_param.get("value", ""),
        }

    def _parse_references(self, references: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Parse publication references.

        Args:
            references: List of reference objects from PRIDE

        Returns:
            List of parsed reference dicts
        """
        parsed_refs = []
        for ref in references:
            parsed_refs.append({
                "pubmed_id": str(ref.get("pubmedId", "")),
                "doi": ref.get("doi", ""),
                "reference_line": ref.get("referenceLine", ""),
            })
        return parsed_refs

    def fetch_dataset_files(self, accession: str) -> list[dict[str, Any]]:
        """Fetch file listing for a proteomics dataset.

        Args:
            accession: PRIDE/ProteomeXchange accession

        Returns:
            List of file metadata dictionaries with:
            - fileName: Name of the file
            - fileSize: Size in bytes
            - fileType: Type (RAW, RESULT, SEARCH, etc.)
            - fileCategory: Category (raw data, result files, etc.)
            - downloadLink: FTP download URL
        """
        url = f"{self.pride_base_url}/files/byProject"
        params = {"accession": accession}

        response = self._make_request(url, params)
        data = response.json()

        # Extract file list
        files = data.get("list", [])

        # Parse file information
        parsed_files = []
        for file_info in files:
            parsed_files.append({
                "file_name": file_info.get("fileName", ""),
                "file_size": file_info.get("fileSize", 0),
                "file_type": file_info.get("fileType", ""),
                "file_category": file_info.get("fileCategory", ""),
                "download_link": file_info.get("publicFileLocations", [{}])[0].get("value", ""),
                "file_extension": file_info.get("fileExtension", ""),
            })

        return parsed_files

    def fetch_protein_identifications(self, accession: str) -> dict[str, Any]:
        """Fetch protein identification summary for a dataset.

        Args:
            accession: PRIDE/ProteomeXchange accession

        Returns:
            Dictionary containing protein identification statistics
        """
        url = f"{self.pride_base_url}/projects/{accession}/proteins"

        try:
            response = self._make_request(url)
            data = response.json()
            return data
        except requests.exceptions.HTTPError as e:
            # Protein data may not be available for all datasets
            if e.response.status_code == 404:
                return {"proteins": [], "total_proteins": 0, "note": "Protein data not available"}
            raise

    def search_by_therapeutic_area(
        self,
        therapeutic_area: str,
        limit: int = 50,
        organism: str = "Homo sapiens",
    ) -> list[str]:
        """Search for proteomics datasets relevant to a therapeutic area.

        This is a specialized search function that constructs queries
        optimized for finding datasets related to therapeutic research.

        Args:
            therapeutic_area: Therapeutic area (e.g., "oncology", "neurology", "immunology")
            limit: Maximum number of results
            organism: Target organism (default: "Homo sapiens")

        Returns:
            List of PRIDE accession IDs
        """
        # Construct therapeutic area query
        # This could be enhanced with LLM-based query generation
        query_terms = [therapeutic_area]

        # Add common related terms
        therapeutic_keywords = {
            "oncology": ["cancer", "tumor", "carcinoma", "malignancy", "neoplasm"],
            "neurology": ["brain", "neurological", "neurodegenerative", "alzheimer", "parkinson"],
            "immunology": ["immune", "autoimmune", "inflammation", "T cell", "B cell"],
            "cardiology": ["heart", "cardiac", "cardiovascular", "myocardial"],
            "diabetes": ["diabetes", "insulin", "glucose", "metabolic syndrome"],
        }

        area_lower = therapeutic_area.lower()
        for key, keywords in therapeutic_keywords.items():
            if key in area_lower:
                query_terms.extend(keywords)
                break

        # Construct query
        query = " OR ".join(query_terms)

        return self.search_datasets(
            query=query,
            limit=limit,
            organism=organism,
        )

    def get_quantification_data_types(self, accession: str) -> dict[str, Any]:
        """Determine what types of quantification data are available.

        Args:
            accession: PRIDE/ProteomeXchange accession

        Returns:
            Dictionary indicating available quantification data types:
            - label_free: Boolean
            - itraq: Boolean
            - tmt: Boolean
            - silac: Boolean
            - spectral_counting: Boolean
        """
        metadata = self.fetch_dataset_metadata(accession)
        quant_methods = metadata.get("quantification_methods", [])
        experiment_types = metadata.get("experiment_types", [])

        # Combine all relevant text
        all_methods = []
        for qm in quant_methods:
            if isinstance(qm, dict):
                all_methods.append(qm.get("name", "").lower())
            else:
                all_methods.append(str(qm).lower())

        for et in experiment_types:
            if isinstance(et, dict):
                all_methods.append(et.get("name", "").lower())
            else:
                all_methods.append(str(et).lower())

        methods_text = " ".join(all_methods)

        # Detect quantification types
        quant_types = {
            "label_free": any(term in methods_text for term in ["label-free", "label free", "lfq"]),
            "itraq": "itraq" in methods_text,
            "tmt": "tmt" in methods_text or "tandem mass tag" in methods_text,
            "silac": "silac" in methods_text,
            "spectral_counting": "spectral count" in methods_text,
            "dia": "dia" in methods_text or "swath" in methods_text,
            "targeted": any(term in methods_text for term in ["srm", "mrm", "prm", "targeted"]),
        }

        return quant_types
