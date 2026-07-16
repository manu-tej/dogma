"""
LLM-powered analysis plan generator.

This module uses LLMs to analyze curated dataset metadata and generate
comprehensive analysis plans with pipeline recommendations.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..llm.providers import LLMProvider
from .models import AnalysisPlan, ComparisonGroup, PipelineType, ReferenceGenome
from .pipeline_registry import (
    GenomeRegistry,
    PipelineRegistry,
    normalize_library_strategy,
)

logger = logging.getLogger(__name__)


class AnalysisPlanGenerator:
    """Generate analysis plans from curated dataset metadata using LLMs."""

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize the plan generator.

        Args:
            llm_provider: Optional LLM provider instance. When omitted, the
                configured provider is resolved lazily on the first LLM-backed
                generation call, so local plan inspection/saving needs no key.
            model: Model name to use; defaults to the active provider's smart
                model from config.
        """
        from quration.llm import get_model_for_config, get_provider_from_config

        self.llm_provider = llm_provider
        self.model = model or get_model_for_config(tier="smart")

    def generate_plan(
        self, curated_dataset: Dict[str, Any]
    ) -> AnalysisPlan:
        """
        Generate an analysis plan for a curated dataset.

        Args:
            curated_dataset: Curated dataset metadata (JSON format)

        Returns:
            AnalysisPlan with recommendations
        """
        logger.info(f"Generating analysis plan for dataset {curated_dataset.get('dataset_id')}")

        # Extract key metadata
        metadata_summary = self._extract_metadata_summary(curated_dataset)

        # Generate plan using LLM
        plan_data = self._generate_plan_with_llm(metadata_summary, curated_dataset)

        # Build analysis plan
        analysis_plan = self._build_analysis_plan(plan_data, curated_dataset)

        logger.info(
            f"Generated plan: {analysis_plan.primary_pipeline.value} "
            f"with {len(analysis_plan.comparison_groups)} comparison groups"
        )

        return analysis_plan

    def generate_plan_from_file(self, curated_dataset_path: Path) -> AnalysisPlan:
        """
        Generate analysis plan from a curated dataset JSON file.

        Args:
            curated_dataset_path: Path to curated dataset JSON file

        Returns:
            AnalysisPlan
        """
        with open(curated_dataset_path, "r") as f:
            curated_dataset = json.load(f)

        return self.generate_plan(curated_dataset)

    def _extract_metadata_summary(self, curated_dataset: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key metadata fields for LLM analysis."""
        summary = {
            "dataset_id": curated_dataset.get("dataset_id", "Unknown"),
            "title": curated_dataset.get("title", ""),
            "summary": curated_dataset.get("summary", ""),
            "sample_count": len(curated_dataset.get("samples", [])),
            "samples": [],
        }

        # Extract sample characteristics
        for sample in curated_dataset.get("samples", [])[:10]:  # Limit to first 10 for context
            characteristics = sample.get("characteristics", {})
            sample_info = {
                "sample_id": sample.get("sample_id"),
                # `or {}` guards a key that's present but explicitly None (ungrounded
                # characteristic) — `.get("X", {})` only defaults when the key is absent.
                "organism": (characteristics.get("organism") or {}).get("term"),
                "tissue": (characteristics.get("tissue") or {}).get("term"),
                "cell_type": (characteristics.get("cell_type") or {}).get("term"),
                "disease": (characteristics.get("disease") or {}).get("term"),
                "treatment": characteristics.get("treatment"),
                "genotype": characteristics.get("genotype"),
            }
            summary["samples"].append(sample_info)

        # Extract protocol information
        protocol = curated_dataset.get("protocol", {})
        summary["protocol"] = {
            "library_strategy": protocol.get("library_strategy"),
            "library_source": protocol.get("library_source"),
            "library_selection": protocol.get("library_selection"),
            "instrument_model": protocol.get("instrument_model"),
            "read_length": protocol.get("read_length"),
            "is_paired_end": protocol.get("is_paired_end"),
        }

        # Experimental design
        summary["experimental_design"] = curated_dataset.get("experimental_design")

        return summary

    def _generate_plan_with_llm(
        self, metadata_summary: Dict[str, Any], full_dataset: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use LLM to generate analysis recommendations."""
        if self.llm_provider is None:
            from quration.llm import get_provider_from_config

            self.llm_provider = get_provider_from_config()
        system_prompt = """You are an expert bioinformatician specializing in NGS data analysis using nf-core pipelines.

Your task is to analyze curated dataset metadata and recommend the most appropriate nf-core analysis pipeline(s).

Available nf-core pipelines:
- nf-core/rnaseq: RNA-seq analysis (gene expression, differential expression)
- nf-core/sarek: Variant calling (WGS, WES, targeted sequencing)
- nf-core/chipseq: ChIP-seq analysis (peak calling, differential binding)
- nf-core/atacseq: ATAC-seq analysis (chromatin accessibility)
- nf-core/scrnaseq: Single-cell RNA-seq analysis
- nf-core/methylseq: Bisulfite-seq analysis (DNA methylation)

Provide your analysis in JSON format with these fields:
{
  "recommended_pipelines": ["pipeline1", "pipeline2"],
  "primary_pipeline": "pipeline1",
  "rationale": "Explanation of why these pipelines are recommended",
  "comparison_groups": [
    {
      "name": "comparison_name",
      "condition_a": "condition_a_description",
      "condition_b": "condition_b_description",
      "sample_ids_a": ["sample1", "sample2"],
      "sample_ids_b": ["sample3", "sample4"]
    }
  ],
  "expected_outputs": ["output1", "output2"],
  "estimated_runtime": "X hours",
  "analysis_parameters": {
    "genome_build": "GRCh38",
    "key_settings": {}
  }
}

Extract comparison groups from the experimental design and sample metadata. Look for:
- Treatment vs control conditions
- Disease vs healthy samples
- Tissue type differences
- Genotype variations
- Time points

Be specific and actionable in your recommendations."""

        user_prompt = f"""Analyze this curated NGS dataset and recommend analysis pipelines:

Dataset ID: {metadata_summary['dataset_id']}
Title: {metadata_summary['title']}
Summary: {metadata_summary['summary']}

Sample Count: {metadata_summary['sample_count']}

Protocol:
- Library Strategy: {metadata_summary['protocol']['library_strategy']}
- Library Source: {metadata_summary['protocol']['library_source']}
- Instrument: {metadata_summary['protocol']['instrument_model']}
- Paired-end: {metadata_summary['protocol']['is_paired_end']}

Sample Characteristics (first 10 samples):
{json.dumps(metadata_summary['samples'], indent=2)}

Experimental Design:
{metadata_summary.get('experimental_design', 'Not specified')}

Provide a comprehensive analysis plan in JSON format."""

        messages = [{"role": "user", "content": user_prompt}]

        response = self.llm_provider.create_message(
            messages=messages,
            model=self.model,
            max_tokens=4096,
            temperature=0.3,  # Lower temperature for more consistent recommendations
            system=system_prompt,
        )

        # Extract JSON from response (handle markdown code blocks)
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()

        try:
            plan_data = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response: {response}")
            raise ValueError(f"LLM response was not valid JSON: {e}")

        return plan_data

    def _build_analysis_plan(
        self, plan_data: Dict[str, Any], curated_dataset: Dict[str, Any]
    ) -> AnalysisPlan:
        """Build an AnalysisPlan object from LLM response and metadata."""
        # Extract basic info
        dataset_id = curated_dataset.get("dataset_id", "Unknown")
        dataset_title = curated_dataset.get("title", "")

        # Map pipeline names to PipelineType
        recommended_pipelines = []
        for pipeline_name in plan_data.get("recommended_pipelines", []):
            try:
                pipeline_type = PipelineType(pipeline_name.lower())
                recommended_pipelines.append(pipeline_type)
            except ValueError:
                logger.warning(f"Unknown pipeline type: {pipeline_name}")

        primary_pipeline_str = plan_data.get("primary_pipeline", "rnaseq").lower()
        try:
            primary_pipeline = PipelineType(primary_pipeline_str)
        except ValueError:
            logger.warning(f"Unknown primary pipeline: {primary_pipeline_str}, defaulting to rnaseq")
            primary_pipeline = PipelineType.RNASEQ

        # Extract organism
        samples = curated_dataset.get("samples", [])
        organism = "Unknown"
        if samples:
            organism_data = samples[0].get("characteristics", {}).get("organism", {})
            organism = organism_data.get("term", "Unknown")

        # Get library strategy
        protocol = curated_dataset.get("protocol", {})
        library_strategy = protocol.get("library_strategy", "RNA-Seq")
        library_strategy = normalize_library_strategy(library_strategy)

        # Determine genome
        genome_build = plan_data.get("analysis_parameters", {}).get("genome_build")
        if genome_build:
            suggested_genome = ReferenceGenome(
                name=genome_build,
                organism=organism,
                igenomes_ref=genome_build,
            )
        else:
            suggested_genome = GenomeRegistry.get_default_genome(organism)
            if not suggested_genome:
                # Fallback
                suggested_genome = ReferenceGenome(
                    name="Unknown",
                    organism=organism,
                )

        # Build comparison groups
        comparison_groups = []
        for cg in plan_data.get("comparison_groups", []):
            comparison_groups.append(
                ComparisonGroup(
                    name=cg.get("name", "comparison"),
                    condition_a=cg.get("condition_a", ""),
                    condition_b=cg.get("condition_b", ""),
                    sample_ids_a=cg.get("sample_ids_a", []),
                    sample_ids_b=cg.get("sample_ids_b", []),
                )
            )

        # Extract SRA IDs if available
        sra_ids = []
        for sample in samples:
            sra_id = sample.get("sra_id") or sample.get("sample_id")
            if sra_id and sra_id.startswith("SRR"):
                sra_ids.append(sra_id)

        # Build the plan
        analysis_plan = AnalysisPlan(
            dataset_id=dataset_id,
            dataset_title=dataset_title,
            recommended_pipelines=recommended_pipelines or [primary_pipeline],
            primary_pipeline=primary_pipeline,
            organism=organism,
            library_strategy=library_strategy,
            sample_count=len(samples),
            has_paired_end=protocol.get("is_paired_end", False),
            suggested_genome=suggested_genome,
            experimental_design=curated_dataset.get("experimental_design"),
            comparison_groups=comparison_groups,
            rationale=plan_data.get("rationale", ""),
            expected_outputs=plan_data.get("expected_outputs", []),
            estimated_runtime=plan_data.get("estimated_runtime"),
            requires_download=len(sra_ids) == 0,  # Require download if no SRA IDs
            sra_ids=sra_ids,
        )

        return analysis_plan

    def save_plan(self, plan: AnalysisPlan, output_path: Path) -> None:
        """Save analysis plan to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(plan.model_dump(mode="json"), f, indent=2, default=str)

        logger.info(f"Saved analysis plan to {output_path}")
