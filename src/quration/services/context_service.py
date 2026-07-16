"""Context service for high-level context memory operations.

This service combines multiple repositories to provide comprehensive
context restoration and management functionality.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from quration.cache.redis_client import RedisClient
from quration.database.models import Conversation, Message, Search, UserInteraction
from quration.repositories.conversation import ConversationRepository
from quration.repositories.interaction import InteractionRepository
from quration.repositories.search import SearchRepository
from quration.repositories.user import UserRepository

logger = logging.getLogger(__name__)


class ContextService:
    """High-level service for context memory operations.

    This service orchestrates multiple repositories to provide
    comprehensive context restoration and management.
    """

    def __init__(self, session: AsyncSession, cache: RedisClient | None = None):
        """Initialize context service.

        Args:
            session: Async database session
            cache: Optional Redis cache instance
        """
        self.session = session
        self.cache = cache

        # Initialize repositories
        self.conversation_repo = ConversationRepository(session, cache)
        self.search_repo = SearchRepository(session, cache)
        self.user_repo = UserRepository(session, cache)
        self.interaction_repo = InteractionRepository(session, cache)

    async def get_conversation_context(
        self, conversation_id: UUID, use_cache: bool = True
    ) -> dict[str, Any] | None:
        """Get full conversation context with graceful degradation.

        This method assembles complete conversation context from multiple sources:
        - Conversation metadata and messages
        - All searches and their results
        - User interactions within this conversation

        If cache is unavailable, falls back to database.
        Returns partial results if some components fail.

        Args:
            conversation_id: Conversation UUID
            use_cache: Whether to use cache (default: True)

        Returns:
            Dictionary with complete or partial context, None if conversation not found
        """
        context = {
            "conversation": None,
            "messages": [],
            "searches": [],
            "interactions": [],
            "warnings": [],  # Track any partial failures
        }

        try:
            # Get conversation with messages
            # If cache fails, this will automatically fall back to database
            conversation = await self.conversation_repo.get_conversation(
                conversation_id, use_cache=use_cache
            )

            if not conversation:
                logger.warning(f"Conversation {conversation_id} not found")
                return None

            # Build conversation data
            context["conversation"] = {
                "id": str(conversation.id),
                "user_id": str(conversation.user_id),
                "title": conversation.title,
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
                "metadata": conversation.metadata,
            }

            context["messages"] = [
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat(),
                    "metadata": msg.metadata,
                }
                for msg in conversation.messages
            ]

        except Exception as e:
            logger.error(f"Failed to get conversation data: {e}")
            return None

        # Get searches (non-critical, continue if fails)
        try:
            searches = await self.search_repo.get_conversation_searches(
                conversation_id
            )
            context["searches"] = [
                {
                    "id": str(search.id),
                    "query_spec": search.query_spec,
                    "result_count": search.result_count,
                    "execution_time_ms": search.execution_time_ms,
                    "created_at": search.created_at.isoformat(),
                }
                for search in searches
            ]
        except Exception as e:
            logger.warning(f"Failed to get searches, continuing with partial context: {e}")
            context["warnings"].append("searches_unavailable")

        # Get interactions (non-critical, continue if fails)
        try:
            interactions = await self.interaction_repo.get_conversation_interactions(
                conversation_id
            )
            context["interactions"] = [
                {
                    "id": str(inter.id),
                    "dataset_id": inter.dataset_id,
                    "interaction_type": inter.interaction_type,
                    "created_at": inter.created_at.isoformat(),
                    "metadata": inter.metadata,
                }
                for inter in interactions
            ]
        except Exception as e:
            logger.warning(f"Failed to get interactions, continuing with partial context: {e}")
            context["warnings"].append("interactions_unavailable")

        # Log context retrieval status
        warnings_str = f" (warnings: {', '.join(context['warnings'])})" if context["warnings"] else ""
        logger.info(
            f"Retrieved context for conversation {conversation_id}: "
            f"{len(context['messages'])} messages, "
            f"{len(context['searches'])} searches, "
            f"{len(context['interactions'])} interactions{warnings_str}"
        )

        return context

    async def restore_conversation_state(
        self, conversation_id: UUID
    ) -> dict[str, Any] | None:
        """Restore complete conversation state for UI rendering.

        This method retrieves all data needed to restore a conversation,
        including search results and interaction history.

        Args:
            conversation_id: Conversation UUID

        Returns:
            Dictionary with complete state or None if conversation not found
        """
        context = await self.get_conversation_context(conversation_id)

        if not context:
            return None

        # Enrich searches with their results
        for search_dict in context["searches"]:
            search_id = UUID(search_dict["id"])
            results = await self.search_repo.get_search_results(search_id)

            search_dict["results"] = [
                {
                    "dataset_id": res.dataset_id,
                    "rank": res.rank,
                    "metadata": res.metadata,
                }
                for res in results
            ]

        return context

    async def create_conversation_with_message(
        self,
        user_id: UUID,
        role: str,
        content: str,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Conversation, Message]:
        """Create a new conversation with an initial message.

        Args:
            user_id: User UUID
            role: Message role (user, assistant, system)
            content: Message content
            title: Optional conversation title
            metadata: Optional conversation metadata

        Returns:
            Tuple of (conversation, message)
        """
        # Create conversation
        conversation = await self.conversation_repo.create_conversation(
            user_id=user_id,
            title=title,
            metadata=metadata,
        )

        # Add initial message
        message = await self.conversation_repo.add_message(
            conversation_id=conversation.id,
            role=role,
            content=content,
        )

        await self.session.commit()

        logger.info(
            f"Created conversation {conversation.id} with initial message"
        )

        return conversation, message

    async def save_search_with_results(
        self,
        conversation_id: UUID,
        user_id: UUID,
        query_spec: dict[str, Any],
        results: list[dict[str, Any]],
        execution_time_ms: int | None = None,
    ) -> Search:
        """Save a search with its results in a single transaction.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID
            query_spec: Complete query specification
            results: List of search results
            execution_time_ms: Optional execution time

        Returns:
            Created search with results
        """
        # Save search
        search = await self.search_repo.save_search(
            conversation_id=conversation_id,
            user_id=user_id,
            query_spec=query_spec,
            result_count=len(results),
            execution_time_ms=execution_time_ms,
        )

        # Save results
        if results:
            await self.search_repo.save_search_results(
                search_id=search.id,
                results=results,
            )

        await self.session.commit()

        logger.info(
            f"Saved search {search.id} with {len(results)} results"
        )

        return search

    async def track_dataset_interaction(
        self,
        user_id: UUID,
        dataset_id: str,
        interaction_type: str,
        conversation_id: UUID | None = None,
        search_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UserInteraction:
        """Track a user interaction with a dataset.

        Args:
            user_id: User UUID
            dataset_id: Dataset ID
            interaction_type: Type of interaction (view, analyze, download)
            conversation_id: Optional conversation UUID
            search_id: Optional search UUID
            metadata: Optional metadata

        Returns:
            Created interaction
        """
        interaction = await self.interaction_repo.record_interaction(
            user_id=user_id,
            dataset_id=dataset_id,
            interaction_type=interaction_type,
            conversation_id=conversation_id,
            search_id=search_id,
            metadata=metadata,
        )

        await self.session.commit()

        return interaction

    async def get_user_context_summary(
        self, user_id: UUID
    ) -> dict[str, Any]:
        """Get a summary of user's context memory.

        Args:
            user_id: User UUID

        Returns:
            Dictionary with user context summary
        """
        try:
            # Get conversation count
            conversation_count = await self.conversation_repo.count_user_conversations(
                user_id
            )

            # Get search count
            search_count = await self.search_repo.count_user_searches(user_id)

            # Get interaction stats
            interaction_stats = await self.interaction_repo.get_interaction_stats(
                user_id
            )

            # Get preference count
            preference_count = await self.user_repo.count_user_preferences(user_id)

            # Get recent conversations
            recent_conversations = await self.conversation_repo.list_user_conversations(
                user_id=user_id,
                limit=5,
            )

            return {
                "user_id": str(user_id),
                "statistics": {
                    "total_conversations": conversation_count,
                    "total_searches": search_count,
                    "total_interactions": interaction_stats["total_interactions"],
                    "unique_datasets_viewed": interaction_stats["unique_datasets"],
                    "saved_preferences": preference_count,
                },
                "recent_conversations": [
                    {
                        "id": str(conv.id),
                        "title": conv.title,
                        "updated_at": conv.updated_at.isoformat(),
                    }
                    for conv in recent_conversations
                ],
                "interaction_breakdown": {
                    "views": interaction_stats["view_count"],
                    "analyses": interaction_stats["analyze_count"],
                    "downloads": interaction_stats["download_count"],
                },
            }
        except Exception as e:
            logger.error(f"Failed to get user context summary for {user_id}: {e}")
            return {
                "user_id": str(user_id),
                "error": str(e),
            }

    async def get_dataset_history(
        self, dataset_id: str, user_id: UUID
    ) -> dict[str, Any]:
        """Get user's history with a specific dataset.

        Args:
            dataset_id: Dataset ID
            user_id: User UUID

        Returns:
            Dictionary with dataset interaction history
        """
        try:
            # Get interactions
            interactions = await self.interaction_repo.get_dataset_interaction_history(
                dataset_id=dataset_id,
                user_id=user_id,
            )

            # Get searches that returned this dataset
            searches = await self.search_repo.get_dataset_searches(
                dataset_id=dataset_id,
                user_id=user_id,
            )

            # Check if viewed
            has_viewed, first_view = await self.interaction_repo.has_user_viewed_dataset(
                user_id=user_id,
                dataset_id=dataset_id,
            )

            return {
                "dataset_id": dataset_id,
                "has_viewed": has_viewed,
                "first_viewed_at": (
                    first_view.created_at.isoformat() if first_view else None
                ),
                "interaction_count": len(interactions),
                "interactions": [
                    {
                        "type": inter.interaction_type,
                        "created_at": inter.created_at.isoformat(),
                        "conversation_id": str(inter.conversation_id) if inter.conversation_id else None,
                    }
                    for inter in interactions
                ],
                "related_searches": [
                    {
                        "id": str(search.id),
                        "conversation_id": str(search.conversation_id),
                        "created_at": search.created_at.isoformat(),
                    }
                    for search in searches
                ],
            }
        except Exception as e:
            logger.error(f"Failed to get dataset history for {dataset_id}: {e}")
            return {
                "dataset_id": dataset_id,
                "error": str(e),
            }

    async def get_recalled_datasets(
        self,
        user_id: UUID,
        limit: int = 10,
        since: Any | None = None,
    ) -> list[dict[str, Any]]:
        """Get recently viewed datasets across all conversations.

        This method enables "show me that dataset I looked at last week" queries
        by retrieving datasets the user has interacted with, ordered by most recent.

        Args:
            user_id: User UUID
            limit: Maximum number of datasets to return
            since: Optional datetime filter for interactions after this time

        Returns:
            List of datasets with interaction context
        """
        try:
            return await self.interaction_repo.get_recalled_datasets(
                user_id=user_id,
                limit=limit,
                since=since,
            )
        except Exception as e:
            logger.error(f"Failed to get recalled datasets for user {user_id}: {e}")
            return []

    async def get_dataset_conversations(
        self,
        dataset_id: str,
        user_id: UUID,
    ) -> list[dict[str, Any]]:
        """Get all conversations where user interacted with a dataset.

        Args:
            dataset_id: Dataset ID
            user_id: User UUID

        Returns:
            List of conversations with interaction details
        """
        try:
            return await self.interaction_repo.get_dataset_conversations(
                dataset_id=dataset_id,
                user_id=user_id,
            )
        except Exception as e:
            logger.error(
                f"Failed to get conversations for dataset {dataset_id}: {e}"
            )
            return []
