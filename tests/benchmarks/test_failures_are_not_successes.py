"""A benchmark must not report a failure as a success.

Running `python -m quration.benchmarks.cli --published` with no API key printed:

    Tasks:               6
    Successful:          6
    Success Rate:        100.0%
    Accuracy:            0.000

in 0.1 seconds. Every one of those six tasks had failed with
"Could not resolve authentication method". A 100% success rate beside an
accuracy of 0.000 is the shape of number most likely to be quoted, and it was
wrong in the direction that flatters.

Three layers each dropped the failure, and fixing any one alone leaves it
hidden:

  1. `claude_integration` and `service` both catch every exception and return a
     well-formed `InterpretationResult` whose summary begins "Error during
     interpretation:". Both passed the cause as `metadata={"error": ...}` — a
     field `InterpretationResult` does not declare, so pydantic silently
     dropped it and the reason survived only as prose inside `summary`.
  2. `_run_interpretation` rebuilds a fresh result from `raw_result`'s parts, so
     even a propagated error vanished at the copy.
  3. Every benchmark task hardcoded `success=True`, because nothing had raised.

The scorer then ran happily over an empty claim list and produced a number.
"""

from __future__ import annotations

from quration.interpretation.models import (
    InterpretationResult,
    InterpretationType,
    TokenUsage,
)


def result(**kw) -> InterpretationResult:
    base = dict(
        interpretation_type=InterpretationType.DEG_ANALYSIS,
        summary="ok",
        token_usage=TokenUsage(),
        model_used="m",
        processing_time_ms=1.0,
        confidence_score=0.0,
    )
    base.update(kw)
    return InterpretationResult(**base)


class TestTheFailureSignalIsMachineReadable:
    def test_a_clean_result_has_not_failed(self):
        assert result().failed is False
        assert result().error is None

    def test_an_error_result_reports_failed(self):
        assert result(error="no auth").failed is True

    def test_the_cause_survives(self):
        """It used to be passed as `metadata`, which the model does not declare,
        so pydantic dropped it and left only prose in `summary`."""
        assert result(error="Could not resolve authentication method").error == (
            "Could not resolve authentication method"
        )

    def test_metadata_is_still_not_a_field(self):
        """Guards the root cause. If `metadata` is ever added, the two `except`
        blocks that pass it would start working by accident and this file's
        reason for existing would quietly change."""
        assert "metadata" not in InterpretationResult.model_fields
        assert "error" in InterpretationResult.model_fields


class TestATaskReportsTheFailure:
    """The layer that produced the misleading number."""

    def _run_task_against(self, interpretation):
        import asyncio

        from quration.benchmarks.tasks.published_tasks import get_published_deg_tasks

        class _Service:
            async def interpret_deg_results(self, **_kw):
                return interpretation

        # A real bundled task, not a constructed one: these are the six that
        # `--published` runs, and they are the ones that reported 100% success.
        task = get_published_deg_tasks()[0]
        return asyncio.run(task.run(_Service()))

    def test_a_failed_interpretation_is_not_a_successful_task(self):
        outcome = self._run_task_against(
            result(summary="Error during interpretation: no auth", error="no auth")
        )
        assert outcome.success is False, (
            "a task whose interpretation failed reported success — this is what "
            "printed a 100% success rate over six authentication errors"
        )
        assert outcome.error == "no auth"

    def test_a_real_interpretation_is_still_a_success(self):
        """The fix must not make every task fail."""
        outcome = self._run_task_against(result(summary="EGFR is upregulated"))
        assert outcome.success is True
        assert outcome.error is None


class TestTheErrorSurvivesTheServiceRebuild:
    def test_run_interpretation_carries_the_error_forward(self):
        """`_run_interpretation` builds a NEW result from `raw_result`'s parts.
        Before the fix the error arrived and was dropped at that copy, so
        `summary` said "Error during interpretation" while `failed` was False."""
        import inspect

        from quration.interpretation import service as service_module

        source = inspect.getsource(service_module._run_interpretation) if hasattr(
            service_module, "_run_interpretation"
        ) else inspect.getsource(service_module.InterpretationService._run_interpretation)
        assert "error=raw_result.error" in source, (
            "the rebuilt result no longer carries the upstream error forward"
        )
