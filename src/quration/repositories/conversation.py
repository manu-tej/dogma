"""Conversation repository for managing chat conversations and messages.

This repository handles CRUD operations for conversations and messages
with integrated caching for fast retrieval.
"""

import logging
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import desc, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from quration.cache.redis_client import RedisClient, build_conversation_key
from quration.database.models import Conversation, Message
from quration.repositories.base import BaseRepository, RepositoryError
from quration.utils.tag_validator import validate_tags, merge_tags, TagValidationError

logger = logging.getLogger(__name__)


class ConversationRepository(BaseRepository[Conversation]):
    """Repository for conversation operations."""

    def __init__(self, session: AsyncSession, cache: RedisClient | None = None):
        """Initialize conversation repository.

        Args:
            session: Async database session
            cache: Optional Redis cache instance
        """
        super().__init__(Conversation, session, cache)

    async def create_conversation(
        self,
        user_id: UUID,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Conversation:
        """Create a new conversation.

        Args:
            user_id: User UUID
            title: Optional conversation title
            metadata: Optional metadata dictionary

        Returns:
            Created conversation

        Raises:
            RepositoryError: If creation fails
        """
        try:
            conversation = await self.create(
                user_id=user_id,
                title=title,
                metadata=metadata or {},
            )

            logger.info(f"Created conversation {conversation.id} for user {user_id}")
            return conversation
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
            raise RepositoryError("Failed to create conversation") from e

    async def get_conversation(
        self, conversation_id: UUID, use_cache: bool = True
    ) -> Conversation | None:
        """Get a conversation by ID with messages.

        This method uses cache-aside pattern:
        1. Check cache first
        2. If miss, load from database
        3. Store in cache for future requests

        Args:
            conversation_id: Conversation UUID
            use_cache: Whether to use cache (default: True)

        Returns:
            Conversation with messages or None if not found
        """
        # Try cache first
        if use_cache and self.cache:
            cache_key = build_conversation_key(str(conversation_id))
            cached_data = self.cache.get(cache_key)

            if cached_data:
                logger.debug(f"Cache hit for conversation {conversation_id}")
                # Return from cache - would need to reconstruct object
                # For now, skip cache reconstruction and load from DB
                pass

        # Load from database
        try:
            result = await self.session.execute(
                select(Conversation)
                .where(Conversation.id == conversation_id)
                .options(selectinload(Conversation.messages))
            )
            conversation = result.scalar_one_or_none()

            # Cache for future use
            if conversation and use_cache and self.cache:
                cache_key = build_conversation_key(str(conversation_id))
                # Serialize conversation data
                cache_data = {
                    "id": str(conversation.id),
                    "user_id": str(conversation.user_id),
                    "title": conversation.title,
                    "metadata": conversation.metadata,
                    "created_at": conversation.created_at.isoformat(),
                    "updated_at": conversation.updated_at.isoformat(),
                    "messages": [
                        {
                            "id": str(msg.id),
                            "role": msg.role,
                            "content": msg.content,
                            "created_at": msg.created_at.isoformat(),
                            "metadata": msg.metadata,
                        }
                        for msg in conversation.messages
                    ],
                }
                self.cache.set(
                    cache_key, cache_data, ttl=self.cache.config.ttl_conversation
                )
                logger.debug(f"Cached conversation {conversation_id}")

            return conversation
        except Exception as e:
            logger.error(f"Failed to get conversation {conversation_id}: {e}")
            return None

    async def list_user_conversations(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        include_messages: bool = False,
    ) -> Sequence[Conversation]:
        """List conversations for a user.

        Args:
            user_id: User UUID
            limit: Maximum number of conversations to return
            offset: Number of conversations to skip
            include_messages: Whether to load messages (default: False)

        Returns:
            List of conversations ordered by updated_at desc
        """
        try:
            stmt = (
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(desc(Conversation.updated_at))
                .offset(offset)
                .limit(limit)
            )

            if include_messages:
                stmt = stmt.options(selectinload(Conversation.messages))

            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to list conversations for user {user_id}: {e}")
            return []

    async def update_conversation(
        self,
        conversation_id: UUID,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Conversation | None:
        """Update a conversation.

        Args:
            conversation_id: Conversation UUID
            title: New title (if provided)
            metadata: New metadata (if provided)

        Returns:
            Updated conversation or None if not found
        """
        update_data = {}
        if title is not None:
            update_data["title"] = title
        if metadata is not None:
            update_data["metadata"] = metadata

        if not update_data:
            return await self.get_by_id(conversation_id)

        conversation = await self.update(conversation_id, **update_data)

        # Invalidate cache
        if conversation and self.cache:
            cache_key = build_conversation_key(str(conversation_id))
            self.cache.delete(cache_key)
            logger.debug(f"Invalidated cache for conversation {conversation_id}")

        return conversation

    async def archive_conversation(self, conversation_id: UUID) -> bool:
        """Archive a conversation (soft delete via metadata).

        Args:
            conversation_id: Conversation UUID

        Returns:
            True if archived successfully
        """
        conversation = await self.get_by_id(conversation_id)
        if not conversation:
            return False

        metadata = conversation.metadata or {}
        metadata["archived"] = True

        updated = await self.update(conversation_id, metadata=metadata)

        # Invalidate cache
        if updated and self.cache:
            cache_key = build_conversation_key(str(conversation_id))
            self.cache.delete(cache_key)

        return updated is not None

    async def delete_conversation(self, conversation_id: UUID) -> bool:
        """Delete a conversation and all its messages.

        Args:
            conversation_id: Conversation UUID

        Returns:
            True if deleted successfully
        """
        success = await self.delete(conversation_id)

        # Invalidate cache
        if success and self.cache:
            cache_key = build_conversation_key(str(conversation_id))
            self.cache.delete(cache_key)
            logger.debug(f"Deleted conversation {conversation_id} and invalidated cache")

        return success

    # Message operations

    async def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        """Add a message to a conversation.

        Args:
            conversation_id: Conversation UUID
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata dictionary

        Returns:
            Created message

        Raises:
            RepositoryError: If creation fails
        """
        try:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                metadata=metadata or {},
            )
            self.session.add(message)
            await self.session.flush()
            await self.session.refresh(message)

            # Invalidate conversation cache
            if self.cache:
                cache_key = build_conversation_key(str(conversation_id))
                self.cache.delete(cache_key)

            logger.debug(f"Added message to conversation {conversation_id}")
            return message
        except Exception as e:
            logger.error(f"Failed to add message: {e}")
            raise RepositoryError("Failed to add message") from e

    async def get_conversation_messages(
        self,
        conversation_id: UUID,
        limit: int | None = None,
        offset: int = 0,
    ) -> Sequence[Message]:
        """Get messages for a conversation.

        Args:
            conversation_id: Conversation UUID
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of messages ordered by created_at
        """
        try:
            stmt = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at)
                .offset(offset)
            )

            if limit is not None:
                stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(
                f"Failed to get messages for conversation {conversation_id}: {e}"
            )
            return []

    async def update_conversation_metadata(
        self, conversation_id: UUID, metadata_updates: dict[str, Any]
    ) -> Conversation | None:
        """Update specific fields in conversation metadata.

        Args:
            conversation_id: Conversation UUID
            metadata_updates: Dictionary of metadata fields to update

        Returns:
            Updated conversation or None if not found
        """
        conversation = await self.get_by_id(conversation_id)
        if not conversation:
            return None

        metadata = conversation.metadata or {}
        metadata.update(metadata_updates)

        return await self.update_conversation(conversation_id, metadata=metadata)

    async def count_user_conversations(self, user_id: UUID) -> int:
        """Count total conversations for a user.

        Args:
            user_id: User UUID

        Returns:
            Number of conversations
        """
        return await self.count({"user_id": user_id})

    # Tag management methods

    async def add_tags(
        self, conversation_id: UUID, tags: list[str]
    ) -> Conversation | None:
        """Add tags to a conversation.

        Tags are validated, normalized, and deduplicated before adding.

        Args:
            conversation_id: Conversation UUID
            tags: List of tags to add

        Returns:
            Updated conversation or None if not found

        Raises:
            RepositoryError: If tag validation fails
        """
        try:
            # Get existing conversation
            conversation = await self.get_by_id(conversation_id)
            if not conversation:
                return None

            # Validate and merge tags
            existing_tags = conversation.tags or []
            merged_tags = merge_tags(existing_tags, tags)

            # Update conversation
            updated = await self.update(conversation_id, tags=merged_tags)

            # Invalidate cache
            if updated and self.cache:
                cache_key = build_conversation_key(str(conversation_id))
                self.cache.delete(cache_key)
                logger.debug(f"Added tags to conversation {conversation_id}")

            return updated

        except TagValidationError as e:
            logger.error(f"Tag validation failed: {e}")
            raise RepositoryError(f"Invalid tags: {str(e)}") from e
        except Exception as e:
            logger.error(f"Failed to add tags to conversation {conversation_id}: {e}")
            raise RepositoryError("Failed to add tags") from e

    async def remove_tag(
        self, conversation_id: UUID, tag: str
    ) -> Conversation | None:
        """Remove a specific tag from a conversation.

        Args:
            conversation_id: Conversation UUID
            tag: Tag to remove (case-insensitive)

        Returns:
            Updated conversation or None if not found
        """
        try:
            conversation = await self.get_by_id(conversation_id)
            if not conversation:
                return None

            # Normalize tag for comparison
            tag_normalized = tag.lower().strip()

            # Filter out the tag
            existing_tags = conversation.tags or []
            updated_tags = [t for t in existing_tags if t.lower() != tag_normalized]

            # Only update if tag was actually removed
            if len(updated_tags) == len(existing_tags):
                logger.debug(
                    f"Tag '{tag}' not found in conversation {conversation_id}"
                )
                return conversation

            # Update conversation
            updated = await self.update(conversation_id, tags=updated_tags)

            # Invalidate cache
            if updated and self.cache:
                cache_key = build_conversation_key(str(conversation_id))
                self.cache.delete(cache_key)
                logger.debug(
                    f"Removed tag '{tag}' from conversation {conversation_id}"
                )

            return updated

        except Exception as e:
            logger.error(
                f"Failed to remove tag from conversation {conversation_id}: {e}"
            )
            raise RepositoryError("Failed to remove tag") from e

    async def search_conversations(
        self,
        user_id: UUID,
        text_query: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[dict[str, Any]]:
        """Search conversations by text and/or tags with relevance scoring.

        Implements efficient search using:
        - Full-text search on conversation title and message content
        - Array operators for tag filtering
        - Relevance scoring based on match quality

        Args:
            user_id: User UUID to filter conversations
            text_query: Optional text search query (searches title and messages)
            tags: Optional list of tags to filter by (AND logic)
            limit: Maximum results to return
            offset: Number of results to skip

        Returns:
            List of conversation dictionaries with relevance scores

        Example:
            # Search for conversations tagged with "rna-seq" containing "melanoma"
            results = await repo.search_conversations(
                user_id=user_id,
                text_query="melanoma",
                tags=["rna-seq"]
            )
        """
        try:
            # Build base query
            stmt = (
                select(Conversation)
                .where(Conversation.user_id == user_id)
            )

            # Add tag filtering if provided
            if tags:
                # Validate tags
                normalized_tags = validate_tags(tags)
                # Use PostgreSQL array contains operator (@>)
                # This checks if conversation.tags contains all specified tags
                for tag in normalized_tags:
                    stmt = stmt.where(Conversation.tags.contains([tag]))

            # Add text search if provided
            if text_query and text_query.strip():
                # Build text search on title and messages
                # Use ILIKE for simple text search (can be upgraded to to_tsvector later)
                search_pattern = f"%{text_query.strip()}%"

                # Search in conversation title
                title_match = Conversation.title.ilike(search_pattern)

                # Search in message content (subquery)
                message_subquery = (
                    select(Message.conversation_id)
                    .where(Message.content.ilike(search_pattern))
                    .distinct()
                )

                # Combine: match either title or has matching messages
                stmt = stmt.where(
                    or_(
                        title_match,
                        Conversation.id.in_(message_subquery)
                    )
                )

            # Order by updated_at (most recent first) and apply pagination
            stmt = (
                stmt
                .order_by(desc(Conversation.updated_at))
                .offset(offset)
                .limit(limit)
            )

            # Execute query
            result = await self.session.execute(stmt)
            conversations = result.scalars().all()

            # Build response with metadata
            search_results = []
            for conv in conversations:
                # Calculate relevance score (simple version)
                relevance_score = 1.0

                # Boost score for tag matches
                if tags:
                    matching_tags = set(tags) & set(conv.tags or [])
                    relevance_score += len(matching_tags) * 0.2

                # Boost score for title matches
                if text_query and conv.title and text_query.lower() in conv.title.lower():
                    relevance_score += 0.5

                # Count messages (for metadata)
                message_count_stmt = (
                    select(func.count(Message.id))
                    .where(Message.conversation_id == conv.id)
                )
                message_count_result = await self.session.execute(message_count_stmt)
                message_count = message_count_result.scalar() or 0

                search_results.append({
                    "id": str(conv.id),
                    "user_id": str(conv.user_id),
                    "title": conv.title,
                    "tags": conv.tags or [],
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "metadata": conv.metadata,
                    "relevance_score": relevance_score,
                    "message_count": message_count,
                })

            # Sort by relevance score
            search_results.sort(key=lambda x: x["relevance_score"], reverse=True)

            logger.info(
                f"Search found {len(search_results)} conversations for user {user_id}"
            )
            return search_results

        except TagValidationError as e:
            logger.error(f"Tag validation failed in search: {e}")
            raise RepositoryError(f"Invalid tags: {str(e)}") from e
        except Exception as e:
            logger.error(f"Failed to search conversations: {e}")
            return []
