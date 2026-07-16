# tests/hypothesis/orchestrator/test_readout_resolver.py
from quration.hypothesis.orchestrator.dataset_search import DatasetCandidate
from quration.hypothesis.orchestrator.evaluation_plan import ReadoutSpec
from quration.hypothesis.orchestrator.readout_resolver import (
    DemoReadoutResolver, RealReadoutResolver, ResolveOutcome, directness_for,
)

PHOSPHO = ReadoutSpec(claimed_entity="pAKT", modality="phospho", ideal_assay_class="phosphoproteomics")

GEO = DatasetCandidate(source="geo", accession="GSE1", title="RNA-seq", assay="RNA-Seq")
PXD = DatasetCandidate(source="pride", accession="PXD1", title="phosphoproteomics", assay="phosphoproteomics")


def test_directness_direct_when_modalities_match():
    assert directness_for("transcript", GEO) == "direct"
    assert directness_for("phospho", PXD) == "direct"


def test_directness_proxy_modality_for_phospho_claim_on_rnaseq():
    assert directness_for("phospho", GEO) == "proxy_modality"


def test_real_resolver_prefers_direct_pride_for_phospho():
    res = RealReadoutResolver(provider=None).resolve(PHOSPHO, [GEO, PXD])
    assert isinstance(res, ResolveOutcome)
    assert res.dataset.accession == "PXD1"        # the DIRECT phospho dataset wins
    assert res.directness == "direct"
    assert GEO.accession in [c.accession for c in res.alternatives]


def test_real_resolver_falls_back_to_proxy_and_labels_it():
    res = RealReadoutResolver(provider=None).resolve(PHOSPHO, [GEO])  # only a proxy exists
    assert res.dataset.accession == "GSE1"
    assert res.directness == "proxy_modality"
    assert res.proxy_rationale != ""


def test_demo_resolver_is_the_canned_pakt_case():
    res = DemoReadoutResolver().resolve(PHOSPHO, [])
    assert res.resolved_readout is not None
    assert res.directness == "proxy_modality"
    assert res.dataset.accession == "GSE-DEMO"
    assert res.resolver_provenance["is_live"] is False
