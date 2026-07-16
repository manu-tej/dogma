"""LLM-based experimental design parser for GEO datasets."""

import json
from typing import Any

from quration.config import get_config
from quration.llm import get_llm_provider


class ExperimentalDesignParser:
    """Parses raw experimental design text into structured format using LLM."""

    def __init__(self, api_key: str | None = None, provider: str | None = None):
        """Initialize the design parser.

        Args:
            api_key: API key for the LLM provider (uses config if not provided)
            provider: LLM provider name ("anthropic" or "openrouter", uses config if not provided)
        """
        config = get_config()

        # Determine provider
        self.provider_name = provider or config.llm.provider

        # Get provider-specific configuration
        if self.provider_name == "anthropic":
            provider_config = config.llm.anthropic
            self.model = provider_config.fast_model  # Use fast model for parsing
        elif self.provider_name == "openrouter":
            provider_config = config.llm.openrouter
            self.model = provider_config.fast_model  # Use fast model for parsing
        elif self.provider_name == "claude_subscription":
            provider_config = config.llm.claude_subscription
            self.model = provider_config.fast_model  # Use fast model for parsing
        else:
            raise ValueError(f"Unsupported provider: {self.provider_name}")

        # Get LLM provider instance. Extra kwargs are harmless for providers
        # that don't read them.
        self.llm = get_llm_provider(
            provider_name=self.provider_name,
            api_key=api_key or getattr(provider_config, "api_key", None),
            site_url=getattr(provider_config, "site_url", None),
            app_name=getattr(provider_config, "app_name", None),
            claude_executable=getattr(provider_config, "claude_executable", "claude"),
            force_subscription=getattr(provider_config, "force_subscription", True),
            timeout_seconds=getattr(provider_config, "timeout_seconds", 180),
        )

    def parse_design(self, raw_design_text: str) -> dict[str, Any]:
        """Parse experimental design text into structured format.

        Args:
            raw_design_text: Raw experimental design description

        Returns:
            Dictionary with structured design information:
            - conditions: List of experimental conditions with sample counts
            - design_type: Type of experimental design (case-control, time-series, etc.)
            - tech: Sequencing technology
            - notes: Summary of the design
            - is_partial: Whether information is incomplete
        """
        if not raw_design_text or not raw_design_text.strip():
            return {
                "conditions": None,
                "design_type": None,
                "tech": None,
                "notes": "No design information available",
                "is_partial": True,
            }

        prompt = self._build_prompt(raw_design_text)

        try:
            content = self.llm.create_message(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=1500,
            )

            # Extract JSON from response
            start_idx = content.find("{")
            end_idx = content.rfind("}") + 1

            if start_idx >= 0 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                design_data = json.loads(json_str)
                return design_data

        except Exception as e:
            print(f"Error parsing design with LLM: {e}")

        # Fallback to simple parsing
        return self._parse_fallback(raw_design_text)

    def _build_prompt(self, raw_text: str) -> str:
        """Build prompt for experimental design parsing."""
        prompt = f"""You are an expert in bioinformatics and experimental design analysis.

Parse the following experimental design text and extract structured information.

Raw Design Text:
\"\"\"
{raw_text}
\"\"\"

Extract and return a JSON object with the following structure:
{{
  "conditions": [
    {{"name": "condition name", "n": sample_count}},
    ...
  ],
  "design_type": "case-control | time-series | dose-response | multi-factor | other",
  "tech": "sequencing technology platform",
  "notes": "brief summary of the experimental design (1-2 sentences)",
  "is_partial": true/false
}}

Guidelines:
- conditions: List experimental groups/conditions with sample counts if mentioned
- design_type: Classify the overall experimental design
- tech: Extract sequencing platform (e.g., "Illumina HiSeq 2500", "NextSeq 500")
- notes: Provide a concise summary
- is_partial: Set to true if any major field is missing or uncertain

Return ONLY the JSON object, no other text.
"""
        return prompt

    def _parse_fallback(self, raw_text: str) -> dict[str, Any]:
        """Simple fallback parser when LLM fails."""
        # Basic tech detection
        tech = None
        tech_keywords = [
            "Illumina",
            "HiSeq",
            "NextSeq",
            "NovaSeq",
            "MiSeq",
            "Ion Torrent",
            "PacBio",
            "454",
        ]
        for keyword in tech_keywords:
            if keyword.lower() in raw_text.lower():
                tech = keyword
                break

        # Basic design type detection
        design_type = None
        if any(word in raw_text.lower() for word in ["control", "case", "treated", "untreated"]):
            design_type = "case-control"
        elif any(word in raw_text.lower() for word in ["time", "temporal", "series"]):
            design_type = "time-series"

        # Create simple notes
        notes = raw_text[:200] + ("..." if len(raw_text) > 200 else "")

        return {
            "conditions": None,
            "design_type": design_type,
            "tech": tech,
            "notes": notes,
            "is_partial": True,
        }


def parse_experimental_design_with_llm(raw_design_text: str) -> dict[str, Any]:
    """
    Use an LLM to convert raw experimental design text into a structured dict.

    This function matches the original spec signature.

    - Try to infer conditions list: group names and sample counts if mentioned.
    - Try to infer design_type (e.g., 'case-control', 'time-series').
    - Try to infer tech (e.g., 'Illumina HiSeq').
    - Always fill 'notes' with a short summary of the design.
    - Set is_partial=True if any major fields are missing/uncertain.

    Args:
        raw_design_text: Raw experimental design text from GEO

    Returns:
        Dictionary with structured design information:
        - conditions: List of dicts with 'name' and 'n' keys
        - design_type: str or None
        - tech: str or None
        - notes: str
        - is_partial: bool
    """
    parser = ExperimentalDesignParser()
    return parser.parse_design(raw_design_text)
