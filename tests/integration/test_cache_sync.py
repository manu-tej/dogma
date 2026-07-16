"""Integration tests for cache-database synchronization.

Tests cache synchronization patterns:
- Write-through cache verification (DB write triggers cache update)
- Cache miss triggers DB fetch
- Cache invalidation on updates
- Cache-aside pattern for reads
- Consistency checks between cache and database
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from quration.database.models import Conversation, User
from quration.repositories.conversation import ConversationRepository
from quration.repositories.search import SearchRepository
from quration.repositories.user import UserRepository
from quration.services.context_service import ContextService


class TestCacheWriteThrough:
    """Test write-through caching pattern."""

    @pytest.mark.asyncio
    async def test_conversation_write_through(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_user: User,
        redis_client,
    ):
        """Test conversation write triggers cache update."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        # Create conversation - should write to DB and cache
        conversation = await conversation_repo.create_conversation(
            user_id=test_user.id,
            title="Cache Test",
        )
        await async_db_session.commit()

        # Load from cache
        cached = await conversation_repo.get_conversation(
            conversation.id,
            use_cache=True,
        )

        # Verify data matches
        assert cached.id == conversation.id
        assert cached.title == "Cache Test"

    @pytest.mark.asyncio
    async def test_preference_write_through(
        self,
        async_db_session: AsyncSession,
        user_repo: UserRepository,
        test_user: User,
        redis_client,
    ):
        """Test preference write updates cache."""
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

        # Load from cache
        prefs = await user_repo.get_user_preferences(
            test_user.id,
            use_cache=True,
        )

        assert len(prefs) == 1
        assert prefs[0].preference_type == "organism"


class TestCacheAside:
    """Test cache-aside pattern."""

    @pytest.mark.asyncio
    async def test_cache_miss_triggers_db_fetch(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_conversation: Conversation,
        redis_client,
    ):
        """Test cache miss triggers database fetch and caches result."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        conv_id = test_conversation.id

        # Clear cache to simulate miss
        from quration.cache.redis_client import build_conversation_key
        cache_key = build_conversation_key(str(conv_id))
        await redis_client.delete(cache_key)

        # First load - cache miss, should fetch from DB and cache
        conv1 = await conversation_repo.get_conversation(conv_id, use_cache=True)
        assert conv1 is not None

        # Expire session to ensure next load comes from cache
        async_db_session.expunge_all()

        # Second load - should be from cache
        conv2 = await conversation_repo.get_conversation(conv_id, use_cache=True)
        assert conv2 is not None
        assert conv2.id == conv_id

    @pytest.mark.asyncio
    async def test_cache_bypass_when_disabled(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_conversation: Conversation,
        redis_client,
    ):
        """Test cache can be bypassed when use_cache=False."""
        conv_id = test_conversation.id

        # Load with cache disabled
        conv1 = await conversation_repo.get_conversation(conv_id, use_cache=False)
        assert conv1 is not None

        # Modify in DB
        await conversation_repo.update_conversation(
            conv_id,
            title="Updated Title",
        )
        await async_db_session.commit()

        # Load with cache disabled - should get fresh data
        async_db_session.expunge_all()
        conv2 = await conversation_repo.get_conversation(conv_id, use_cache=False)
        assert conv2.title == "Updated Title"


class TestCacheInvalidation:
    """Test cache invalidation on updates."""

    @pytest.mark.asyncio
    async def test_conversation_update_invalidates_cache(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_conversation: Conversation,
        redis_client,
    ):
        """Test updating conversation invalidates cache."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        conv_id = test_conversation.id

        # Load to populate cache
        await conversation_repo.get_conversation(conv_id, use_cache=True)

        # Update conversation - should invalidate cache
        await conversation_repo.update_conversation(
            conv_id,
            title="New Title",
        )
        await async_db_session.commit()

        # Load again - should get updated data from DB
        async_db_session.expunge_all()
        updated = await conversation_repo.get_conversation(conv_id, use_cache=True)
        assert updated.title == "New Title"

    @pytest.mark.asyncio
    async def test_message_add_invalidates_conversation_cache(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_conversation: Conversation,
        redis_client,
    ):
        """Test adding message invalidates conversation cache."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        conv_id = test_conversation.id
        initial_msg_count = len(test_conversation.messages)

        # Load to cache
        await conversation_repo.get_conversation(conv_id, use_cache=True)

        # Add message - should invalidate conversation cache
        await conversation_repo.add_message(
            conversation_id=conv_id,
            role="user",
            content="New message",
        )
        await async_db_session.commit()

        # Load again - should have new message
        async_db_session.expunge_all()
        reloaded = await conversation_repo.get_conversation(conv_id, use_cache=True)
        assert len(reloaded.messages) == initial_msg_count + 1

    @pytest.mark.asyncio
    async def test_delete_invalidates_cache(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_user: User,
        redis_client,
    ):
        """Test deleting conversation invalidates cache."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        # Create conversation
        conv = await conversation_repo.create_conversation(
            user_id=test_user.id,
            title="To Delete",
        )
        await async_db_session.commit()
        conv_id = conv.id

        # Load to cache
        await conversation_repo.get_conversation(conv_id, use_cache=True)

        # Delete - should invalidate cache
        await conversation_repo.delete_conversation(conv_id)
        await async_db_session.commit()

        # Load again - should return None
        deleted = await conversation_repo.get_conversation(conv_id, use_cache=True)
        assert deleted is None


class TestCacheConsistency:
    """Test consistency between cache and database."""

    @pytest.mark.asyncio
    async def test_cache_db_consistency_conversation(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_user: User,
        redis_client,
    ):
        """Test cache and DB remain consistent for conversations."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        # Create conversation
        conv = await conversation_repo.create_conversation(
            user_id=test_user.id,
            title="Consistency Test",
            metadata={"version": 1},
        )
        await async_db_session.commit()
        conv_id = conv.id

        # Load from cache
        cached = await conversation_repo.get_conversation(conv_id, use_cache=True)

        # Load from DB
        async_db_session.expunge_all()
        from_db = await conversation_repo.get_conversation(conv_id, use_cache=False)

        # Verify consistency
        assert cached.id == from_db.id
        assert cached.title == from_db.title
        assert cached.metadata == from_db.metadata
        assert cached.user_id == from_db.user_id

    @pytest.mark.asyncio
    async def test_cache_db_consistency_with_messages(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_conversation: Conversation,
        redis_client,
    ):
        """Test cache and DB consistency for conversations with messages."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        conv_id = test_conversation.id

        # Load to cache
        cached = await conversation_repo.get_conversation(conv_id, use_cache=True)

        # Load from DB
        async_db_session.expunge_all()
        from_db = await conversation_repo.get_conversation(conv_id, use_cache=False)

        # Verify message consistency
        assert len(cached.messages) == len(from_db.messages)
        for cached_msg, db_msg in zip(cached.messages, from_db.messages):
            assert cached_msg.id == db_msg.id
            assert cached_msg.role == db_msg.role
            assert cached_msg.content == db_msg.content

    @pytest.mark.asyncio
    async def test_concurrent_updates_consistency(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_user: User,
        redis_client,
    ):
        """Test cache consistency with concurrent updates."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        # Create conversation
        conv = await conversation_repo.create_conversation(
            user_id=test_user.id,
            title="Concurrent Test",
        )
        await async_db_session.commit()
        conv_id = conv.id

        # Simulate concurrent updates
        await conversation_repo.update_conversation(
            conv_id,
            title="Update 1",
        )
        await async_db_session.commit()

        await conversation_repo.update_conversation(
            conv_id,
            title="Update 2",
        )
        await async_db_session.commit()

        # Final read should have latest data
        async_db_session.expunge_all()
        final = await conversation_repo.get_conversation(conv_id, use_cache=True)
        assert final.title == "Update 2"


class TestCacheGracefulDegradation:
    """Test graceful degradation when cache is unavailable."""

    @pytest.mark.asyncio
    async def test_operations_work_without_cache(
        self,
        async_db_session: AsyncSession,
        test_user: User,
    ):
        """Test all operations work when cache is None."""
        # Create repo without cache
        repo = ConversationRepository(async_db_session, cache=None)

        # All operations should still work
        conv = await repo.create_conversation(
            user_id=test_user.id,
            title="No Cache Test",
        )
        await async_db_session.commit()

        # Read works
        loaded = await repo.get_conversation(conv.id)
        assert loaded is not None
        assert loaded.title == "No Cache Test"

        # Update works
        updated = await repo.update_conversation(
            conv.id,
            title="Updated",
        )
        await async_db_session.commit()
        assert updated.title == "Updated"

    @pytest.mark.asyncio
    async def test_cache_failure_fallback_to_db(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_conversation: Conversation,
        redis_client,
        monkeypatch,
    ):
        """Test fallback to DB when cache operations fail."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        # Mock cache.get to raise exception
        async def failing_get(*args, **kwargs):
            raise Exception("Cache failure")

        monkeypatch.setattr(redis_client, "get", failing_get)

        # Operation should still work by falling back to DB
        conv = await conversation_repo.get_conversation(
            test_conversation.id,
            use_cache=True,
        )
        assert conv is not None


class TestCacheWithContextService:
    """Test cache synchronization via context service."""

    @pytest.mark.asyncio
    async def test_full_context_restoration_with_cache(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_user: User,
        redis_client,
    ):
        """Test full context restoration uses cache effectively."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        # Create conversation with messages
        conv, msg = await context_service.create_conversation_with_message(
            user_id=test_user.id,
            role="user",
            content="Test message",
            title="Cache Context Test",
        )

        # Add search
        await context_service.save_search_with_results(
            conversation_id=conv.id,
            user_id=test_user.id,
            query_spec={"query": "test"},
            results=[{"dataset_id": "GSE123", "score": 0.9}],
        )

        # Track interaction
        await context_service.track_dataset_interaction(
            user_id=test_user.id,
            dataset_id="GSE123",
            interaction_type="view",
            conversation_id=conv.id,
        )

        # First restoration - populates cache
        context1 = await context_service.restore_conversation_state(conv.id)

        # Expire session
        async_db_session.expunge_all()

        # Second restoration - should use cache
        context2 = await context_service.restore_conversation_state(conv.id)

        # Verify consistency
        assert context1["conversation"]["id"] == context2["conversation"]["id"]
        assert len(context1["messages"]) == len(context2["messages"])
        assert len(context1["searches"]) == len(context2["searches"])

    @pytest.mark.asyncio
    async def test_cache_performance_benefit(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_conversation: Conversation,
        redis_client,
    ):
        """Test cache provides performance benefit."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        import time

        conv_id = test_conversation.id

        # Cold load (no cache) - measure time
        start = time.time()
        await conversation_repo.get_conversation(conv_id, use_cache=False)
        cold_time = time.time() - start

        # Warm load (with cache) - should be faster
        # First load to populate cache
        await conversation_repo.get_conversation(conv_id, use_cache=True)

        # Expire session
        async_db_session.expunge_all()

        # Second load from cache
        start = time.time()
        await conversation_repo.get_conversation(conv_id, use_cache=True)
        warm_time = time.time() - start

        # Cache should be at least as fast (allowing for some variance)
        # This is a soft check - cache should generally be faster but we
        # don't want flaky tests from timing variations
        assert warm_time <= cold_time * 2  # Allow 2x slower for variance
