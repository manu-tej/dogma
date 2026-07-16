"""Unit tests for BrokerMethodSelector.

The structural happy-path uses a REAL MethodBroker backed by a fake methods
provider (the duck-typed get_methods() seam). The fallback/no-match branches use
a tiny fake broker so scores can be controlled precisely.
"""
from types import SimpleNamespace

from quration.broker.method_broker import MethodBroker
from quration.broker.models import DataModality
from quration.config import get_config
from quration.hypothesis.graph import CausalGraph, Edge, Node, NodeType
from quration.hypothesis.orchestrator.checkpoint import ProposedTest
from quration.hypothesis.orchestrator.method_selection import (
    BrokerMethodSelector,
    _modality_for_accession,
)


# --- fixtures -----------------------------------------------------------------

class _FakeProvider:
    """Duck-types methods_graph's provider: just get_methods()."""

    def __init__(self, methods):
        self._methods = methods

    def get_methods(self):
        return self._methods


def _rna_and_dna_broker():
    methods = [
        {"id": "deseq2", "name": "DESeq2", "category": "differential_expression",
         "description": "differential expression of RNA-seq counts",
         "supported_modalities": ["rna_seq"], "tags": ["expression", "rna-seq"]},
        {"id": "bcftools", "name": "bcftools", "category": "variant_calling",
         "description": "variant calling from DNA", "supported_modalities": ["dna_seq"],
         "tags": ["variant", "dna"]},
    ]
    return MethodBroker(get_config(), method_provider=_FakeProvider(methods))


def _gene_gene_graph():
    g = CausalGraph(id="g", query="does EGFR drive KRAS?")
    g.add_node(Node(id="egfr", type=NodeType.TARGET, label="EGFR"))
    g.add_node(Node(id="kras", type=NodeType.TARGET, label="KRAS"))
    g.add_edge(Edge(id="e1", source_id="egfr", target_id="kras",
                    relation="up-regulates", pending=True))
    return g


def _proposed(**kw):
    base = dict(edge_id="e1", gap="g", pipeline="nf-core/rnaseq",
                data_accession="GSE1", source_symbol="EGFR", target_symbol="KRAS",
                relation="up-regulates")
    base.update(kw)
    return ProposedTest(**base)


class _Match:
    def __init__(self, method_id, name, score):
        self.method = SimpleNamespace(id=method_id, name=name)
        self.score = score


class _FakeMatcher:
    """Returns canned matches based on a scoring function of the parsed request."""

    def __init__(self, score_fn):
        self._score_fn = score_fn

    def find_matches(self, parsed_request, max_results=5, min_score=0.0):
        m = self._score_fn(parsed_request)
        return [m] if m is not None else []


class _FakeBroker:
    def __init__(self, score_fn):
        self.matcher = _FakeMatcher(score_fn)


# --- tests --------------------------------------------------------------------

def test_modality_for_accession():
    assert _modality_for_accession("GSE12345") == DataModality.RNA_SEQ
    assert _modality_for_accession("PXD0001") == DataModality.UNKNOWN
    assert _modality_for_accession("") == DataModality.UNKNOWN


def test_structural_picks_rna_method_for_gene_gene_edge():
    selector = BrokerMethodSelector(_rna_and_dna_broker())
    choice = selector.select(_proposed(), _gene_gene_graph())
    assert choice is not None
    assert choice.method_id == "deseq2"
    assert choice.source == "structural"
    assert choice.score > 0


def test_no_match_returns_none():
    selector = BrokerMethodSelector(_FakeBroker(lambda req: None))
    assert selector.select(_proposed(), _gene_gene_graph()) is None


def test_fallback_used_when_structural_below_threshold():
    # Structural keywords score low; the enriched query (contains "DRIVER") scores high.
    def score_fn(req):
        text = (req.original_query or "") + " " + " ".join(req.keywords)
        if "DRIVER" in text:
            return _Match("enriched-method", "Enriched", 0.9)
        return _Match("weak-method", "Weak", 0.2)

    selector = BrokerMethodSelector(
        _FakeBroker(score_fn),
        intent_author=lambda proposed, graph: "DRIVER differential expression",
        threshold=0.4,
    )
    choice = selector.select(_proposed(), _gene_gene_graph())
    assert choice is not None
    assert choice.method_id == "enriched-method"
    assert choice.source == "fallback"


def test_fallback_not_used_when_structural_confident():
    def score_fn(req):
        text = (req.original_query or "") + " " + " ".join(req.keywords)
        return _Match("enriched", "E", 0.99) if "DRIVER" in text else _Match("strong", "S", 0.8)

    calls = []
    selector = BrokerMethodSelector(
        _FakeBroker(score_fn),
        intent_author=lambda p, g: calls.append(1) or "DRIVER",
        threshold=0.4,
    )
    choice = selector.select(_proposed(), _gene_gene_graph())
    assert choice.method_id == "strong"
    assert choice.source == "structural"
    assert calls == []  # author never invoked when structural is confident


# --- graph grounding (slice 1) ------------------------------------------------

class _RagFakeProvider(_FakeProvider):
    """get_methods() + a RAG surface that records the keywords it was given."""

    def __init__(self, methods, text="# grounding", raises=False):
        super().__init__(methods)
        self._text, self._raises = text, raises
        self.calls = []

    def retrieve_context_for_keywords(self, keywords, *, k_hops=1):
        self.calls.append(list(keywords))
        if self._raises:
            raise RuntimeError("boom")
        return self._text


_RNA_DNA_METHODS = [
    {"id": "deseq2", "name": "DESeq2", "category": "differential_expression",
     "description": "differential expression of RNA-seq counts",
     "supported_modalities": ["rna_seq"], "tags": ["expression", "rna-seq"]},
    {"id": "bcftools", "name": "bcftools", "category": "variant_calling",
     "description": "variant calling from DNA", "supported_modalities": ["dna_seq"],
     "tags": ["variant", "dna"]},
]


def test_select_attaches_grounding_seeded_by_method_name_only():
    provider = _RagFakeProvider(_RNA_DNA_METHODS, text="# DESeq2 neighborhood")
    broker = MethodBroker(get_config(), method_provider=provider)
    sel = BrokerMethodSelector(broker)
    choice = sel.select(_proposed(), _gene_gene_graph())
    assert choice is not None
    assert choice.grounding == "# DESeq2 neighborhood"
    # seeded by the chosen method name ONLY — gene symbols are not seeded
    # (no gene layer in the graph; they match nothing and would imply false specificity)
    assert provider.calls == [[choice.name]]


def test_select_pick_is_identical_without_provider():
    """Grounding is purely additive: the pick must not change vs no provider."""
    graph, proposed = _gene_gene_graph(), _proposed()
    with_p = BrokerMethodSelector(
        MethodBroker(get_config(), method_provider=_RagFakeProvider(_RNA_DNA_METHODS))
    ).select(proposed, graph)
    without_p = BrokerMethodSelector(
        MethodBroker(get_config(), method_provider=_FakeProvider(_RNA_DNA_METHODS))
    ).select(proposed, graph)
    assert with_p is not None and without_p is not None
    assert (with_p.method_id, with_p.score, with_p.source) == \
           (without_p.method_id, without_p.score, without_p.source)
    assert without_p.grounding is None  # no RAG surface → no grounding


def test_select_survives_provider_error():
    provider = _RagFakeProvider(_RNA_DNA_METHODS, raises=True)
    sel = BrokerMethodSelector(MethodBroker(get_config(), method_provider=provider))
    choice = sel.select(_proposed(), _gene_gene_graph())
    assert choice is not None
    assert choice.grounding is None
