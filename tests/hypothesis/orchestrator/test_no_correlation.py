"""The hardcoded Spearman correlation executor is gone (Task 10).

An approved edge is grounded against the methods graph (INCONCLUSIVE-only) or is
honestly "execution pending"; no edge runs a correlation. These guards keep the
deleted module/runners from silently coming back.
"""
import importlib

import pytest


def test_correlation_module_is_deleted():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("quration.hypothesis.orchestrator.correlation")


def test_real_pipeline_has_no_correlation_runner():
    import quration.hypothesis.orchestrator.real_pipeline as rp

    assert not hasattr(rp, "RealPipelineRunner")
    assert not hasattr(rp, "DispatchRunner")
