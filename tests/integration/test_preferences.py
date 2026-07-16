"""Integration tests for user preferences.

Tests preference management:
- save_preference() / get_user_preferences() CRUD
- analyze_search_patterns() for preference suggestions
- get_high_confidence_preferences() filtering (>0.7 confidence)
- Preference acceptance workflow
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from quration.database.models import User, Conversation
from quration.repositories.user import UserRepository
from quration.services.context_service import ContextService


class TestPreferenceCRUD:
    """Test preference CRUD operations."""

    @pytest.mark.asyncio
    async def test_save_preference_basic(
        self,
        async_db_session: AsyncSession,
        user_repo: UserRepository,
        test_user: User,
    ):
        """Test saving a basic preference."""
        preference = await user_repo.save_preference(
            user_id=test_user.id,
            preference_type="organism",
            preference_value="Homo sapiens",
            confidence_score=0.9,
            evidence={"source": "search_history", "count": 15},
        )
        await async_db_session.commit()

        assert preference.id is not None
        assert preference.user_id == test_user.id
        assert preference.preference_type == "organism"
        assert preference.preference_value == "Homo sapiens"
        assert preference.confidence_score == 0.9

    @pytest.mark.asyncio
    async def test_get_user_preferences(
        self,
        async_db_session: AsyncSession,
        user_repo: UserRepository,
        test_user: User,
        sample_preferences: list[dict],
    ):
        """Test retrieving user preferences."""
        # Save multiple preferences
        for pref_data in sample_preferences:
            await user_repo.save_preference(
                user_id=test_user.id,
                preference_type=pref_data["preference_key"],
                preference_value=pref_data["preference_value"],
                confidence_score=pref_data["confidence"],
                evidence={"description": pref_data["evidence"]},
            )
        await async_db_session.commit()

        # Get all preferences
        preferences = await user_repo.get_user_preferences(
            test_user.id,
            use_cache=False,
        )

        assert len(preferences) == 3
        # Should be ordered by updated_at desc
        pref_types = {p.preference_type for p in preferences}
        assert pref_types == {"organism", "library_strategy", "disease"}

    @pytest.mark.asyncio
    async def test_update_preference(
        self,
        async_db_session: AsyncSession,
        user_repo: UserRepository,
        test_user: User,
    ):
        """Test updating an existing preference."""
        # Create initial preference
        preference = await user_repo.save_preference(
            user_id=test_user.id,
            preference_type="organism",
            preference_value="Homo sapiens",
            confidence_score=0.8,
            evidence={"count": 10},
        )
        await async_db_session.commit()
        pref_id = preference.id

        # Update preference
        updated = await user_repo.update_preference(
            preference_id=pref_id,
            confidence_score=0.95,
            evidence={"count": 20, "updated": True},
        )
        await async_db_session.commit()

        assert updated.confidence_score == 0.95
        assert updated.evidence["count"] == 20
        assert updated.evidence["updated"] is True

        # Verify persistence
        async_db_session.expunge_all()
        reloaded = await user_repo.get_preference(pref_id)
        assert reloaded.confidence_score == 0.95

    @pytest.mark.asyncio
    async def test_delete_preference(
        self,
        async_db_session: AsyncSession,
        user_repo: UserRepository,
        test_user: User,
    ):
        """Test deleting a preference."""
        # Create preference
        preference = await user_repo.save_preference(
            user_id=test_user.id,
            preference_type="test",
            preference_value="value",
            confidence_score=0.5,
        )
        await async_db_session.commit()
        pref_id = preference.id

        # Delete
        success = await user_repo.delete_preference(pref_id)
        await async_db_session.commit()

        assert success is True

        # Verify deletion
        deleted = await user_repo.get_preference(pref_id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_preference_cache_integration(
        self,
        async_db_session: AsyncSession,
        user_repo: UserRepository,
        test_user: User,
        redis_client,
    ):
        """Test preference caching."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        # Save preference
        await user_repo.save_preference(
            user_id=test_user.id,
            preference_type="organism",
            preference_value="Homo sapiens",
            confidence_score=0.9,
        )
        await async_db_session.commit()

        # First load - should cache
        prefs1 = await user_repo.get_user_preferences(
            test_user.id,
            use_cache=True,
        )
        assert len(prefs1) == 1

        # Expire session
        async_db_session.expunge_all()

        # Second load - should use cache
        prefs2 = await user_repo.get_user_preferences(
            test_user.id,
            use_cache=True,
        )
        assert len(prefs2) == 1


class TestPreferenceFiltering:
    """Test preference filtering and analysis."""

    @pytest.mark.asyncio
    async def test_get_high_confidence_preferences(
        self,
        async_db_session: AsyncSession,
        user_repo: UserRepository,
        test_user: User,
    ):
        """Test filtering preferences by confidence threshold (>0.7)."""
        # Create preferences with varying confidence
        preferences_data = [
            ("organism", "Homo sapiens", 0.9),
            ("library_strategy", "RNA-Seq", 0.75),
            ("disease", "cancer", 0.6),  # Below threshold
            ("tissue", "breast", 0.85),
            ("platform", "Illumina", 0.5),  # Below threshold
        ]

        for pref_type, pref_value, confidence in preferences_data:
            await user_repo.save_preference(
                user_id=test_user.id,
                preference_type=pref_type,
                preference_value=pref_value,
                confidence_score=confidence,
            )
        await async_db_session.commit()

        # Get high confidence preferences (>0.7)
        high_conf = await user_repo.get_high_confidence_preferences(
            test_user.id,
            min_confidence=0.7,
        )

        assert len(high_conf) == 3
        conf_scores = [p.confidence_score for p in high_conf]
        assert all(score > 0.7 for score in conf_scores)

        # Verify specific preferences
        pref_types = {p.preference_type for p in high_conf}
        assert pref_types == {"organism", "library_strategy", "tissue"}

    @pytest.mark.asyncio
    async def test_get_preferences_by_type(
        self,
        async_db_session: AsyncSession,
        user_repo: UserRepository,
        test_user: User,
    ):
        """Test filtering preferences by type."""
        # Create multiple preferences of same type
        for i, organism in enumerate(["Homo sapiens", "Mus musculus", "Rattus norvegicus"]):
            await user_repo.save_preference(
                user_id=test_user.id,
                preference_type="organism",
                preference_value=organism,
                confidence_score=0.9 - (i * 0.1),
            )
        await async_db_session.commit()

        # Get organism preferences
        organism_prefs = await user_repo.get_preferences_by_type(
            test_user.id,
            preference_type="organism",
        )

        assert len(organism_prefs) == 3
        assert all(p.preference_type == "organism" for p in organism_prefs)

    @pytest.mark.asyncio
    async def test_count_user_preferences(
        self,
        async_db_session: AsyncSession,
        user_repo: UserRepository,
        test_user: User,
        test_user_2: User,
    ):
        """Test counting user preferences."""
        # User 1: 3 preferences
        for i in range(3):
            await user_repo.save_preference(
                user_id=test_user.id,
                preference_type=f"type_{i}",
                preference_value="value",
                confidence_score=0.8,
            )

        # User 2: 2 preferences
        for i in range(2):
            await user_repo.save_preference(
                user_id=test_user_2.id,
                preference_type=f"type_{i}",
                preference_value="value",
                confidence_score=0.8,
            )
        await async_db_session.commit()

        # Count for each user
        count1 = await user_repo.count_user_preferences(test_user.id)
        count2 = await user_repo.count_user_preferences(test_user_2.id)

        assert count1 == 3
        assert count2 == 2


class TestPreferenceAnalysis:
    """Test preference analysis and suggestion."""

    @pytest.mark.asyncio
    async def test_analyze_search_patterns(
        self,
        async_db_session: AsyncSession,
        user_repo: UserRepository,
        context_service: ContextService,
        test_user: User,
        test_conversation: Conversation,
    ):
        """Test analyzing search patterns for preference suggestions."""
        # Create searches with consistent patterns
        search_queries = [
            {"query": "breast cancer RNA-seq", "organism": "Homo sapiens"},
            {"query": "melanoma gene expression", "organism": "Homo sapiens"},
            {"query": "lung cancer transcriptome", "organism": "Homo sapiens"},
        ]

        for query_spec in search_queries:
            await context_service.save_search_with_results(
                conversation_id=test_conversation.id,
                user_id=test_user.id,
                query_spec=query_spec,
                results=[],
            )
        await async_db_session.commit()

        # Analyze patterns
        suggestions = await user_repo.analyze_search_patterns(test_user.id)

        # Should suggest organism preference
        assert "organism" in suggestions
        assert suggestions["organism"]["value"] == "Homo sapiens"
        assert suggestions["organism"]["confidence"] > 0.7

    @pytest.mark.asyncio
    async def test_preference_acceptance_workflow(
        self,
        async_db_session: AsyncSession,
        user_repo: UserRepository,
        test_user: User,
    ):
        """Test preference suggestion acceptance workflow."""
        # System suggests a preference (low confidence initially)
        suggestion = await user_repo.save_preference(
            user_id=test_user.id,
            preference_type="organism",
            preference_value="Homo sapiens",
            confidence_score=0.6,
            evidence={"source": "suggestion", "auto_detected": True},
            is_accepted=False,
        )
        await async_db_session.commit()

        # User accepts the suggestion
        accepted = await user_repo.accept_preference(suggestion.id)
        await async_db_session.commit()

        assert accepted.is_accepted is True
        # Accepting should boost confidence
        assert accepted.confidence_score >= suggestion.confidence_score

    @pytest.mark.asyncio
    async def test_merge_preference_evidence(
        self,
        async_db_session: AsyncSession,
        user_repo: UserRepository,
        test_user: User,
    ):
        """Test merging evidence when updating preferences."""
        # Create initial preference
        preference = await user_repo.save_preference(
            user_id=test_user.id,
            preference_type="organism",
            preference_value="Homo sapiens",
            confidence_score=0.7,
            evidence={"searches": 5, "source": "auto"},
        )
        await async_db_session.commit()

        # Update with additional evidence
        updated = await user_repo.update_preference(
            preference_id=preference.id,
            confidence_score=0.85,
            evidence={
                "searches": 10,
                "source": "auto",
                "user_confirmed": True,
            },
        )
        await async_db_session.commit()

        assert updated.evidence["searches"] == 10
        assert updated.evidence["user_confirmed"] is True


class TestPreferenceWithContextService:
    """Test preference operations via context service."""

    @pytest.mark.asyncio
    async def test_user_context_summary_includes_preferences(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        user_repo: UserRepository,
        test_user: User,
    ):
        """Test user context summary includes preference count."""
        # Save preferences
        for i in range(5):
            await user_repo.save_preference(
                user_id=test_user.id,
                preference_type=f"type_{i}",
                preference_value="value",
                confidence_score=0.8,
            )
        await async_db_session.commit()

        # Get summary
        summary = await context_service.get_user_context_summary(test_user.id)

        assert summary["statistics"]["saved_preferences"] == 5

    @pytest.mark.asyncio
    async def test_preference_influence_on_search(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        user_repo: UserRepository,
        test_user: User,
    ):
        """Test that preferences can influence search behavior."""
        # Save high-confidence organism preference
        await user_repo.save_preference(
            user_id=test_user.id,
            preference_type="organism",
            preference_value="Homo sapiens",
            confidence_score=0.95,
            is_accepted=True,
        )
        await async_db_session.commit()

        # Get high confidence preferences
        prefs = await user_repo.get_high_confidence_preferences(
            test_user.id,
            min_confidence=0.9,
        )

        # Verify preference can be used to auto-fill search filters
        assert len(prefs) == 1
        assert prefs[0].preference_type == "organism"
        assert prefs[0].preference_value == "Homo sapiens"

    @pytest.mark.asyncio
    async def test_preference_cache_invalidation(
        self,
        async_db_session: AsyncSession,
        user_repo: UserRepository,
        test_user: User,
        redis_client,
    ):
        """Test preference cache is invalidated on updates."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        # Create preference
        pref = await user_repo.save_preference(
            user_id=test_user.id,
            preference_type="organism",
            preference_value="Homo sapiens",
            confidence_score=0.8,
        )
        await async_db_session.commit()

        # Load to cache
        prefs1 = await user_repo.get_user_preferences(test_user.id, use_cache=True)
        assert prefs1[0].confidence_score == 0.8

        # Update preference
        await user_repo.update_preference(
            preference_id=pref.id,
            confidence_score=0.95,
        )
        await async_db_session.commit()

        # Load again - should get updated value
        async_db_session.expunge_all()
        prefs2 = await user_repo.get_user_preferences(test_user.id, use_cache=True)
        assert prefs2[0].confidence_score == 0.95
