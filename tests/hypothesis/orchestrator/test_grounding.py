"""Tests for on-demand ontology grounding of graph nodes."""

import pytest

from quration.data_sources.uniprot import ProteinInfo
from quration.hypothesis.graph import Node, NodeType
from quration.hypothesis.orchestrator.edge_chat import SetGrounding
from quration.hypothesis.orchestrator.grounding import (
    DemoGroundingService,
    FallbackGroundingService,
    GroundingProposal,
    OntologyGroundingService,
)
from quration.models.metadata import OntologyTerm


class FakeMapper:
    """Stand-in for OntologyMapper returning canned terms keyed by ontology."""

    def __init__(self, by_ontology=None, disease=None, cell_type=None, tissue=None):
        self._by_ontology = by_ontology or {}
        self._disease = disease
        self._cell_type = cell_type
        self._tissue = tissue

    def search_term(self, query, ontologies=None, exact=False, limit=5):
        key = (ontologies or [None])[0]
        term = self._by_ontology.get(key)
        return [term] if term else []

    def map_disease(self, text):
        return self._disease

    def map_cell_type(self, text):
        return self._cell_type

    def map_tissue(self, text):
        return self._tissue


class FakeUniProt:
    def __init__(self, hits=None, responder=None):
        self._hits = hits or []
        self._responder = responder
        self.queries = []

    def search(self, query, organism=None, limit=10):
        self.queries.append(query)
        return self._responder(query) if self._responder else self._hits


def _svc(mapper=None, uniprot=None):
    return OntologyGroundingService(mapper=mapper or FakeMapper(), uniprot=uniprot or FakeUniProt())


def test_grounds_target_to_uniprot():
    svc = _svc(uniprot=FakeUniProt([ProteinInfo(uniprot_id="P00533", protein_name="EGFR")]))
    node = Node(id="n", type=NodeType.TARGET, label="EGFR")
    proposal = svc.ground(node)
    assert proposal.found
    edit = proposal.proposed_edit
    assert edit.op == "set_grounding" and edit.node_id == "n"
    assert edit.ontology == "UniProt" and edit.term_id == "P00533"


def test_grounds_disease_to_mondo():
    term = OntologyTerm(term="heart failure", ontology_id="MONDO:0005252", ontology_name="mondo")
    svc = _svc(mapper=FakeMapper(disease=term))
    proposal = svc.ground(Node(id="d", type=NodeType.DISEASE, label="heart failure"))
    assert proposal.found
    assert proposal.proposed_edit.ontology == "MONDO"
    assert proposal.proposed_edit.term_id == "MONDO:0005252"


def test_grounds_target_prefers_reviewed_canonical_entry():
    # The first attempt is gene_exact + reviewed (Swiss-Prot canonical, e.g. P00533),
    # not whatever generic/unreviewed entry ranks first.
    up = FakeUniProt(responder=lambda q: (
        [ProteinInfo(uniprot_id="P00533", protein_name="EGFR")]
        if "gene_exact:EGFR" in q and "reviewed:true" in q else []))
    svc = _svc(uniprot=up)
    proposal = svc.ground(Node(id="n", type=NodeType.TARGET, label="EGFR"))
    assert proposal.found and proposal.proposed_edit.term_id == "P00533"
    assert "reviewed:true" in up.queries[0]


def test_grounds_target_falls_back_to_plain_query():
    # When no reviewed gene match exists, the plain-label query is the last resort.
    up = FakeUniProt(responder=lambda q: (
        [ProteinInfo(uniprot_id="Q1")] if ("gene_exact" not in q and "reviewed" not in q) else []))
    proposal = _svc(uniprot=up).ground(Node(id="n", type=NodeType.TARGET, label="some protein"))
    assert proposal.found and proposal.proposed_edit.term_id == "Q1"
    assert len(up.queries) == 3  # all three cascade steps fired
    assert "reviewed:true" in up.queries[1]  # middle step: plain label + reviewed


def test_normalizes_ols_short_form_to_curie():
    term = OntologyTerm(term="x", ontology_id="GO_0046427", ontology_name="go")
    svc = _svc(mapper=FakeMapper(by_ontology={"go": term}))
    edit = svc.ground(Node(id="p", type=NodeType.PATHWAY, label="x")).proposed_edit
    assert edit.term_id == "GO:0046427" and edit.ontology == "GO"


def test_grounds_pathway_to_go():
    term = OntologyTerm(term="JAK-STAT cascade", ontology_id="GO:0007259", ontology_name="go")
    svc = _svc(mapper=FakeMapper(by_ontology={"go": term}))
    proposal = svc.ground(Node(id="p", type=NodeType.PATHWAY, label="JAK/STAT3 signaling"))
    assert proposal.found
    assert proposal.proposed_edit.term_id == "GO:0007259"
    assert proposal.proposed_edit.ontology == "GO"


def test_no_match_returns_not_found_with_no_edit():
    proposal = _svc().ground(Node(id="x", type=NodeType.PATHWAY, label="nonsense"))
    assert proposal.found is False
    assert proposal.proposed_edit is None
    assert proposal.summary  # a human-readable "no match" message


def test_other_type_is_not_grounded():
    # OTHER nodes have no canonical ontology; don't even attempt a lookup.
    proposal = _svc().ground(Node(id="o", type=NodeType.OTHER, label="something"))
    assert proposal.found is False
    assert proposal.proposed_edit is None


def test_demo_grounding_is_deterministic_and_offline():
    # The demo service grounds a known label without any network client.
    svc = DemoGroundingService()
    proposal = svc.ground(Node(id="n", type=NodeType.TARGET, label="EGFR"))
    assert proposal.found
    assert proposal.proposed_edit.op == "set_grounding"


# --- FallbackGroundingService: chain a precise backend with a public fallback ---

class _StubGrounder:
    """A grounding backend that returns a canned proposal (or raises)."""

    def __init__(self, proposal=None, raises=False):
        self._proposal = proposal
        self._raises = raises
        self.calls = 0

    def ground(self, node):
        self.calls += 1
        if self._raises:
            raise RuntimeError("backend boom")
        return self._proposal


def _hit(term="GO:0001"):
    return GroundingProposal(
        found=True, summary="hit",
        proposed_edit=SetGrounding(node_id="n", ontology="GO", term_id=term, label="x"),
    )


_MISS = GroundingProposal(found=False, summary="no match")
_NODE = Node(id="n", type=NodeType.PATHWAY, label="some pathway")


def test_fallback_returns_first_hit_without_calling_later_backends():
    primary, secondary = _StubGrounder(_hit("PRIMARY")), _StubGrounder(_hit("SECONDARY"))
    p = FallbackGroundingService([primary, secondary]).ground(_NODE)
    assert p.found and p.proposed_edit.term_id == "PRIMARY"
    assert secondary.calls == 0  # short-circuits on first hit


def test_fallback_falls_through_to_secondary_on_miss():
    primary, secondary = _StubGrounder(_MISS), _StubGrounder(_hit("SECONDARY"))
    p = FallbackGroundingService([primary, secondary]).ground(_NODE)
    assert p.found and p.proposed_edit.term_id == "SECONDARY"
    assert primary.calls == 1 and secondary.calls == 1


def test_fallback_all_miss_returns_not_found():
    p = FallbackGroundingService([_StubGrounder(_MISS), _StubGrounder(_MISS)]).ground(_NODE)
    assert not p.found


def test_fallback_skips_a_raising_backend():
    boom, good = _StubGrounder(raises=True), _StubGrounder(_hit("RECOVERED"))
    p = FallbackGroundingService([boom, good]).ground(_NODE)
    assert p.found and p.proposed_edit.term_id == "RECOVERED"  # raise didn't propagate


# --- phospho-readout grounding (pAKT -> AKT, not a clinical ontology) ----------

def test_protein_base_detects_phospho_readouts():
    from quration.hypothesis.orchestrator.labels import protein_base

    assert protein_base("pAKT") == "AKT"
    assert protein_base("phospho-AKT") == "AKT"
    assert protein_base("pERK1/2") == "ERK1/2"
    assert protein_base("AKT") is None      # not a readout
    assert protein_base("PI3K") is None     # uppercase P, not phospho
    assert protein_base("p53") is None      # digit after p (it's TP53)
    assert protein_base("pH") is None       # 1-char base


def test_phospho_readout_grounds_to_protein_family_state():
    # pAKT is typed 'phenotype' but is a pan-isoform phospho readout -> ground to the
    # AKT FAMILY in a phospho state (AKT1/2/3), isoform deferred, not a single protein.
    fam = [
        ProteinInfo(uniprot_id="P31749", protein_name="AKT1", gene_names=["AKT1", "PKB"]),
        ProteinInfo(uniprot_id="P31751", protein_name="AKT2", gene_names=["AKT2"]),
        ProteinInfo(uniprot_id="Q9Y243", protein_name="AKT3", gene_names=["AKT3"]),
        ProteinInfo(uniprot_id="Q14164", protein_name="IKK epsilon", gene_names=["IKBKE"]),  # noise
        ProteinInfo(uniprot_id="Q9NWT8", protein_name="AKT-interacting protein",
                    gene_names=["AKTIP", "FTS"]),  # look-alike (starts with AKT), NOT an isoform
    ]
    svc = _svc(uniprot=FakeUniProt(fam))
    p = svc.ground(Node(id="n", type=NodeType.PHENOTYPE,
                        label="pAKT (phospho-AKT; S473/T308)"))
    assert p.found
    edit = p.proposed_edit
    assert edit.op == "set_protein_state_grounding" and edit.node_id == "n"
    assert {m.term_id for m in edit.members} == {"P31749", "P31751", "Q9Y243"}  # IKBKE + AKTIP excluded
    assert all(m.ontology == "UniProt" for m in edit.members)
    assert sorted(edit.residues) == ["S473", "T308"]
    assert edit.resolved_to is None
    assert "AKT" in edit.family_label and "phospho" in edit.family_label


def test_phospho_single_family_member_still_grounds():
    # A base with exactly one family member yields a one-member state (not an error).
    svc = _svc(uniprot=FakeUniProt([
        ProteinInfo(uniprot_id="P31749", protein_name="AKT1", gene_names=["AKT1"])]))
    p = svc.ground(Node(id="n", type=NodeType.PHENOTYPE, label="pAKT"))
    assert p.found and p.proposed_edit.op == "set_protein_state_grounding"
    assert [m.term_id for m in p.proposed_edit.members] == ["P31749"]
    assert p.proposed_edit.residues == []  # no sites stated in "pAKT"


def test_phospho_rejects_gene_mismatch():
    # An unrelated full-text hit (gene IKBKE) must NOT seed a family for base 'AKT'.
    ikbke = ProteinInfo(uniprot_id="Q14164", protein_name="IKK epsilon",
                        gene_names=["IKBKE", "IKKE"])
    svc = _svc(uniprot=FakeUniProt([ikbke]))  # mapper canned-empty -> no HPO term either
    p = svc.ground(Node(id="n", type=NodeType.PHENOTYPE, label="pAKT"))
    assert not p.found  # honest empty, never the wrong protein/family


def test_phospho_residues_extracts_stated_sites_in_order():
    from quration.hypothesis.orchestrator.labels import phospho_residues

    assert phospho_residues("pAKT (phospho-AKT; S473/T308)") == ["S473", "T308"]
    assert phospho_residues("pERK1/2 (T202/Y204)") == ["T202", "Y204"]
    assert phospho_residues("phospho-AKT") == []   # no explicit sites
    assert phospho_residues("pAKT") == []
    assert phospho_residues("") == []
