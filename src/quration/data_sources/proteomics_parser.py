"""Proteomics metadata parser - maps PRIDE/ProteomeXchange data to unified schema."""

from datetime import datetime
from typing import Any

from quration.models.metadata import (
    CuratedDataset,
    CuratedSample,
    ExperimentalProtocol,
    ExperimentType,
    MassSpecPlatform,
    OntologyTerm,
    Platform,
    Publication,
    QualityMetrics,
    SampleCharacteristics,
)


class ProteomicsMetadataParser:
    """Parses proteomics metadata from PRIDE into unified schema."""

    def __init__(self):
        """Initialize parser."""
        pass

    def parse_pride_dataset(self, pride_metadata: dict[str, Any]) -> CuratedDataset:
        """Parse PRIDE dataset metadata into CuratedDataset.

        Args:
            pride_metadata: Structured metadata from ProteomicsFetcher

        Returns:
            CuratedDataset with proteomics data mapped to unified schema
        """
        accession = pride_metadata.get("accession", "")
        title = pride_metadata.get("title", "")
        description = pride_metadata.get("description", "")

        # Parse platform (mass spectrometry instrument)
        platform = self._parse_platform(pride_metadata)

        # Parse experimental protocol
        protocol = self._parse_protocol(pride_metadata)

        # Parse samples
        samples = self._parse_samples(pride_metadata)

        # Parse publication
        publication = self._parse_publication(pride_metadata)

        # Create dataset
        dataset = CuratedDataset(
            dataset_id=accession,
            title=title,
            description=description,
            platform=platform,
            protocol=protocol,
            samples=samples,
            sample_count=len(samples),
            publication=publication,
            submission_date=pride_metadata.get("submission_date", ""),
            release_date=pride_metadata.get("publication_date", ""),
            dataset_quality_metrics=self._calculate_dataset_quality(pride_metadata, samples),
            source_database="PRIDE",
            raw_metadata=pride_metadata.get("_raw", {}),
        )

        return dataset

    def _parse_platform(self, pride_metadata: dict[str, Any]) -> Platform:
        """Parse mass spectrometry platform information.

        Args:
            pride_metadata: PRIDE metadata dictionary

        Returns:
            Platform object
        """
        instruments = pride_metadata.get("instruments", [])

        # Get primary instrument
        platform_name = "Unknown"
        platform_model = None
        platform_id = None

        if instruments:
            primary_instrument = instruments[0]
            if isinstance(primary_instrument, dict):
                platform_name = primary_instrument.get("name", "Unknown")
                platform_id = primary_instrument.get("accession", None)
            else:
                platform_name = str(primary_instrument)

        # Try to map to known platform enum
        platform_type = self._map_instrument_to_platform(platform_name)

        return Platform(
            platform_type=platform_type,
            platform_model=platform_name,
            platform_id=platform_id,
            platform_category="mass_spectrometry",
        )

    def _map_instrument_to_platform(self, instrument_name: str) -> MassSpecPlatform | str:
        """Map instrument name to MassSpecPlatform enum.

        Args:
            instrument_name: Instrument name from PRIDE

        Returns:
            MassSpecPlatform enum value or original string
        """
        name_lower = instrument_name.lower()

        # Orbitrap family
        if "fusion lumos" in name_lower:
            return MassSpecPlatform.ORBITRAP_FUSION_LUMOS
        elif "fusion" in name_lower and "orbitrap" in name_lower:
            return MassSpecPlatform.ORBITRAP_FUSION
        elif "eclipse" in name_lower:
            return MassSpecPlatform.ORBITRAP_ECLIPSE
        elif "exploris" in name_lower:
            return MassSpecPlatform.ORBITRAP_EXPLORIS
        elif "astral" in name_lower:
            return MassSpecPlatform.ORBITRAP_ASTRAL
        elif "q exactive hf-x" in name_lower or "qe hf-x" in name_lower:
            return MassSpecPlatform.Q_EXACTIVE_HF_X
        elif "q exactive hf" in name_lower or "qe-hf" in name_lower:
            return MassSpecPlatform.Q_EXACTIVE_HF
        elif "q exactive plus" in name_lower:
            return MassSpecPlatform.Q_EXACTIVE_PLUS
        elif "q exactive" in name_lower or "qe" in name_lower:
            return MassSpecPlatform.Q_EXACTIVE

        # timsTOF
        elif "timstof pro" in name_lower:
            return MassSpecPlatform.TIMSTOF_PRO
        elif "timstof flex" in name_lower:
            return MassSpecPlatform.TIMSTOF_FLEX
        elif "timstof scp" in name_lower:
            return MassSpecPlatform.TIMSTOF_SCP

        # Triple TOF
        elif "tripletof 6600" in name_lower or "triple tof 6600" in name_lower:
            return MassSpecPlatform.TRIPLE_TOF_6600
        elif "tripletof 5600" in name_lower or "triple tof 5600" in name_lower:
            return MassSpecPlatform.TRIPLE_TOF_5600

        # Triple Quadrupole
        elif "tsq quantiva" in name_lower:
            return MassSpecPlatform.TSQ_QUANTIVA
        elif "tsq altis" in name_lower:
            return MassSpecPlatform.TSQ_ALTIS
        elif "qtrap" in name_lower:
            return MassSpecPlatform.QTRAP

        # MALDI
        elif "maldi" in name_lower:
            if "tof/tof" in name_lower or "toftof" in name_lower:
                return MassSpecPlatform.MALDI_TOF_TOF
            return MassSpecPlatform.MALDI_TOF

        # Older instruments
        elif "ltq orbitrap" in name_lower:
            return MassSpecPlatform.LTQ_ORBITRAP
        elif "ltq" in name_lower:
            return MassSpecPlatform.LTQ
        elif "velos" in name_lower:
            return MassSpecPlatform.VELOS

        # Generic Q-TOF
        elif "qtof" in name_lower or "q-tof" in name_lower:
            return MassSpecPlatform.QTOF

        # Return original string if no match
        return instrument_name

    def _parse_protocol(self, pride_metadata: dict[str, Any]) -> ExperimentalProtocol:
        """Parse experimental protocol information.

        Args:
            pride_metadata: PRIDE metadata dictionary

        Returns:
            ExperimentalProtocol object
        """
        # Determine experiment type
        experiment_types = pride_metadata.get("experiment_types", [])
        quant_methods = pride_metadata.get("quantification_methods", [])

        # Extract names
        exp_type_names = []
        for et in experiment_types:
            if isinstance(et, dict):
                exp_type_names.append(et.get("name", ""))
            else:
                exp_type_names.append(str(et))

        quant_method_names = []
        for qm in quant_methods:
            if isinstance(qm, dict):
                quant_method_names.append(qm.get("name", ""))
            else:
                quant_method_names.append(str(qm))

        # Map to experiment type enum
        experiment_type = self._map_experiment_type(exp_type_names, quant_method_names)

        # Library strategy (for proteomics, this is the quantification method)
        library_strategy = self._map_library_strategy(quant_method_names)

        # Protocols
        sample_protocol = pride_metadata.get("sample_processing_protocol", "")
        data_protocol = pride_metadata.get("data_processing_protocol", "")

        return ExperimentalProtocol(
            experiment_type=experiment_type,
            library_strategy=library_strategy,
            library_source="PROTEOMIC",
            extraction_protocol=sample_protocol,
            sequencing_protocol=data_protocol,
            protocol_validated=bool(sample_protocol and data_protocol),
            protocol_completeness_score=self._calculate_protocol_completeness(
                sample_protocol, data_protocol
            ),
        )

    def _map_experiment_type(
        self, exp_types: list[str], quant_methods: list[str]
    ) -> ExperimentType | str:
        """Map experiment and quantification types to ExperimentType enum.

        Args:
            exp_types: List of experiment type names
            quant_methods: List of quantification method names

        Returns:
            ExperimentType enum value or string
        """
        # Combine all text for analysis
        all_text = " ".join(exp_types + quant_methods).lower()

        # PTM-specific experiments
        if "phospho" in all_text:
            return ExperimentType.PHOSPHOPROTEOMICS
        elif "glyco" in all_text:
            return ExperimentType.GLYCOPROTEOMICS
        elif "ubiquitin" in all_text:
            return ExperimentType.UBIQUITINOMICS
        elif "acetyl" in all_text:
            return ExperimentType.ACETYLOMICS
        elif "ptm" in all_text or "post-translational" in all_text:
            return ExperimentType.PTM_ANALYSIS

        # Quantification strategies
        elif "tmt" in all_text or "tandem mass tag" in all_text:
            return ExperimentType.TMT_LABELING
        elif "itraq" in all_text:
            return ExperimentType.ITRAQ_LABELING
        elif "silac" in all_text:
            return ExperimentType.SILAC
        elif "label-free" in all_text or "label free" in all_text or "lfq" in all_text:
            return ExperimentType.LABEL_FREE_QUANT

        # Acquisition strategies
        elif "dia" in all_text or "swath" in all_text:
            return ExperimentType.DIA_PROTEOMICS
        elif "dda" in all_text:
            return ExperimentType.DDA_PROTEOMICS
        elif "srm" in all_text or "mrm" in all_text or "prm" in all_text or "targeted" in all_text:
            return ExperimentType.TARGETED_PROTEOMICS

        # General approaches
        elif "top-down" in all_text or "top down" in all_text:
            return ExperimentType.TOP_DOWN_PROTEOMICS
        elif "bottom-up" in all_text or "bottom up" in all_text:
            return ExperimentType.BOTTOM_UP_PROTEOMICS
        elif "shotgun" in all_text:
            return ExperimentType.SHOTGUN_PROTEOMICS

        # Default to LC-MS/MS
        return ExperimentType.LC_MSMS

    def _map_library_strategy(self, quant_methods: list[str]) -> str:
        """Map quantification methods to library strategy.

        Args:
            quant_methods: List of quantification method names

        Returns:
            Library strategy string
        """
        if not quant_methods:
            return "PROTEOMICS"

        # Use first quantification method
        first_method = quant_methods[0].upper()
        return first_method if first_method else "PROTEOMICS"

    def _calculate_protocol_completeness(
        self, sample_protocol: str, data_protocol: str
    ) -> float:
        """Calculate protocol completeness score.

        Args:
            sample_protocol: Sample processing protocol text
            data_protocol: Data processing protocol text

        Returns:
            Completeness score (0-1)
        """
        score = 0.0

        # Sample protocol (50% of score)
        if sample_protocol:
            # Basic presence: 25%
            score += 0.25

            # Length and detail (25%)
            if len(sample_protocol) > 100:
                score += 0.15
            elif len(sample_protocol) > 50:
                score += 0.10

        # Data protocol (50% of score)
        if data_protocol:
            # Basic presence: 25%
            score += 0.25

            # Length and detail (25%)
            if len(data_protocol) > 100:
                score += 0.15
            elif len(data_protocol) > 50:
                score += 0.10

        return min(score, 1.0)

    def _parse_samples(self, pride_metadata: dict[str, Any]) -> list[CuratedSample]:
        """Parse sample information from PRIDE metadata.

        Note: PRIDE typically stores sample-level metadata as dataset-level
        characteristics. For now, we create a single sample representing
        the dataset characteristics.

        Args:
            pride_metadata: PRIDE metadata dictionary

        Returns:
            List of CuratedSample objects
        """
        accession = pride_metadata.get("accession", "")

        # Extract characteristics from dataset-level metadata
        organisms = pride_metadata.get("organisms", [])
        tissues = pride_metadata.get("tissues", [])
        diseases = pride_metadata.get("diseases", [])
        cell_types = pride_metadata.get("cell_types", [])

        # Parse characteristics
        characteristics = SampleCharacteristics(
            sample_id=accession,
            sample_name=pride_metadata.get("title", ""),
            organism=self._parse_ontology_term(organisms[0] if organisms else None),
            tissue=self._parse_ontology_term(tissues[0] if tissues else None),
            cell_type=self._parse_ontology_term(cell_types[0] if cell_types else None),
            disease=self._parse_ontology_term(diseases[0] if diseases else None),
            original_characteristics={
                "organisms": str(organisms),
                "tissues": str(tissues),
                "diseases": str(diseases),
                "cell_types": str(cell_types),
            },
        )

        # Calculate quality metrics
        quality_metrics = self._calculate_sample_quality(characteristics)

        # Create curated sample
        sample = CuratedSample(
            characteristics=characteristics,
            quality_metrics=quality_metrics,
            source_database="PRIDE",
            source_id=accession,
            curated_at=datetime.utcnow(),
        )

        # For now, return single sample
        # TODO: Parse individual assays/runs as separate samples
        return [sample]

    def _parse_ontology_term(
        self, cv_param: dict[str, Any] | str | None
    ) -> OntologyTerm | None:
        """Parse controlled vocabulary parameter to OntologyTerm.

        Args:
            cv_param: CV parameter from PRIDE

        Returns:
            OntologyTerm or None
        """
        if not cv_param:
            return None

        if isinstance(cv_param, str):
            # Free-text term (no accession) → lower confidence, matching the dict path.
            return OntologyTerm(
                term=cv_param, ontology_id=None, ontology_name=None, confidence=0.8
            )

        if isinstance(cv_param, dict):
            term = cv_param.get("name", "")
            accession = cv_param.get("accession", "")
            cv_label = cv_param.get("cv_label", "")

            if not term:
                return None

            # Extract ontology name from accession (e.g., "NCBITAXON:9606" -> "NCBITAXON")
            ontology_name = cv_label or (accession.split(":")[0] if accession and ":" in accession else None)

            # Construct IRI based on ontology
            iri = self._construct_ontology_iri(accession)

            return OntologyTerm(
                term=term,
                ontology_id=accession if accession else None,
                ontology_name=ontology_name,
                iri=iri,
                confidence=1.0 if accession else 0.8,
            )

        return None

    def _construct_ontology_iri(self, accession: str | None) -> str | None:
        """Construct full IRI from ontology accession.

        Args:
            accession: Ontology accession (e.g., "EFO:0000001")

        Returns:
            Full IRI or None
        """
        if not accession or ":" not in accession:
            return None

        prefix, local_id = accession.split(":", 1)
        prefix_upper = prefix.upper()

        # Map to standard ontology IRIs
        iri_map = {
            "NCBITAXON": f"http://purl.obolibrary.org/obo/NCBITaxon_{local_id}",
            "UBERON": f"http://purl.obolibrary.org/obo/UBERON_{local_id}",
            "EFO": f"http://www.ebi.ac.uk/efo/EFO_{local_id}",
            "CL": f"http://purl.obolibrary.org/obo/CL_{local_id}",
            "DOID": f"http://purl.obolibrary.org/obo/DOID_{local_id}",
            "MONDO": f"http://purl.obolibrary.org/obo/MONDO_{local_id}",
            "BTO": f"http://purl.obolibrary.org/obo/BTO_{local_id}",
            "PATO": f"http://purl.obolibrary.org/obo/PATO_{local_id}",
            "MS": f"http://purl.obolibrary.org/obo/MS_{local_id}",  # Mass spectrometry ontology
        }

        return iri_map.get(prefix_upper, None)

    def _calculate_sample_quality(self, characteristics: SampleCharacteristics) -> QualityMetrics:
        """Calculate quality metrics for sample.

        Args:
            characteristics: Sample characteristics

        Returns:
            QualityMetrics object
        """
        # Calculate completeness
        total_fields = 8  # organism, tissue, cell_type, disease, age, sex, genotype, treatment
        filled_fields = sum([
            characteristics.organism is not None,
            characteristics.tissue is not None,
            characteristics.cell_type is not None,
            characteristics.disease is not None,
            characteristics.age is not None,
            characteristics.sex is not None,
            characteristics.genotype is not None,
            characteristics.treatment is not None,
        ])

        completeness_score = filled_fields / total_fields

        # Calculate ontology coverage
        ontology_fields = 5  # organism, tissue, cell_type, disease, treatment
        ontology_mapped = sum([
            characteristics.organism is not None and characteristics.organism.ontology_id is not None,
            characteristics.tissue is not None and characteristics.tissue.ontology_id is not None,
            characteristics.cell_type is not None and characteristics.cell_type.ontology_id is not None,
            characteristics.disease is not None and characteristics.disease.ontology_id is not None,
            characteristics.treatment is not None and characteristics.treatment.ontology_id is not None,
        ])

        ontology_coverage = ontology_mapped / ontology_fields if ontology_fields > 0 else 0.0

        # Overall quality
        overall_quality_score = (completeness_score * 0.6 + ontology_coverage * 0.4)

        # Assign grade
        if overall_quality_score >= 0.9:
            grade = "A"
        elif overall_quality_score >= 0.8:
            grade = "B"
        elif overall_quality_score >= 0.7:
            grade = "C"
        elif overall_quality_score >= 0.6:
            grade = "D"
        else:
            grade = "F"

        return QualityMetrics(
            completeness_score=completeness_score,
            consistency_score=1.0,  # TODO: Implement consistency checks
            ontology_coverage=ontology_coverage,
            overall_quality_score=overall_quality_score,
            quality_grade=grade,
        )

    def _parse_publication(self, pride_metadata: dict[str, Any]) -> Publication | None:
        """Parse publication information.

        Args:
            pride_metadata: PRIDE metadata dictionary

        Returns:
            Publication object or None
        """
        references = pride_metadata.get("references", [])
        doi = pride_metadata.get("doi", "")

        if not references and not doi:
            return None

        # Extract from first reference
        if references:
            ref = references[0]
            pmid = ref.get("pubmed_id", "")
            reference_line = ref.get("reference_line", "")

            # Try to extract title, journal, year from reference line
            # Format is typically: "Authors. Title. Journal. Year"
            title = None
            journal = None
            year = None

            # Simple parsing - can be enhanced
            if reference_line:
                title = reference_line  # Simplified

            return Publication(
                pmid=pmid if pmid else None,
                title=title,
                doi=doi if doi else ref.get("doi", None),
            )

        # Just DOI available
        return Publication(doi=doi)

    def _calculate_dataset_quality(
        self, pride_metadata: dict[str, Any], samples: list[CuratedSample]
    ) -> QualityMetrics:
        """Calculate overall dataset quality metrics.

        Args:
            pride_metadata: PRIDE metadata dictionary
            samples: List of curated samples

        Returns:
            QualityMetrics object
        """
        # Average sample quality
        if samples:
            avg_sample_quality = sum(s.quality_metrics.overall_quality_score for s in samples) / len(samples)
            avg_completeness = sum(s.quality_metrics.completeness_score for s in samples) / len(samples)
            avg_ontology = sum(s.quality_metrics.ontology_coverage for s in samples) / len(samples)
        else:
            avg_sample_quality = 0.0
            avg_completeness = 0.0
            avg_ontology = 0.0

        # Dataset-level completeness
        dataset_fields = 5  # title, description, publication, protocols, instruments
        dataset_filled = sum([
            bool(pride_metadata.get("title")),
            bool(pride_metadata.get("description")),
            bool(pride_metadata.get("references") or pride_metadata.get("doi")),
            bool(pride_metadata.get("sample_processing_protocol")),
            bool(pride_metadata.get("instruments")),
        ])

        dataset_completeness = dataset_filled / dataset_fields

        # Overall
        overall_quality_score = (avg_sample_quality * 0.5 + dataset_completeness * 0.5)

        # Grade
        if overall_quality_score >= 0.9:
            grade = "A"
        elif overall_quality_score >= 0.8:
            grade = "B"
        elif overall_quality_score >= 0.7:
            grade = "C"
        elif overall_quality_score >= 0.6:
            grade = "D"
        else:
            grade = "F"

        return QualityMetrics(
            completeness_score=avg_completeness,
            consistency_score=1.0,
            ontology_coverage=avg_ontology,
            overall_quality_score=overall_quality_score,
            quality_grade=grade,
        )
