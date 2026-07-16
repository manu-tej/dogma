"""Integration tests for conversation persistence.

Tests full conversation lifecycle:
- Create conversation with messages
- Refresh/reload from database
- Verify complete restoration
- Test message ordering
- Test cache integration
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from quration.database.models import Conversation, Message, User
from quration.repositories.conversation import ConversationRepository
from quration.services.context_service import ContextService


class TestConversationPersistence:
    """Test conversation persistence and restoration."""

    @pytest.mark.asyncio
    async def test_create_conversation_with_messages(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_user: User,
    ):
        """Test creating a conversation with multiple messages."""
        # Create conversation
        conversation = await conversation_repo.create_conversation(
            user_id=test_user.id,
            title="Test Conversation",
            metadata={"purpose": "testing"},
        )
        await async_db_session.commit()

        assert conversation.id is not None
        assert conversation.user_id == test_user.id
        assert conversation.title == "Test Conversation"
        assert conversation.metadata["purpose"] == "testing"

        # Add messages
        message_1 = await conversation_repo.add_message(
            conversation_id=conversation.id,
            role="user",
            content="Hello",
            metadata={"first": True},
        )
        await async_db_session.commit()

        message_2 = await conversation_repo.add_message(
            conversation_id=conversation.id,
            role="assistant",
            content="Hi there!",
            metadata={},
        )
        await async_db_session.commit()

        # Verify messages
        assert message_1.conversation_id == conversation.id
        assert message_2.conversation_id == conversation.id
        assert message_1.role == "user"
        assert message_2.role == "assistant"

    @pytest.mark.asyncio
    async def test_conversation_restoration_after_refresh(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_conversation: Conversation,
    ):
        """Test conversation can be restored after session refresh."""
        original_id = test_conversation.id

        # Expunge from session to simulate fresh load
        async_db_session.expunge_all()

        # Reload conversation
        restored = await conversation_repo.get_conversation(
            original_id, use_cache=False
        )

        assert restored is not None
        assert restored.id == original_id
        assert len(restored.messages) == 3
        assert restored.messages[0].role == "user"
        assert restored.messages[1].role == "assistant"
        assert restored.messages[2].role == "user"

    @pytest.mark.asyncio
    async def test_message_ordering_preserved(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_user: User,
    ):
        """Test message ordering is preserved across persistence."""
        # Create conversation
        conversation = await conversation_repo.create_conversation(
            user_id=test_user.id,
            title="Order Test",
        )
        await async_db_session.commit()

        # Add messages in specific order
        expected_order = []
        for i in range(10):
            content = f"Message {i}"
            msg = await conversation_repo.add_message(
                conversation_id=conversation.id,
                role="user" if i % 2 == 0 else "assistant",
                content=content,
            )
            await async_db_session.commit()
            expected_order.append(content)

        # Reload and verify order
        async_db_session.expunge_all()
        restored = await conversation_repo.get_conversation(conversation.id)

        assert len(restored.messages) == 10
        actual_order = [msg.content for msg in restored.messages]
        assert actual_order == expected_order

    @pytest.mark.asyncio
    async def test_full_crud_cycle(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_user: User,
    ):
        """Test full CRUD lifecycle for conversations."""
        # CREATE
        conversation = await conversation_repo.create_conversation(
            user_id=test_user.id,
            title="CRUD Test",
            metadata={"version": 1},
        )
        await async_db_session.commit()
        conv_id = conversation.id

        # READ
        read_conv = await conversation_repo.get_conversation(conv_id)
        assert read_conv is not None
        assert read_conv.title == "CRUD Test"
        assert read_conv.metadata["version"] == 1

        # UPDATE
        updated = await conversation_repo.update_conversation(
            conv_id,
            title="Updated CRUD Test",
            metadata={"version": 2, "updated": True},
        )
        await async_db_session.commit()
        assert updated.title == "Updated CRUD Test"
        assert updated.metadata["version"] == 2

        # Verify update persisted
        async_db_session.expunge_all()
        reread = await conversation_repo.get_conversation(conv_id)
        assert reread.title == "Updated CRUD Test"
        assert reread.metadata["updated"] is True

        # DELETE
        success = await conversation_repo.delete_conversation(conv_id)
        await async_db_session.commit()
        assert success is True

        # Verify deletion
        deleted = await conversation_repo.get_conversation(conv_id)
        assert deleted is None

    @pytest.mark.asyncio
    async def test_conversation_with_cache(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_conversation: Conversation,
        redis_client,
    ):
        """Test conversation caching behavior."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        conv_id = test_conversation.id

        # First load - should cache
        conv1 = await conversation_repo.get_conversation(conv_id, use_cache=True)
        assert conv1 is not None

        # Expire session to ensure we're not using session cache
        async_db_session.expunge_all()

        # Second load - should use cache
        conv2 = await conversation_repo.get_conversation(conv_id, use_cache=True)
        assert conv2 is not None
        assert conv2.id == conv_id

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_update(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_conversation: Conversation,
        redis_client,
    ):
        """Test cache is invalidated when conversation is updated."""
        if not redis_client.is_available():
            pytest.skip("Redis not available")

        conv_id = test_conversation.id

        # Load to populate cache
        await conversation_repo.get_conversation(conv_id, use_cache=True)

        # Update conversation (should invalidate cache)
        await conversation_repo.update_conversation(
            conv_id,
            title="Updated Title",
        )
        await async_db_session.commit()

        # Load again - should get updated version
        async_db_session.expunge_all()
        updated_conv = await conversation_repo.get_conversation(conv_id, use_cache=True)
        assert updated_conv.title == "Updated Title"

    @pytest.mark.asyncio
    async def test_large_conversation_handling(
        self,
        async_db_session: AsyncSession,
        conversation_repo: ConversationRepository,
        test_user: User,
        large_message_list: list[dict],
    ):
        """Test handling of conversations with 100+ messages."""
        # Create conversation
        conversation = await conversation_repo.create_conversation(
            user_id=test_user.id,
            title="Large Conversation Test",
        )
        await async_db_session.commit()

        # Add 100 messages
        for msg_data in large_message_list:
            await conversation_repo.add_message(
                conversation_id=conversation.id,
                role=msg_data["role"],
                content=msg_data["content"],
                metadata=msg_data["metadata"],
            )
        await async_db_session.commit()

        # Reload and verify
        async_db_session.expunge_all()
        restored = await conversation_repo.get_conversation(conversation.id)
        assert len(restored.messages) == 100

        # Verify message order and content
        for i, msg in enumerate(restored.messages):
            assert msg.metadata["index"] == i
            assert f"Message {i}" in msg.content


class TestConversationContextService:
    """Test context service for conversation operations."""

    @pytest.mark.asyncio
    async def test_create_conversation_with_initial_message(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_user: User,
    ):
        """Test creating conversation with initial message via service."""
        conversation, message = await context_service.create_conversation_with_message(
            user_id=test_user.id,
            role="user",
            content="I need help with analysis",
            title="Analysis Help",
            metadata={"source": "api"},
        )

        assert conversation.id is not None
        assert conversation.title == "Analysis Help"
        assert message.conversation_id == conversation.id
        assert message.role == "user"
        assert message.content == "I need help with analysis"

    @pytest.mark.asyncio
    async def test_get_conversation_context_full(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_conversation: Conversation,
    ):
        """Test retrieving full conversation context."""
        context = await context_service.get_conversation_context(
            test_conversation.id
        )

        assert context is not None
        assert context["conversation"]["id"] == str(test_conversation.id)
        assert len(context["messages"]) == 3
        assert context["searches"] == []  # No searches yet
        assert context["interactions"] == []  # No interactions yet

    @pytest.mark.asyncio
    async def test_restore_conversation_state(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_conversation: Conversation,
    ):
        """Test full conversation state restoration."""
        state = await context_service.restore_conversation_state(
            test_conversation.id
        )

        assert state is not None
        assert state["conversation"]["id"] == str(test_conversation.id)
        assert len(state["messages"]) == 3

        # Verify message content
        messages = state["messages"]
        assert messages[0]["role"] == "user"
        assert "RNA-seq" in messages[0]["content"]
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"

    @pytest.mark.asyncio
    async def test_conversation_persistence_across_sessions(
        self,
        async_db_session: AsyncSession,
        context_service: ContextService,
        test_user: User,
    ):
        """Test conversation persists correctly across multiple sessions."""
        # Session 1: Create conversation
        conv, msg = await context_service.create_conversation_with_message(
            user_id=test_user.id,
            role="user",
            content="First message",
            title="Multi-Session Test",
        )
        conv_id = conv.id

        # Session 2: Add more messages
        await context_service.conversation_repo.add_message(
            conversation_id=conv_id,
            role="assistant",
            content="Response message",
        )
        await async_db_session.commit()

        # Session 3: Reload and verify all data
        async_db_session.expunge_all()
        restored = await context_service.get_conversation_context(conv_id)

        assert len(restored["messages"]) == 2
        assert restored["messages"][0]["content"] == "First message"
        assert restored["messages"][1]["content"] == "Response message"
