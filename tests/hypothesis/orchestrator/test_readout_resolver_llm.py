# tests/hypothesis/orchestrator/test_readout_resolver_llm.py
from quration.hypothesis.orchestrator.dataset_search import DatasetCandidate
from quration.hypothesis.orchestrator.evaluation_plan import ReadoutSpec
from quration.hypothesis.orchestrator.readout_resolver import RealReadoutResolver

IDEAL = ReadoutSpec(claimed_entity="MDM2", modality="transcript", ideal_assay_class="RNA-seq")
A = DatasetCandidate(source="geo", accession="GSE_A", title="rna-seq A", assay="RNA-Seq")
B = DatasetCandidate(source="geo", accession="GSE_B", title="rna-seq B", assay="RNA-Seq")


class PickSecond:
    def create_message(self, messages, model, system=None, temperature=1.0, **kw):
        return '{"choice": 1}'


class Boom:
    def create_message(self, *a, **k):
        raise RuntimeError("llm down")


def test_llm_pick_overrides_when_valid():
    res = RealReadoutResolver(provider=PickSecond(), model="sonnet").resolve(IDEAL, [A, B])
    assert res.dataset.accession == "GSE_B"
    assert res.resolver_provenance.get("model") == "sonnet"


def test_llm_failure_degrades_to_deterministic():
    res = RealReadoutResolver(provider=Boom(), model="sonnet").resolve(IDEAL, [A, B])
    assert res.dataset.accession == "GSE_A"        # deterministic top rank survives
    assert res.directness == "direct"
