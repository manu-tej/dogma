"""
Tests for the Method Broker system.
"""

import pytest
from datetime import datetime

from quration.broker import (
    AnalysisMethod,
    MatchingEngine,
    MethodBroker,
    MethodCategory,
    MethodRegistry,
    MethodRequest,
    ProposalManager,
    DataModality,
)
from quration.broker.models import (
    MethodAssumption,
    MethodCaveat,
    MethodInputSpec,
    MethodOutputSpec,
    MethodProposal,
    MethodQualityMetrics,
)
from quration.config import QurationConfig


@pytest.fixture
def sample_method():
    """Create a sample analysis method for testing."""
    return AnalysisMethod(
        id="test-method",
        name="Test Analysis Method",
        category=MethodCategory.VARIANT_CALLING,
        description="A test method for variant calling",
        implementation_type="nextflow",
        version="1.0.0",
        repository_url="https://github.com/test/method",
        documentation_url="https://test.method.com/docs",
        inputs=[
            MethodInputSpec(
                name="reads",
                description="FASTQ files",
                data_type="FASTQ",
                required=True,
                multiple=True,
            )
        ],
        outputs=[
            MethodOutputSpec(
                name="vcf", description="Variant calls", data_type="VCF"
            )
        ],
        supported_modalities=[DataModality.DNA_SEQ],
        supported_organisms=["human", "mouse"],
        min_samples=1,
        assumptions=[
            MethodAssumption(
                description="High quality reads",
                category="data_quality",
                critical=True,
            )
        ],
        caveats=[
            MethodCaveat(
                description="May be slow for large genomes",
                severity="medium",
                workaround="Use parallel processing",
            )
        ],
        quality_metrics=MethodQualityMetrics(
            reproducibility_score=0.95,
            code_availability=True,
            documentation_quality=0.90,
            peer_reviewed=True,
            citation_count=100,
        ),
        compute_requirements={"cpu_cores": 8, "memory_gb": 32},
        tags=["variant-calling", "test"],
    )


@pytest.fixture
def registry(sample_method):
    """Create a method registry with a sample method."""
    reg = MethodRegistry()
    reg.add_method(sample_method)
    return reg


class TestMethodRegistry:
    """Tests for MethodRegistry class."""

    def test_add_method(self, registry, sample_method):
        """Test adding a method to registry."""
        assert sample_method.id in registry.methods
        assert registry.get_method(sample_method.id) == sample_method

    def test_list_methods(self, registry):
        """Test listing methods."""
        methods = registry.list_methods()
        assert len(methods) > 0

    def test_list_methods_by_category(self, registry):
        """Test filtering methods by category."""
        methods = registry.list_methods(category=MethodCategory.VARIANT_CALLING)
        assert all(m.category == MethodCategory.VARIANT_CALLING for m in methods)

    def test_list_methods_by_modality(self, registry):
        """Test filtering methods by modality."""
        methods = registry.list_methods(modality=DataModality.DNA_SEQ)
        assert all(DataModality.DNA_SEQ in m.supported_modalities for m in methods)

    def test_search_methods(self, registry):
        """Test searching methods by keyword."""
        results = registry.search_methods("variant")
        assert len(results) > 0

    def test_get_stats(self, registry):
        """Test getting registry statistics."""
        stats = registry.get_stats()
        assert "total_methods" in stats
        assert "by_category" in stats
        assert stats["total_methods"] > 0


class TestMatchingEngine:
    """Tests for MatchingEngine class."""

    def test_find_matches_variant_calling(self, registry):
        """Test finding matches for variant calling request."""
        from quration.broker.models import ParsedRequest

        engine = MatchingEngine(registry)

        parsed_request = ParsedRequest(
            original_query="I need to call variants from DNA sequencing",
            data_modality=DataModality.DNA_SEQ,
            analysis_type="variant calling",
            specific_tools=[],
            keywords=["variant", "calling"],
            confidence=0.9,
        )

        matches = engine.find_matches(parsed_request, max_results=5)
        assert len(matches) > 0
        assert all(m.score > 0 for m in matches)

    def test_find_matches_rna_seq(self, registry):
        """Test finding matches for RNA-seq request."""
        from quration.broker.models import ParsedRequest

        engine = MatchingEngine(registry)

        parsed_request = ParsedRequest(
            original_query="Differential expression analysis of RNA-seq data",
            data_modality=DataModality.RNA_SEQ,
            analysis_type="differential expression",
            specific_tools=[],
            keywords=["rnaseq", "differential", "expression"],
            confidence=0.9,
        )

        matches = engine.find_matches(parsed_request, max_results=5)
        # Should find DESeq2 method from default registry
        assert len(matches) > 0

    def test_match_score_range(self, registry):
        """Test that match scores are in valid range."""
        from quration.broker.models import ParsedRequest

        engine = MatchingEngine(registry)

        parsed_request = ParsedRequest(
            original_query="Some analysis",
            data_modality=DataModality.DNA_SEQ,
            analysis_type="test",
            specific_tools=[],
            keywords=[],
            confidence=0.5,
        )

        matches = engine.find_matches(parsed_request, max_results=10, min_score=0.0)

        for match in matches:
            assert 0.0 <= match.score <= 1.0
            assert 0.0 <= match.relevance_score <= 1.0
            assert 0.0 <= match.quality_score <= 1.0
            assert 0.0 <= match.compatibility_score <= 1.0


class TestProposalManager:
    """Tests for ProposalManager class."""

    def test_submit_proposal(self, tmp_path):
        """Test submitting a method proposal."""
        manager = ProposalManager(tmp_path / "proposals.json")

        proposal = MethodProposal(
            name="New Method",
            category=MethodCategory.RNA_SEQ,
            description="A new RNA-seq method",
            justification="We need this for our research",
            use_cases=["Analyze RNA-seq data"],
            proposed_by="test_user",
        )

        proposal_id = manager.submit_proposal(proposal)
        assert proposal_id is not None

        retrieved = manager.get_proposal(proposal_id)
        assert retrieved is not None
        assert retrieved.name == "New Method"

    def test_list_proposals(self, tmp_path):
        """Test listing proposals."""
        manager = ProposalManager(tmp_path / "proposals.json")

        proposal1 = MethodProposal(
            name="Method 1",
            category=MethodCategory.RNA_SEQ,
            description="Description 1",
            justification="Justification 1",
            use_cases=["Use case 1"],
            proposed_by="user1",
        )

        proposal2 = MethodProposal(
            name="Method 2",
            category=MethodCategory.VARIANT_CALLING,
            description="Description 2",
            justification="Justification 2",
            use_cases=["Use case 2"],
            proposed_by="user2",
        )

        manager.submit_proposal(proposal1)
        manager.submit_proposal(proposal2)

        all_proposals = manager.list_proposals()
        assert len(all_proposals) == 2

        user1_proposals = manager.list_proposals(proposed_by="user1")
        assert len(user1_proposals) == 1
        assert user1_proposals[0].proposed_by == "user1"

    def test_update_proposal_status(self, tmp_path):
        """Test updating proposal status."""
        manager = ProposalManager(tmp_path / "proposals.json")

        proposal = MethodProposal(
            name="Test Method",
            category=MethodCategory.RNA_SEQ,
            description="Test",
            justification="Test",
            use_cases=["Test"],
            proposed_by="test_user",
        )

        proposal_id = manager.submit_proposal(proposal)

        success = manager.update_proposal_status(
            proposal_id, "approved", "Looks good"
        )
        assert success

        updated = manager.get_proposal(proposal_id)
        assert updated.status == "approved"
        assert updated.review_notes == "Looks good"

    def test_get_proposal_stats(self, tmp_path):
        """Test getting proposal statistics."""
        manager = ProposalManager(tmp_path / "proposals.json")

        for i in range(3):
            proposal = MethodProposal(
                name=f"Method {i}",
                category=MethodCategory.RNA_SEQ,
                description=f"Description {i}",
                justification=f"Justification {i}",
                use_cases=[f"Use case {i}"],
                proposed_by=f"user{i}",
            )
            manager.submit_proposal(proposal)

        stats = manager.get_proposal_stats()
        assert stats["total_proposals"] == 3
        assert stats["by_status"]["pending"] == 3


class TestMethodBroker:
    """Tests for MethodBroker integration."""

    @pytest.mark.asyncio
    async def test_process_request_variant_calling(self):
        """Test processing a variant calling request."""
        # Note: This test requires LLM provider which may not be available
        # In a real test environment, you'd mock the LLM provider

        # For now, we'll skip this test
        pytest.skip("Requires LLM provider configuration")

    def test_get_method(self, registry):
        """Test getting a specific method."""
        from quration.config import get_config

        config = get_config()
        broker = MethodBroker(config)

        # Add a method
        method = registry.get_method("gatk-germline-variant-calling")
        if method:
            retrieved = broker.get_method("gatk-germline-variant-calling")
            assert retrieved is not None
            assert retrieved.id == "gatk-germline-variant-calling"

    def test_list_all_methods(self):
        """Test listing all methods."""
        from quration.config import get_config

        config = get_config()
        broker = MethodBroker(config)

        methods = broker.list_all_methods()
        assert len(methods) > 0

    def test_search_methods(self):
        """Test searching methods."""
        from quration.config import get_config

        config = get_config()
        broker = MethodBroker(config)

        results = broker.search_methods("variant")
        assert isinstance(results, list)

    def test_get_registry_stats(self):
        """Test getting registry statistics."""
        from quration.config import get_config

        config = get_config()
        broker = MethodBroker(config)

        stats = broker.get_registry_stats()
        assert "total_methods" in stats
        assert "by_category" in stats


def test_data_modality_enum():
    """Test DataModality enum values."""
    assert DataModality.DNA_SEQ.value == "dna_seq"
    assert DataModality.RNA_SEQ.value == "rna_seq"
    assert DataModality.CHIP_SEQ.value == "chip_seq"


def test_method_category_enum():
    """Test MethodCategory enum values."""
    assert MethodCategory.VARIANT_CALLING.value == "variant_calling"
    assert MethodCategory.RNA_SEQ.value == "rna_seq"
    assert MethodCategory.DIFFERENTIAL_EXPRESSION.value == "differential_expression"
