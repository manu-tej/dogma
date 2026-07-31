"""An edge must not claim a provenance it does not have.

Two lies, both reproduced against a running server before these tests existed:

  1. Every demo-seeded edge reported `proposal_source: "llm"`. No model had run —
     the field defaulted to LLM and the fixtures never overrode it. 10 of the 15
     `Edge(...)` construction sites in `src/` omit the field, so all of them were
     asserting a model had proposed the relation.

  2. The phenotype node "drug resistance" was grounded to
     `UniProt:RESIST`. That is not a valid accession in any namespace, and a
     phenotype has no UniProt entry to point at. The graph therefore reported an
     entity as ontology-grounded on the strength of an identifier that cannot
     exist.

Both matter more than their size suggests: the epistemics layer is the one part of
this system whose whole purpose is to be trusted about provenance.
"""

import re

import pytest

from quration.hypothesis.epistemics import ProposalSource
from quration.hypothesis.graph import Edge
from quration.hypothesis.orchestrator.demo import DemoSuggester

#: UniProt accession grammar, from the official regex.
UNIPROT_ACCESSION = re.compile(
    r"^[OPQ][0-9][A-Z0-9]{3}[0-9]$"
    r"|^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}$"
)


@pytest.fixture
def suggestion():
    return DemoSuggester().expand(seeds=["EGFR"], query="anything at all")


class TestProposalSourceTellsTheTruth:
    def test_demo_edges_are_labelled_demo_not_llm(self, suggestion):
        assert suggestion.edges, "the demo suggester returned no edges"
        for edge in suggestion.edges:
            assert edge.proposal_source == ProposalSource.DEMO, (
                f"edge {edge.id} reports {edge.proposal_source!r}; no model ran"
            )

    def test_no_demo_edge_claims_an_llm_proposed_it(self, suggestion):
        assert all(e.proposal_source != ProposalSource.LLM for e in suggestion.edges)

    def test_an_unspecified_proposal_source_does_not_claim_llm(self):
        """The default is what made the lie systemic. Unknown provenance must read
        as unknown, not as a model attribution."""
        edge = Edge(id="e", source_id="a", target_id="b", relation="drives")
        assert edge.proposal_source != ProposalSource.LLM
        assert edge.proposal_source == ProposalSource.SYSTEM

    def test_demo_is_a_distinct_source(self):
        assert ProposalSource.DEMO.value == "demo"
        assert ProposalSource.DEMO not in (ProposalSource.LLM, ProposalSource.SYSTEM)


class TestGroundingIsNotFabricated:
    def test_no_node_is_grounded_to_an_invalid_uniprot_accession(self, suggestion):
        for node in suggestion.nodes:
            grounding = node.grounding
            if grounding is None or getattr(grounding, "ontology", None) != "UniProt":
                continue
            assert UNIPROT_ACCESSION.match(grounding.term_id), (
                f"node {node.id} ({node.label}) is grounded to "
                f"UniProt:{grounding.term_id}, which is not a valid accession"
            )

    def test_the_phenotype_is_left_ungrounded(self, suggestion):
        """Honest absence. A phenotype has no UniProt entry, so the correct value
        is None — not a plausible-looking placeholder."""
        phenotypes = [n for n in suggestion.nodes if n.type.value == "phenotype"]
        assert phenotypes, "expected a phenotype in the demo sketch"
        for node in phenotypes:
            assert node.grounding is None

    def test_the_proteins_are_still_grounded(self, suggestion):
        """The fix must not throw away the grounding that was correct: EGFR and
        KRAS have real accessions and should keep them."""
        grounded = {
            n.label: n.grounding.term_id for n in suggestion.nodes if n.grounding
        }
        assert grounded.get("EGFR") == "P00533"
        assert grounded.get("KRAS") == "P01116"
