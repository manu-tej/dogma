"""
LLM-based Request Parser

Decomposes natural language analysis requests into structured tasks
using language models.
"""

import json
from typing import Any, Dict

from quration.broker.models import DataModality, ParsedRequest
from quration.config import QurationConfig
from quration.llm.providers import LLMProvider, get_llm_provider


class RequestParser:
    """
    Parses natural language analysis requests using LLMs.
    """

    def __init__(
        self,
        config: QurationConfig,
        provider: LLMProvider | None = None,
    ):
        """
        Initialize the request parser.

        Args:
            config: Quration configuration
            provider: Optional LLM provider (will use default if not provided)
        """
        self.config = config
        self._provider = provider  # Store the provider
        self._provider_initialized = provider is not None

    @property
    def provider(self) -> LLMProvider:
        """Lazy initialization of LLM provider."""
        if not self._provider_initialized:
            # Build provider from config so provider:claude_subscription /
            # openrouter / anthropic all route correctly.
            from quration.llm import get_provider_from_config

            self._provider = get_provider_from_config(self.config)
            self._provider_initialized = True
        return self._provider

    def parse_request(self, query: str, context: Dict[str, Any] | None = None) -> ParsedRequest:
        """
        Parse a natural language request into structured components.

        Args:
            query: User's natural language query
            context: Optional context (e.g., previous conversation)

        Returns:
            ParsedRequest with structured task information
        """
        # Build the parsing prompt
        prompt = self._build_parsing_prompt(query, context)

        # Call LLM with structured output request
        # Use the create_message method with proper message format.
        # Resolve the model for the active provider (alias for subscription).
        from quration.llm import get_model_for_config

        model = get_model_for_config(self.config, tier="smart")

        response = self.provider.create_message(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            max_tokens=2048,
            temperature=0.1,  # Low temperature for consistent parsing
        )

        # Parse the LLM response
        parsed_data = self._extract_structured_output(response)

        # Create ParsedRequest object
        parsed_request = ParsedRequest(
            original_query=query,
            data_modality=self._parse_modality(parsed_data.get("data_modality", "unknown")),
            analysis_type=parsed_data.get("analysis_type", "unknown"),
            specific_tools=parsed_data.get("specific_tools", []),
            organism=parsed_data.get("organism"),
            sample_count=parsed_data.get("sample_count"),
            experimental_design=parsed_data.get("experimental_design"),
            constraints=parsed_data.get("constraints", {}),
            preferences=parsed_data.get("preferences", {}),
            keywords=parsed_data.get("keywords", []),
            confidence=parsed_data.get("confidence", 0.7),
        )

        return parsed_request

    def _build_parsing_prompt(self, query: str, context: Dict[str, Any] | None) -> str:
        """
        Build the prompt for LLM-based request parsing.

        Args:
            query: User query
            context: Optional context

        Returns:
            Formatted prompt string
        """
        context_str = ""
        if context:
            context_str = f"\n\nAdditional Context:\n{json.dumps(context, indent=2)}"

        prompt = f"""You are an expert bioinformatics analyst. Parse the following analysis request and extract structured information.

User Request: "{query}"{context_str}

Extract the following information and respond ONLY with valid JSON:

{{
  "data_modality": "<one of: dna_seq, rna_seq, chip_seq, atac_seq, bisulfite_seq, single_cell_rna, single_cell_atac, metagenomics, metatranscriptomics, unknown>",
  "analysis_type": "<brief description of the requested analysis, e.g., 'differential expression', 'variant calling', 'peak calling'>",
  "specific_tools": ["<list of specific tools or methods mentioned, if any>"],
  "organism": "<target organism if mentioned, e.g., 'human', 'mouse', or null>",
  "sample_count": <number of samples if mentioned, or null>,
  "experimental_design": "<experimental design type if mentioned, e.g., 'case-control', 'time-series', or null>",
  "constraints": {{
    "<constraint_name>": "<constraint_value>"
  }},
  "preferences": {{
    "<preference_name>": "<preference_value>"
  }},
  "keywords": ["<list of key technical terms extracted from the request>"],
  "confidence": <float between 0 and 1 indicating your confidence in this parsing>
}}

Guidelines:
1. data_modality: Identify the sequencing technology/data type
2. analysis_type: What kind of analysis is being requested
3. specific_tools: Only include if explicitly mentioned (e.g., "use GATK", "run DESeq2")
4. organism: Extract if mentioned (human, mouse, etc.)
5. sample_count: Extract if mentioned
6. experimental_design: Case-control, time-series, etc.
7. constraints: Any limitations mentioned (time, resources, etc.)
8. preferences: User preferences (prefer published methods, need reproducibility, etc.)
9. keywords: Extract key technical terms
10. confidence: Your confidence in the parsing (0-1)

Respond ONLY with the JSON object, no additional text."""

        return prompt

    def _extract_structured_output(self, llm_response: str) -> Dict[str, Any]:
        """
        Extract structured JSON from LLM response.

        Args:
            llm_response: Raw LLM response

        Returns:
            Parsed dictionary
        """
        # Try to find JSON in the response
        response_text = llm_response.strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]

        response_text = response_text.strip()

        try:
            parsed = json.loads(response_text)
            return parsed
        except json.JSONDecodeError as e:
            # Fallback: try to extract JSON from within the text
            import re

            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

            # If all else fails, return a minimal valid response
            return {
                "data_modality": "unknown",
                "analysis_type": "unknown",
                "specific_tools": [],
                "keywords": [],
                "confidence": 0.3,
            }

    def _parse_modality(self, modality_str: str) -> DataModality:
        """
        Convert string to DataModality enum.

        Args:
            modality_str: Modality string from LLM

        Returns:
            DataModality enum value
        """
        modality_map = {
            "dna_seq": DataModality.DNA_SEQ,
            "rna_seq": DataModality.RNA_SEQ,
            "chip_seq": DataModality.CHIP_SEQ,
            "atac_seq": DataModality.ATAC_SEQ,
            "bisulfite_seq": DataModality.BISULFITE_SEQ,
            "single_cell_rna": DataModality.SINGLE_CELL_RNA,
            "single_cell_atac": DataModality.SINGLE_CELL_ATAC,
            "metagenomics": DataModality.METAGENOMICS,
            "metatranscriptomics": DataModality.METATRANSCRIPTOMICS,
        }

        return modality_map.get(modality_str.lower(), DataModality.UNKNOWN)

    def refine_with_context(
        self,
        parsed_request: ParsedRequest,
        additional_info: Dict[str, Any],
    ) -> ParsedRequest:
        """
        Refine a parsed request with additional information.

        Args:
            parsed_request: Previously parsed request
            additional_info: Additional information to incorporate

        Returns:
            Updated ParsedRequest
        """
        # Build a refinement prompt
        refinement_query = f"""
        Original query: {parsed_request.original_query}
        Current parsing: {parsed_request.model_dump_json(indent=2)}
        Additional information: {json.dumps(additional_info, indent=2)}

        Please update the parsed request based on the additional information.
        """

        # Re-parse with context
        return self.parse_request(refinement_query, context=additional_info)
