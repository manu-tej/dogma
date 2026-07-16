"""Integration tests for interaction tracking.

Tests user interaction tracking:
- track_dataset_interaction() with different types
- get_interaction_stats() verification
- has_user_viewed_dataset() checks
- Interaction history retrieval
"""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from quration.database.models import Conversation, User
from quration.repositories.interaction import InteractionRepository
from quration.services.context_service import ContextService


class TestInteractionTracking:
    """Test interaction tracking and retrieval."""

    @pytest.mark.asyncio
    async def test_record_interaction_basic(
        self,
        async_db_session: AsyncSession,
        interaction_repo: InteractionRepository,
        test_user: User,
    ):
        """Test recording a basic interaction."""
        interaction = await interaction_repo.record_interaction(
            user_id=test_user.id,
            dataset_id="GSE123456",
            interaction_type="view",
            metadata={"source": "search"},
        )
        await async_db_session.commit()

        assert interaction.id is not None
        assert interaction.user_id == test_user.id
        assert interaction.dataset_id == "GSE123456"
        assert interaction.interaction_type == "view"
        assert interaction.metadata["source"] == "search"

    @pytest.mark.asyncio
    async def test_record_interaction_types(
        self,
        async_db_session: AsyncSession,
        interaction_repo: InteractionRepository,
        test_user: User,
        test_conversation: Conversation,
    ):
        """Test recording different interaction types."""
        interaction_types = ["view", "analyze", "download"]

        for int_type in interaction_types:
            interaction = await interaction_repo.record_interaction(
                user_id=test_user.id,
                dataset_id=f"GSE{int_type}",
                interaction_type=int_type,
                conversation_id=test_conversation.id,
            )
            await async_db_session.commit()

            assert interaction.interaction_type == int_type
            assert interaction.conversation_id == test_conversation.id

    @pytest.mark.asyncio
    async def test_get_interaction_stats(
        self,
        async_db_session: AsyncSession,
        interaction_repo: InteractionRepository,
        test_user: User,
    ):
        """Test getting interaction statistics."""
        # Create various interactions
        datasets = ["GSE111", "GSE222", "GSE333", "GSE111"]  # Note duplicate
        types = ["view", "analyze", "view", "download"]

        for dataset, int_type in zip(datasets, types):
            await interaction_repo.record_interaction(
                user_id=test_user.id,
                dataset_id=dataset,
                interaction_type=int_type,
            )
        await async_db_session.commit()

        # Get stats
        stats = await interaction_repo.get_interaction_stats(test_user.id)

        assert stats["total_interactions"] == 4
        assert stats["unique_datasets"] == 3  # GSE111, GSE222, GSE333
        assert stats["view_count"] == 2
        assert stats["analyze_count"] == 1
        assert stats["download_count"] == 1

    @pytest.mark.asyncio
    async def test_has_user_viewed_dataset(
        self,
        async_db_session: AsyncSession,
        interaction_repo: InteractionRepository,
        test_user: User,
    ):
        """Test checking if user has viewed a dataset."""
        dataset_id = "GSE123456"

        # Initially not viewed
        has_viewed, first_view = await interaction_repo.has_user_viewed_dataset(
            user_id=test_user.id,
            dataset_id=dataset_id,
        )
        assert has_viewed is False
        assert first_view is None

        # Record view
        await interaction_repo.record_interaction(
            user_id=test_user.id,
            dataset_id=dataset_id,
            interaction_type="view",
        )
        await async_db_session.commit()

        # Now viewed
        has_viewed, first_view = await interaction_repo.has_user_viewed_dataset(
            user_id=test_user.id,
            dataset_id=dataset_id,
        )
        assert has_viewed is True
        assert first_view is not None
        assert first_view.dataset_id == dataset_id

    @pytest.mark.asyncio
    async def test_get_user_interactions_filtered(
        self,
        async_db_session: AsyncSession,
        interaction_repo: InteractionRepository,
        test_user: User,
    ):
        """Test getting filtered user interactions."""
        # Create interactions
        interactions_data = [
            ("GSE111", "view"),
            ("GSE222", "analyze"),
            ("GSE111", "download"),
            ("GSE333", "view"),
        ]

        for dataset, int_type in interactions_data:
            await interaction_repo.record_interaction(
                user_id=test_user.id,
                dataset_id=dataset,
                interaction_type=int_type,
            )
        await async_db_session.commit()

        # Filter by dataset
        gse111_interactions = await interaction_repo.get_user_interactions(
            user_id=test_user.id,
            dataset_id="GSE111",
        )
        assert len(gse111_interactions) == 2

        # Filter by type
        view_interactions = await interaction_repo.get_user_interactions(
            user_id=test_user.id,
            interaction_type="view",
        )
        assert len(view_interactions) == 2

        # Both filters
        gse111_downloads = await interaction_repo.get_user_interactions(
            user_id=test_user.id,
            dataset_id="GSE111",
            interaction_type="download",
        )
        assert len(gse111_downloads) == 1

    @pytest.mark.asyncio
    async def test_get_conversation_interactions(
        self,
        async_db_session: AsyncSession,
        interaction_repo: InteractionRepository,
        test_user: User,
        test_conversation: Conversation,
        empty_conversation: Conversation,
    ):
        """Test getting interactions for a specific conversation."""
        # Add interactions to different conversations
        await interaction_repo.record_interaction(
            user_id=test_user.id,
            dataset_id="GSE111",
            interaction_type="view",
            conversation_id=test_conversation.id,
        )
        await interaction_repo.record_interaction(
            user_id=test_user.id,
            dataset_id="GSE222",
            interaction_type="analyze",
            conversation_id=test_conversation.id,
        )
        await interaction_repo.record_interaction(
            user_id=test_user.id,
            dataset_id="GSE333",
            interaction_type="view",
            conversation_id=empty_conversation.id,
        )
        await async_db_session.commit()

        # Get interactions for test_conversation
        interactions = await interaction_repo.get_conversation_interactions(
            test_conversation.id
        )
        assert len(interactions) == 2

        # Get interactions for empty_conversation
        interactions = await interaction_repo.get_conversation_interactions(
            empty_conversation.id
        )
        assert len(interactions) == 1

    @pytest.mark.asyncio
    async def test_interaction_ordering(
        self,
        async_db_session: AsyncSession,
        interaction_repo: InteractionRepository,
        test_user: User,
    ):
        """Test interactions are ordered by created_at desc."""
        # Create interactions with small delays
        import asyncio

        datasets = [f"GSE{i}" for i in range(5)]
        for dataset in datasets:
            await interaction_repo.record_interaction(
                user_id=test_user.id,
                dataset_id=dataset,
                interaction_type="view",
            )
            await async_db_session.commit()
            await asyncio.sleep(0.01)  # Small delay to ensure different timestamps

        # Get interactions
        interactions = await interaction_repo.get_user_interactions(
            user_id=test_user.id
        )

        # Should be in reverse order (most recent first)
        assert interactions[0].dataset_id == "GSE4"
        assert interactions[1].dataset_id == "GSE3"
        assert interactions[4].dataset_id == "GSE0"


class TestInteractionWithContextService:
    """Test interaction tracking via context service."""

    @pytest.mark.asyncio
    async def test_track_dataset_interaction(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_user: User,
        test_conversation: Conversation,
    ):
        """Test tracking dataset interaction via service."""
        interaction = await context_service.track_dataset_interaction(
            user_id=test_user.id,
            dataset_id="GSE123456",
            interaction_type="view",
            conversation_id=test_conversation.id,
            metadata={"source": "search_results"},
        )

        assert interaction.id is not None
        assert interaction.dataset_id == "GSE123456"
        assert interaction.conversation_id == test_conversation.id

    @pytest.mark.asyncio
    async def test_get_dataset_history(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_user: User,
        test_conversation: Conversation,
    ):
        """Test getting dataset interaction history."""
        dataset_id = "GSE789012"

        # Record multiple interactions
        await context_service.track_dataset_interaction(
            user_id=test_user.id,
            dataset_id=dataset_id,
            interaction_type="view",
            conversation_id=test_conversation.id,
        )
        await context_service.track_dataset_interaction(
            user_id=test_user.id,
            dataset_id=dataset_id,
            interaction_type="analyze",
            conversation_id=test_conversation.id,
        )

        # Get history
        history = await context_service.get_dataset_history(
            dataset_id=dataset_id,
            user_id=test_user.id,
        )

        assert history["dataset_id"] == dataset_id
        assert history["has_viewed"] is True
        assert history["first_viewed_at"] is not None
        assert history["interaction_count"] == 2
        assert len(history["interactions"]) == 2

    @pytest.mark.asyncio
    async def test_get_recalled_datasets(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_user: User,
    ):
        """Test getting recently viewed datasets."""
        # View multiple datasets
        datasets = ["GSE111", "GSE222", "GSE333", "GSE444", "GSE555"]
        for dataset in datasets:
            await context_service.track_dataset_interaction(
                user_id=test_user.id,
                dataset_id=dataset,
                interaction_type="view",
            )

        # Get recalled datasets
        recalled = await context_service.get_recalled_datasets(
            user_id=test_user.id,
            limit=3,
        )

        assert len(recalled) == 3
        # Most recent first
        assert recalled[0]["dataset_id"] == "GSE555"
        assert recalled[1]["dataset_id"] == "GSE444"
        assert recalled[2]["dataset_id"] == "GSE333"

    @pytest.mark.asyncio
    async def test_get_dataset_conversations(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_user: User,
        test_conversation: Conversation,
        empty_conversation: Conversation,
    ):
        """Test getting all conversations where user interacted with a dataset."""
        dataset_id = "GSE123456"

        # Interact with dataset in multiple conversations
        await context_service.track_dataset_interaction(
            user_id=test_user.id,
            dataset_id=dataset_id,
            interaction_type="view",
            conversation_id=test_conversation.id,
        )
        await context_service.track_dataset_interaction(
            user_id=test_user.id,
            dataset_id=dataset_id,
            interaction_type="analyze",
            conversation_id=empty_conversation.id,
        )

        # Get conversations
        conversations = await context_service.get_dataset_conversations(
            dataset_id=dataset_id,
            user_id=test_user.id,
        )

        assert len(conversations) == 2
        conv_ids = {str(c["conversation_id"]) for c in conversations}
        assert str(test_conversation.id) in conv_ids
        assert str(empty_conversation.id) in conv_ids

    @pytest.mark.asyncio
    async def test_user_context_summary_interactions(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_user: User,
    ):
        """Test user context summary includes interaction stats."""
        # Create various interactions
        await context_service.track_dataset_interaction(
            user_id=test_user.id,
            dataset_id="GSE111",
            interaction_type="view",
        )
        await context_service.track_dataset_interaction(
            user_id=test_user.id,
            dataset_id="GSE222",
            interaction_type="analyze",
        )
        await context_service.track_dataset_interaction(
            user_id=test_user.id,
            dataset_id="GSE333",
            interaction_type="download",
        )

        # Get summary
        summary = await context_service.get_user_context_summary(test_user.id)

        assert summary["statistics"]["total_interactions"] == 3
        assert summary["statistics"]["unique_datasets_viewed"] == 3
        assert summary["interaction_breakdown"]["views"] == 1
        assert summary["interaction_breakdown"]["analyses"] == 1
        assert summary["interaction_breakdown"]["downloads"] == 1

    @pytest.mark.asyncio
    async def test_interaction_with_search_context(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_user: User,
        test_conversation: Conversation,
        sample_query_spec: dict,
        sample_search_results: list[dict],
    ):
        """Test tracking interactions that originated from searches."""
        # Save search
        search = await context_service.save_search_with_results(
            conversation_id=test_conversation.id,
            user_id=test_user.id,
            query_spec=sample_query_spec,
            results=sample_search_results,
        )

        # Track interaction from this search
        interaction = await context_service.track_dataset_interaction(
            user_id=test_user.id,
            dataset_id="GSE123456",
            interaction_type="view",
            conversation_id=test_conversation.id,
            search_id=search.id,
            metadata={"from_search": True},
        )

        assert interaction.search_id == search.id
        assert interaction.metadata["from_search"] is True

        # Verify relationship
        history = await context_service.get_dataset_history(
            dataset_id="GSE123456",
            user_id=test_user.id,
        )
        assert len(history["related_searches"]) == 1
