"""LLM-powered metadata curator."""

import json
from typing import Any

from anthropic import Anthropic

from quration.config import get_config
from quration.data_sources.geo import GEOFetcher
from quration.data_sources.ontologies import OntologyMapper
from quration.models.metadata import (
    CuratedDataset,
    CuratedSample,
    ExperimentalProtocol,
    OntologyTerm,
    Platform,
    QualityMetrics,
    SampleCharacteristics,
)


class MetadataCurator:
    """LLM-powered curator for NGS metadata."""

    # System prompt for curation (will be cached)
    CURATION_SYSTEM_PROMPT = """You are an expert bioinformatics curator specializing in Next-Generation Sequencing (NGS) metadata.

Your role is to curate, standardize, and validate metadata from public genomics datasets. You have deep knowledge of:
- NGS experimental protocols and best practices
- Sample characteristics and biological metadata
- Standard ontologies (EFO, UBERON, Cell Ontology, MONDO, NCBITaxon, etc.)
- Data quality standards for genomics metadata

When curating metadata, you should:
1. **Standardize terminology**: Convert free-text descriptions to standardized terms
2. **Validate protocols**: Check if experimental protocols are complete and scientifically sound
3. **Enrich information**: Infer missing information from context when confident
4. **Map to ontologies**: Suggest appropriate ontology terms for biological concepts
5. **Assess quality**: Evaluate completeness, consistency, and compliance with standards

Guidelines:
- Be conservative with inference - only fill missing data when highly confident
- Prioritize accuracy over completeness
- Flag any inconsistencies or quality issues
- Use standard ontologies whenever possible
- Maintain provenance of changes

Output your curation in valid JSON format following the provided schema."""

    def __init__(
        self,
        api_key: str | None = None,
        use_fast_model: bool = True,
    ):
        """Initialize metadata curator.

        Args:
            api_key: Anthropic API key (uses config if not provided)
            use_fast_model: Use fast model (Haiku) instead of smart model (Sonnet). Defaults to True (Haiku).
        """
        config = get_config()

        # max_tokens / temperature defaults live on the anthropic config block
        self.llm_config = config.llm.anthropic
        self.provider_name = config.llm.provider
        self.use_subscription = self.provider_name == "claude_subscription"

        if self.use_subscription:
            # Local, subscription-backed path via `claude -p` — no API key,
            # no prompt-caching/token tracking (handled by the CLI/subscription).
            from quration.llm import get_provider_from_config

            self.subscription_provider = get_provider_from_config(config)
            self.client = None
            self.api_key = None
            cs = config.llm.claude_subscription
            self.model = cs.fast_model if use_fast_model else cs.smart_model
            self.enable_caching = False
        else:
            # Metered Anthropic API path (keeps prompt caching + token tracking)
            self.api_key = api_key or config.llm.anthropic.api_key
            if not self.api_key:
                raise ValueError("Anthropic API key not provided")
            self.client = Anthropic(api_key=self.api_key)
            self.subscription_provider = None
            self.model = (
                self.llm_config.fast_model if use_fast_model else self.llm_config.smart_model
            )
            self.enable_caching = self.llm_config.enable_prompt_caching

        # Initialize data sources
        self.geo_fetcher = GEOFetcher()
        self.ontology_mapper = OntologyMapper()

        # Cost tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_read_tokens = 0
        self.total_cache_write_tokens = 0

    def _create_curation_prompt(
        self,
        sample_metadata: dict[str, Any],
        dataset_context: dict[str, Any] | None = None,
    ) -> str:
        """Create prompt for sample metadata curation.

        Args:
            sample_metadata: Raw sample metadata
            dataset_context: Optional dataset-level context

        Returns:
            Formatted prompt
        """
        prompt = "Please curate the following NGS sample metadata.\n\n"

        if dataset_context:
            prompt += "## Dataset Context\n"
            prompt += f"Dataset ID: {dataset_context.get('id', 'Unknown')}\n"
            prompt += f"Title: {dataset_context.get('title', 'Unknown')}\n"
            if "description" in dataset_context:
                prompt += f"Description: {dataset_context['description']}\n"
            if "organism" in dataset_context:
                prompt += f"Organism: {dataset_context['organism']}\n"
            prompt += "\n"

        prompt += "## Raw Sample Metadata\n"
        prompt += f"```json\n{json.dumps(sample_metadata, indent=2)}\n```\n\n"

        prompt += """## Curation Tasks

Please perform the following:

1. **Extract and standardize** sample characteristics:
   - Organism (species)
   - Tissue/organ
   - Cell type (if applicable)
   - Disease state (if applicable)
   - Age, sex, genotype (if available)
   - Other relevant characteristics

2. **Suggest ontology terms** for:
   - Organism → NCBITaxon
   - Tissue → UBERON
   - Cell type → Cell Ontology (CL)
   - Disease → MONDO or DOID

3. **Assess quality**:
   - Completeness: What proportion of important fields are filled?
   - Consistency: Are there any contradictions?
   - Issues: Flag any problems or missing critical information

4. **Provide curation notes**: Brief notes on any assumptions or changes made

Return your curation as a JSON object with this structure:
```json
{
  "sample_id": "sample identifier",
  "sample_name": "sample name/title",
  "organism": {"term": "Homo sapiens", "ontology_id": "NCBITaxon:9606", "confidence": 1.0},
  "tissue": {"term": "breast", "ontology_id": "UBERON:0000310", "confidence": 0.9},
  "cell_type": null,
  "disease": {"term": "breast carcinoma", "ontology_id": "MONDO:0007254", "confidence": 0.85},
  "age": "45",
  "sex": "female",
  "additional_characteristics": {},
  "completeness_score": 0.8,
  "consistency_score": 1.0,
  "quality_issues": [],
  "curation_notes": ["Inferred tissue from sample description"]
}
```

Provide only the JSON output, no additional text."""

        return prompt

    def curate_sample(
        self,
        sample_metadata: dict[str, Any],
        dataset_context: dict[str, Any] | None = None,
    ) -> CuratedSample:
        """Curate a single sample's metadata using LLM.

        Args:
            sample_metadata: Raw sample metadata
            dataset_context: Optional dataset-level context

        Returns:
            CuratedSample with standardized metadata
        """
        # Create prompt
        user_prompt = self._create_curation_prompt(sample_metadata, dataset_context)

        # Prepare messages
        messages = [{"role": "user", "content": user_prompt}]

        if self.use_subscription:
            # Subscription-backed completion (no usage/cache tracking).
            response_text = self.subscription_provider.create_message(
                messages=messages,
                model=self.model,
                max_tokens=self.llm_config.max_tokens,
                temperature=self.llm_config.temperature,
                system=self.CURATION_SYSTEM_PROMPT,
            )
        else:
            # Call Claude API with caching
            cache_control = {"type": "ephemeral"} if self.enable_caching else None

            system_blocks = [
                {
                    "type": "text",
                    "text": self.CURATION_SYSTEM_PROMPT,
                    "cache_control": cache_control,
                }
            ]

            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.llm_config.max_tokens,
                temperature=self.llm_config.temperature,
                system=system_blocks,
                messages=messages,
            )

            # Track token usage
            usage = response.usage
            self.total_input_tokens += usage.input_tokens
            self.total_output_tokens += usage.output_tokens

            if hasattr(usage, "cache_read_input_tokens"):
                self.total_cache_read_tokens += usage.cache_read_input_tokens or 0
            if hasattr(usage, "cache_creation_input_tokens"):
                self.total_cache_write_tokens += usage.cache_creation_input_tokens or 0

            # Parse response
            response_text = response.content[0].text

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()

        curated_data = json.loads(response_text)

        # Convert to structured models
        characteristics = SampleCharacteristics(
            sample_id=curated_data.get("sample_id", ""),
            sample_name=curated_data.get("sample_name"),
            organism=self._parse_ontology_term(curated_data.get("organism")),
            tissue=self._parse_ontology_term(curated_data.get("tissue")),
            cell_type=self._parse_ontology_term(curated_data.get("cell_type")),
            disease=self._parse_ontology_term(curated_data.get("disease")),
            development_stage=self._parse_ontology_term(curated_data.get("development_stage")),
            age=curated_data.get("age"),
            sex=curated_data.get("sex"),
            genotype=self._parse_ontology_term(curated_data.get("genotype")),
            treatment=self._parse_ontology_term(curated_data.get("treatment")),
            additional_characteristics=curated_data.get("additional_characteristics", {}),
            original_characteristics=sample_metadata,
            curation_notes=curated_data.get("curation_notes", []),
        )

        quality_metrics = QualityMetrics(
            completeness_score=curated_data.get("completeness_score", 0.0),
            consistency_score=curated_data.get("consistency_score", 1.0),
            consistency_issues=curated_data.get("quality_issues", []),
            overall_quality_score=curated_data.get("completeness_score", 0.0),
        )

        # Enhance with ontology mapper for any missing mappings
        self._enhance_with_ontology_mapping(characteristics)

        # Calculate quality grade
        quality_metrics.quality_grade = self._calculate_quality_grade(
            quality_metrics.overall_quality_score
        )

        curated_sample = CuratedSample(
            characteristics=characteristics,
            quality_metrics=quality_metrics,
            source_database="GEO",
            source_id=characteristics.sample_id,
        )

        return curated_sample

    def _parse_ontology_term(self, term_data: dict[str, Any] | None) -> OntologyTerm | None:
        """Parse ontology term from curated data.

        Args:
            term_data: Dictionary with term information

        Returns:
            OntologyTerm or None
        """
        if not term_data or not isinstance(term_data, dict):
            return None

        return OntologyTerm(
            term=term_data.get("term", ""),
            ontology_id=term_data.get("ontology_id"),
            ontology_name=term_data.get("ontology_name"),
            confidence=term_data.get("confidence", 0.5),
        )

    def _enhance_with_ontology_mapping(self, characteristics: SampleCharacteristics) -> None:
        """Enhance characteristics with ontology mappings for unmapped terms.

        Args:
            characteristics: SampleCharacteristics to enhance (modified in place)
        """
        # Map organism if not already mapped
        if characteristics.organism and not characteristics.organism.ontology_id:
            mapped = self.ontology_mapper.map_organism(characteristics.organism.term)
            if mapped:
                characteristics.organism = mapped

        # Map tissue
        if characteristics.tissue and not characteristics.tissue.ontology_id:
            mapped = self.ontology_mapper.map_tissue(characteristics.tissue.term)
            if mapped:
                characteristics.tissue = mapped

        # Map cell type
        if characteristics.cell_type and not characteristics.cell_type.ontology_id:
            mapped = self.ontology_mapper.map_cell_type(characteristics.cell_type.term)
            if mapped:
                characteristics.cell_type = mapped

        # Map disease
        if characteristics.disease and not characteristics.disease.ontology_id:
            mapped = self.ontology_mapper.map_disease(characteristics.disease.term)
            if mapped:
                characteristics.disease = mapped

    def _calculate_quality_grade(self, score: float) -> str:
        """Calculate letter grade from quality score.

        Args:
            score: Quality score (0-1)

        Returns:
            Letter grade (A/B/C/D/F)
        """
        if score >= 0.9:
            return "A"
        elif score >= 0.8:
            return "B"
        elif score >= 0.7:
            return "C"
        elif score >= 0.6:
            return "D"
        else:
            return "F"

    def get_cost_estimate(self) -> dict[str, Any]:
        """Get cost estimate for API usage.

        Returns:
            Dictionary with token usage and cost estimates
        """
        # Pricing (as of late 2024, check current pricing)
        if "haiku" in self.model:
            input_cost_per_m = 0.25
            output_cost_per_m = 1.25
            cache_write_cost_per_m = 0.30
            cache_read_cost_per_m = 0.03
        else:  # sonnet
            input_cost_per_m = 3.00
            output_cost_per_m = 15.00
            cache_write_cost_per_m = 3.75
            cache_read_cost_per_m = 0.30

        input_cost = (self.total_input_tokens / 1_000_000) * input_cost_per_m
        output_cost = (self.total_output_tokens / 1_000_000) * output_cost_per_m
        cache_write_cost = (self.total_cache_write_tokens / 1_000_000) * cache_write_cost_per_m
        cache_read_cost = (self.total_cache_read_tokens / 1_000_000) * cache_read_cost_per_m

        total_cost = input_cost + output_cost + cache_write_cost + cache_read_cost

        return {
            "model": self.model,
            "tokens": {
                "input": self.total_input_tokens,
                "output": self.total_output_tokens,
                "cache_write": self.total_cache_write_tokens,
                "cache_read": self.total_cache_read_tokens,
            },
            "cost_usd": {
                "input": round(input_cost, 4),
                "output": round(output_cost, 4),
                "cache_write": round(cache_write_cost, 4),
                "cache_read": round(cache_read_cost, 4),
                "total": round(total_cost, 4),
            },
        }

    def curate_from_query(
        self, query: str, limit: int = 5, samples_per_dataset: int = 10
    ) -> list[CuratedDataset]:
        """End-to-end: Search GEO, fetch metadata, and curate.

        Args:
            query: Search query
            limit: Maximum number of datasets
            samples_per_dataset: Maximum samples per dataset to curate

        Returns:
            List of curated datasets
        """
        # Fetch datasets from GEO
        datasets = self.geo_fetcher.fetch_datasets_from_query(query, limit=limit)

        curated_datasets = []

        for dataset_info in datasets:
            if "full_metadata" not in dataset_info:
                continue

            metadata = dataset_info["full_metadata"]
            series = metadata.get("series", {})
            samples = metadata.get("samples", [])[:samples_per_dataset]

            # Extract dataset context
            dataset_context = {
                "id": dataset_info.get("accession"),
                "title": series.get("Series_title", ""),
                "description": series.get("Series_summary", ""),
                "organism": series.get("Series_sample_organism", ""),
            }

            # Curate each sample
            curated_samples = []
            for sample in samples:
                try:
                    sample_chars = self.geo_fetcher.extract_sample_characteristics(sample)
                    curated_sample = self.curate_sample(sample_chars, dataset_context)
                    curated_samples.append(curated_sample)
                except Exception as e:
                    print(f"Error curating sample: {e}")
                    continue

            if not curated_samples:
                continue

            # Create curated dataset
            # Extract platform info
            platforms = metadata.get("platforms", [])
            platform_info = platforms[0] if platforms else {}

            platform = Platform(
                platform_type=platform_info.get("Platform_title", "Unknown"),
                platform_model=platform_info.get("Platform_technology", ""),
                platform_id=platform_info.get("Platform_geo_accession", ""),
            )

            # Create protocol (simplified for now)
            # GEO's Series_type is often a list, extract first element if so
            series_type = series.get("Series_type", "Unknown")
            if isinstance(series_type, list):
                series_type = series_type[0] if series_type else "Unknown"

            protocol = ExperimentalProtocol(
                experiment_type=series_type,
                library_strategy="Unknown",
            )

            # Calculate dataset-level quality
            avg_quality = sum(s.quality_metrics.overall_quality_score for s in curated_samples) / len(
                curated_samples
            )

            dataset_quality = QualityMetrics(
                completeness_score=avg_quality,
                consistency_score=1.0,
                overall_quality_score=avg_quality,
            )
            dataset_quality.quality_grade = self._calculate_quality_grade(avg_quality)

            curated_dataset = CuratedDataset(
                dataset_id=dataset_info.get("accession", ""),
                title=series.get("Series_title", ""),
                description=series.get("Series_summary"),
                platform=platform,
                protocol=protocol,
                samples=curated_samples,
                sample_count=len(curated_samples),
                dataset_quality_metrics=dataset_quality,
            )

            curated_datasets.append(curated_dataset)

        return curated_datasets
