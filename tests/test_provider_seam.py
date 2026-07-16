"""Tests for the methods-graph provider injection seam.

quration consumes any duck-typed provider exposing ``get_methods() -> list[dict]``
(the shape emitted by methods_graph's KuzuMethodsGraphProvider) without importing
methods_graph. When a provider is injected the registry is populated from it,
replacing the hardcoded defaults; when absent, the defaults are used.
"""

import pytest

from quration.broker.method_registry import MethodRegistry, analysis_method_from_dict
from quration.broker.method_broker import MethodBroker
from quration.broker.models import DataModality, MethodCategory, ParsedRequest
from quration.config import get_config


# A method dict in exactly the shape methods_graph.provider emits for "salmon".
SALMON_DICT = {
    "id": "m:salmon",
    "name": "salmon",
    "category": "rna_seq",
    "description": "quant",
    "implementation_type": "nextflow",
    "version": "1.10.0",
    "repository_url": None,
    "tags": ["Read summarisation", "RNA-Seq"],
    "inputs": [],
    "outputs": [],
    "supported_modalities": ["rna_seq"],
    "quality_metrics": {
        "reproducibility_score": 0.8,
        "code_availability": True,
        "documentation_quality": 0.7,
        "peer_reviewed": False,
        "citation_count": 0,
    },
    "compute_requirements": {"container_image": "quay.io/biocontainers/salmon:1.10.0"},
    "status": "active",
    "publications": [],
}


class FakeProvider:
    """Duck-types methods_graph's provider: just get_methods()."""

    def __init__(self, methods):
        self._methods = methods

    def get_methods(self):
        return self._methods


# --- analysis_method_from_dict -------------------------------------------------

def test_from_dict_builds_complete_method():
    method = analysis_method_from_dict(SALMON_DICT)
    assert method.id == "m:salmon"
    assert method.category == MethodCategory.RNA_SEQ
    assert method.supported_modalities == [DataModality.RNA_SEQ]
    assert method.quality_metrics.reproducibility_score == 0.8


def test_from_dict_fills_defaults_for_partial_dict():
    """quration owns its types and tolerates a partial provider dict."""
    method = analysis_method_from_dict(
        {"id": "x", "name": "x", "description": "d"}
    )
    assert method.category == MethodCategory.CUSTOM
    assert method.supported_modalities == [DataModality.UNKNOWN]
    assert method.inputs == []
    assert method.outputs == []
    assert method.implementation_type == "tool"
    # quality_metrics is required by AnalysisMethod — a neutral default is supplied
    assert 0.0 <= method.quality_metrics.reproducibility_score <= 1.0


# --- MethodRegistry(provider=...) ---------------------------------------------

def test_registry_loads_methods_from_provider():
    registry = MethodRegistry(provider=FakeProvider([SALMON_DICT]))
    assert registry.get_method("m:salmon") is not None
    # provider replaces the hardcoded defaults
    assert registry.get_method("gatk-germline-variant-calling") is None
    assert len(registry.list_methods()) == 1


def test_registry_without_provider_uses_defaults():
    registry = MethodRegistry()
    assert registry.get_method("gatk-germline-variant-calling") is not None
    assert len(registry.list_methods()) >= 5


# --- MethodBroker(method_provider=...) ----------------------------------------

def test_broker_uses_injected_provider():
    broker = MethodBroker(get_config(), method_provider=FakeProvider([SALMON_DICT]))
    ids = {m.id for m in broker.list_all_methods()}
    assert ids == {"m:salmon"}


def test_injected_method_is_matchable():
    broker = MethodBroker(get_config(), method_provider=FakeProvider([SALMON_DICT]))
    parsed = ParsedRequest(
        original_query="rna-seq quant with salmon",
        data_modality=DataModality.RNA_SEQ,
        analysis_type="quantification",
        keywords=["salmon", "quant"],
        confidence=1.0,
    )
    matches = broker.matcher.find_matches(parsed, max_results=5, min_score=0.0)
    assert any(m.method.id == "m:salmon" for m in matches)


def test_broker_env_var_set_but_package_absent_falls_back(monkeypatch):
    """If QURATION_METHODS_GRAPH_DB points somewhere but methods_graph can't be
    imported, the broker must fall back to the hardcoded registry, not crash."""
    monkeypatch.setenv("QURATION_METHODS_GRAPH_DB", "/nonexistent/methods.kuzu")
    broker = MethodBroker(get_config())
    assert broker.get_method("gatk-germline-variant-calling") is not None
