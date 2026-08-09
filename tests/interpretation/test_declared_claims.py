"""The interpreter declares its claims; regex over prose is the fallback.

Two benchmark runs bracketed the problem. Before the fragment fix, regex
extraction scored 'NANOG activate their' as a claim. After it, the same
extractor pulled ONE claim from a COVID report that plainly asserted all four
expected findings — accuracy 0.033 and recall 0.103 were measuring extractor
coverage, not interpretation quality. Parsing assertions back out of markdown
prose fails in whichever direction it isn't currently tuned for.

So the model now emits its claims as data: a fenced ```claims block, a JSON
array of {statement, type, confidence}, required by SYSTEM_OUTPUT_FORMAT and
therefore present in every template's system prompt. The service uses the
declared block when present and falls back to the extractor when absent — and
records which path ran in the typed `claim_source` field, because a silent
fallback would make every downstream number ambiguous about what it measures.

Boundary semantics that matter:

- An *empty* declared block is an honest "this report makes no claims" and is
  respected — it must NOT trigger the regex fallback, which would invent the
  claims the model deliberately declined to make.
- A *malformed* block is an instruction failure, not a statement: fall back.
"""

import pytest

from quration.interpretation.models import ClaimType, ConfidenceLevel
from quration.interpretation.parsers import extract_declared_claims

BLOCK = """## Analysis

ERBB2 shows elevated expression, consistent with the study.

```claims
[
  {"statement": "ERBB2 shows elevated expression in luminal tumours",
   "type": "from_data", "confidence": "high"},
  {"statement": "GRB7 co-amplifies with ERBB2 at 17q12",
   "type": "literature", "confidence": "medium"}
]
```
"""


class TestDeclaredClaimsAreParsed:
    def test_statements_come_through(self):
        claims = extract_declared_claims(BLOCK)
        assert [c.statement for c in claims] == [
            "ERBB2 shows elevated expression in luminal tumours",
            "GRB7 co-amplifies with ERBB2 at 17q12",
        ]

    def test_type_and_confidence_are_mapped(self):
        claims = extract_declared_claims(BLOCK)
        assert claims[0].claim_type == ClaimType.FROM_DATA
        assert claims[0].confidence == ConfidenceLevel.HIGH
        assert claims[1].claim_type == ClaimType.LITERATURE

    def test_unknown_type_defaults_to_inference_not_crash(self):
        text = '```claims\n[{"statement": "long enough statement here", "type": "wild-guess", "confidence": "very"}]\n```'
        claims = extract_declared_claims(text)
        assert claims[0].claim_type == ClaimType.INFERENCE
        assert claims[0].confidence == ConfidenceLevel.MEDIUM

    def test_the_last_block_wins(self):
        """A model that revises mid-report supersedes its earlier list."""
        text = BLOCK + '\n```claims\n[{"statement": "only this one stands"}]\n```'
        claims = extract_declared_claims(text)
        assert [c.statement for c in claims] == ["only this one stands"]

    def test_entries_without_a_statement_are_skipped(self):
        text = '```claims\n[{"type": "from_data"}, {"statement": "the real one"}]\n```'
        claims = extract_declared_claims(text)
        assert [c.statement for c in claims] == ["the real one"]


class TestAbsenceAndFailureFallBack:
    def test_no_block_returns_none(self):
        assert extract_declared_claims("Just prose. No block.") is None

    def test_malformed_json_returns_none(self):
        assert extract_declared_claims("```claims\n[{not json\n```") is None

    def test_a_non_list_payload_returns_none(self):
        assert extract_declared_claims('```claims\n{"statement": "x"}\n```') is None

    def test_all_entries_invalid_returns_none(self):
        assert extract_declared_claims('```claims\n[{"type": "x"}, "y"]\n```') is None

    def test_an_empty_block_is_an_honest_no_claims(self):
        """[] is a statement — "this report asserts nothing" — and must be
        respected, not overridden by regex inventing claims from the prose."""
        assert extract_declared_claims("```claims\n[]\n```") == []


class TestEveryTemplateDemandsTheBlock:
    def test_system_output_format_requires_it(self):
        from quration.interpretation.prompts import SYSTEM_OUTPUT_FORMAT

        assert "```claims" in SYSTEM_OUTPUT_FORMAT

    def test_each_template_system_prompt_carries_the_instruction(self):
        from quration.interpretation.prompts import get_template, list_templates

        for name in list_templates():
            template = get_template(name)
            filler = {v: "x" for v in template.required_variables}
            system, _ = template.render(**filler)
            assert "```claims" in system, name


class TestTheServicePrefersDeclaredClaims:
    @pytest.mark.asyncio
    async def test_declared_claims_are_used_and_the_source_recorded(self):
        from quration.interpretation.models import InterpretationType
        from quration.interpretation.service import InterpretationService

        service = InterpretationService.__new__(InterpretationService)
        # Use the real pipeline: only the caller is faked.
        self._wire(service, BLOCK)
        result = await service._run_interpretation(
            user_prompt="p",
            interpretation_type=InterpretationType.DEG_ANALYSIS,
            system_prompt="s",
        )
        assert [c.statement for c in result.claims] == [
            "ERBB2 shows elevated expression in luminal tumours",
            "GRB7 co-amplifies with ERBB2 at 17q12",
        ]
        assert result.claim_source == "declared"

    @pytest.mark.asyncio
    async def test_without_a_block_the_fallback_runs_and_is_recorded(self):
        from quration.interpretation.models import InterpretationType
        from quration.interpretation.service import InterpretationService

        service = InterpretationService.__new__(InterpretationService)
        self._wire(service, "TP53 is upregulated in treated samples versus control.")
        result = await service._run_interpretation(
            user_prompt="p",
            interpretation_type=InterpretationType.DEG_ANALYSIS,
            system_prompt="s",
        )
        assert result.claim_source == "extracted"
        assert result.claims  # the regex path still found the assertion

    def _wire(self, service, summary: str) -> None:
        """Fake only the caller; every parser/scorer stage stays real."""
        from unittest.mock import AsyncMock, MagicMock

        from quration.interpretation.models import (
            InterpretationResult,
            InterpretationType,
            TokenUsage,
        )
        from quration.interpretation.parsers import ClaimExtractor, ResponseParser
        from quration.interpretation.citations import CitationGenerator
        from quration.interpretation.confidence import (
            ConfidenceScorer,
            InterpretationValidator,
        )
        from uuid import uuid4

        raw = InterpretationResult(
            id=uuid4(),
            interpretation_type=InterpretationType.DEG_ANALYSIS,
            summary=summary,
            claims=[],
            tool_calls=[],
            confidence_score=0.0,
            token_usage=TokenUsage(),
            processing_time_ms=1.0,
            model_used="test",
        )
        service._claude_caller = MagicMock(interpret=AsyncMock(return_value=raw))
        service._parser = ResponseParser()
        service._claim_extractor = ClaimExtractor()
        service._citation_generator = CitationGenerator()
        service._scorer = ConfidenceScorer()
        service._validator = InterpretationValidator()
        service._model = "test"
        service._cache = None
