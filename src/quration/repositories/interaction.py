"""Interaction repository for tracking user interactions with datasets.

This repository handles CRUD operations for user interactions (view, analyze, download)
with datasets across all conversations.
"""

import logging
from datetime import datetime
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from quration.cache.redis_client import RedisClient, build_user_interactions_key
from quration.database.models import UserInteraction
from quration.repositories.base import BaseRepository, RepositoryError

logger = logging.getLogger(__name__)


class InteractionRepository(BaseRepository[UserInteraction]):
    """Repository for user interaction operations."""

    def __init__(self, session: AsyncSession, cache: RedisClient | None = None):
        """Initialize interaction repository.

        Args:
            session: Async database session
            cache: Optional Redis cache instance
        """
        super().__init__(UserInteraction, session, cache)

    async def record_interaction(
        self,
        user_id: UUID,
        dataset_id: str,
        interaction_type: str,
        conversation_id: UUID | None = None,
        search_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UserInteraction:
        """Record a user interaction with a dataset.

        Args:
            user_id: User UUID
            dataset_id: Dataset ID (e.g., GSE12345)
            interaction_type: Type of interaction (view, analyze, download)
            conversation_id: Optional conversation UUID
            search_id: Optional search UUID
            metadata: Optional metadata dictionary

        Returns:
            Created interaction

        Raises:
            RepositoryError: If creation fails
        """
        try:
            interaction = await self.create(
                user_id=user_id,
                dataset_id=dataset_id,
                interaction_type=interaction_type,
                conversation_id=conversation_id,
                search_id=search_id,
                metadata=metadata or {},
            )

            # Invalidate cache for this user-dataset combination
            if self.cache:
                cache_key = build_user_interactions_key(str(user_id), dataset_id)
                self.cache.delete(cache_key)

            logger.info(
                f"Recorded {interaction_type} interaction for user {user_id} "
                f"on dataset {dataset_id}"
            )
            return interaction
        except Exception as e:
            logger.error(f"Failed to record interaction: {e}")
            raise RepositoryError("Failed to record interaction") from e

    async def get_user_interactions(
        self,
        user_id: UUID,
        dataset_id: str | None = None,
        interaction_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[UserInteraction]:
        """Get interactions for a user.

        Args:
            user_id: User UUID
            dataset_id: Optional filter by dataset
            interaction_type: Optional filter by interaction type
            limit: Maximum number of interactions to return
            offset: Number of interactions to skip

        Returns:
            List of interactions ordered by created_at desc
        """
        try:
            stmt = (
                select(UserInteraction)
                .where(UserInteraction.user_id == user_id)
                .order_by(desc(UserInteraction.created_at))
                .offset(offset)
                .limit(limit)
            )

            if dataset_id:
                stmt = stmt.where(UserInteraction.dataset_id == dataset_id)

            if interaction_type:
                stmt = stmt.where(UserInteraction.interaction_type == interaction_type)

            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get interactions for user {user_id}: {e}")
            return []

    async def get_dataset_interaction_history(
        self,
        dataset_id: str,
        user_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[UserInteraction]:
        """Get interaction history for a dataset.

        Args:
            dataset_id: Dataset ID
            user_id: Optional filter by user
            limit: Maximum number of interactions to return
            offset: Number of interactions to skip

        Returns:
            List of interactions ordered by created_at desc
        """
        try:
            stmt = (
                select(UserInteraction)
                .where(UserInteraction.dataset_id == dataset_id)
                .order_by(desc(UserInteraction.created_at))
                .offset(offset)
                .limit(limit)
            )

            if user_id:
                stmt = stmt.where(UserInteraction.user_id == user_id)

            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(
                f"Failed to get interaction history for dataset {dataset_id}: {e}"
            )
            return []

    async def has_user_viewed_dataset(
        self, user_id: UUID, dataset_id: str
    ) -> tuple[bool, UserInteraction | None]:
        """Check if user has viewed a dataset.

        Args:
            user_id: User UUID
            dataset_id: Dataset ID

        Returns:
            Tuple of (has_viewed, most_recent_interaction)
        """
        try:
            stmt = (
                select(UserInteraction)
                .where(UserInteraction.user_id == user_id)
                .where(UserInteraction.dataset_id == dataset_id)
                .where(UserInteraction.interaction_type == "view")
                .order_by(desc(UserInteraction.created_at))
                .limit(1)
            )

            result = await self.session.execute(stmt)
            interaction = result.scalar_one_or_none()

            return (interaction is not None, interaction)
        except Exception as e:
            logger.error(
                f"Failed to check if user {user_id} viewed dataset {dataset_id}: {e}"
            )
            return (False, None)

    async def get_user_viewed_datasets(
        self, user_id: UUID, limit: int = 100, offset: int = 0
    ) -> Sequence[str]:
        """Get list of datasets user has viewed.

        Args:
            user_id: User UUID
            limit: Maximum number of dataset IDs to return
            offset: Number of dataset IDs to skip

        Returns:
            List of unique dataset IDs ordered by most recent interaction
        """
        try:
            # Get distinct dataset IDs for view interactions
            stmt = (
                select(UserInteraction.dataset_id)
                .where(UserInteraction.user_id == user_id)
                .where(UserInteraction.interaction_type == "view")
                .order_by(desc(UserInteraction.created_at))
                .distinct()
                .offset(offset)
                .limit(limit)
            )

            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get viewed datasets for user {user_id}: {e}")
            return []

    async def get_interaction_stats(
        self, user_id: UUID
    ) -> dict[str, Any]:
        """Get interaction statistics for a user.

        Args:
            user_id: User UUID

        Returns:
            Dictionary with interaction statistics
        """
        try:
            # Count by interaction type
            view_count = await self.count({
                "user_id": user_id,
                "interaction_type": "view"
            })
            analyze_count = await self.count({
                "user_id": user_id,
                "interaction_type": "analyze"
            })
            download_count = await self.count({
                "user_id": user_id,
                "interaction_type": "download"
            })

            # Get unique datasets count
            stmt = (
                select(UserInteraction.dataset_id)
                .where(UserInteraction.user_id == user_id)
                .distinct()
            )
            result = await self.session.execute(stmt)
            unique_datasets = len(result.scalars().all())

            return {
                "total_interactions": view_count + analyze_count + download_count,
                "view_count": view_count,
                "analyze_count": analyze_count,
                "download_count": download_count,
                "unique_datasets": unique_datasets,
            }
        except Exception as e:
            logger.error(f"Failed to get interaction stats for user {user_id}: {e}")
            return {
                "total_interactions": 0,
                "view_count": 0,
                "analyze_count": 0,
                "download_count": 0,
                "unique_datasets": 0,
            }

    async def get_conversation_interactions(
        self, conversation_id: UUID, limit: int | None = None, offset: int = 0
    ) -> Sequence[UserInteraction]:
        """Get all interactions for a conversation.

        Args:
            conversation_id: Conversation UUID
            limit: Maximum number of interactions to return
            offset: Number of interactions to skip

        Returns:
            List of interactions ordered by created_at
        """
        try:
            stmt = (
                select(UserInteraction)
                .where(UserInteraction.conversation_id == conversation_id)
                .order_by(UserInteraction.created_at)
                .offset(offset)
            )

            if limit is not None:
                stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(
                f"Failed to get interactions for conversation {conversation_id}: {e}"
            )
            return []

    async def get_recent_interactions(
        self,
        user_id: UUID,
        dataset_id: str,
        limit: int = 5,
    ) -> Sequence[UserInteraction]:
        """Get recent interactions for a user with a specific dataset.

        Args:
            user_id: User UUID
            dataset_id: Dataset ID
            limit: Maximum number of interactions to return

        Returns:
            List of recent interactions ordered by created_at desc
        """
        # Check cache first
        if self.cache:
            cache_key = build_user_interactions_key(str(user_id), dataset_id)
            cached_data = self.cache.get(cache_key)

            if cached_data:
                logger.debug(
                    f"Cache hit for user {user_id} interactions with {dataset_id}"
                )
                # For now, skip cache reconstruction and load from DB
                pass

        try:
            stmt = (
                select(UserInteraction)
                .where(UserInteraction.user_id == user_id)
                .where(UserInteraction.dataset_id == dataset_id)
                .order_by(desc(UserInteraction.created_at))
                .limit(limit)
            )

            result = await self.session.execute(stmt)
            interactions = result.scalars().all()

            # Cache for future use
            if self.cache and interactions:
                cache_key = build_user_interactions_key(str(user_id), dataset_id)
                cache_data = [
                    {
                        "id": str(inter.id),
                        "interaction_type": inter.interaction_type,
                        "created_at": inter.created_at.isoformat(),
                        "metadata": inter.metadata,
                    }
                    for inter in interactions
                ]
                # Short TTL since interactions are frequently updated
                self.cache.set(cache_key, cache_data, ttl=3600)  # 1 hour

            return interactions
        except Exception as e:
            logger.error(
                f"Failed to get recent interactions for user {user_id} "
                f"with dataset {dataset_id}: {e}"
            )
            return []

    async def get_recalled_datasets(
        self,
        user_id: UUID,
        limit: int = 10,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get recently viewed datasets across all conversations.

        Returns datasets ordered by most recent interaction, with aggregated
        interaction information including conversation context.

        Args:
            user_id: User UUID
            limit: Maximum number of datasets to return
            since: Optional datetime filter for interactions after this time

        Returns:
            List of dictionaries with dataset and interaction info
        """
        try:
            from sqlalchemy import func, and_
            from quration.database.models import Conversation

            # Build subquery to get most recent interaction per dataset
            subquery = (
                select(
                    UserInteraction.dataset_id,
                    func.max(UserInteraction.created_at).label("last_interaction_at"),
                    func.count(UserInteraction.id).label("interaction_count"),
                )
                .where(UserInteraction.user_id == user_id)
            )

            if since:
                subquery = subquery.where(UserInteraction.created_at >= since)

            subquery = (
                subquery.group_by(UserInteraction.dataset_id)
                .order_by(desc(func.max(UserInteraction.created_at)))
                .limit(limit)
                .subquery()
            )

            # Join with interactions to get full details and conversation info
            stmt = (
                select(
                    UserInteraction,
                    Conversation.title.label("conversation_title"),
                    subquery.c.interaction_count,
                )
                .join(
                    subquery,
                    and_(
                        UserInteraction.dataset_id == subquery.c.dataset_id,
                        UserInteraction.created_at == subquery.c.last_interaction_at,
                    ),
                )
                .outerjoin(
                    Conversation,
                    UserInteraction.conversation_id == Conversation.id,
                )
                .where(UserInteraction.user_id == user_id)
                .order_by(desc(UserInteraction.created_at))
            )

            result = await self.session.execute(stmt)
            rows = result.all()

            datasets = []
            for row in rows:
                interaction, conv_title, interaction_count = row
                datasets.append({
                    "dataset_id": interaction.dataset_id,
                    "last_interaction_at": interaction.created_at,
                    "interaction_count": interaction_count,
                    "last_interaction_type": interaction.interaction_type,
                    "conversation_id": interaction.conversation_id,
                    "conversation_title": conv_title,
                })

            logger.info(
                f"Retrieved {len(datasets)} recalled datasets for user {user_id}"
            )
            return datasets

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
            from sqlalchemy import func
            from quration.database.models import Conversation

            # Aggregate counts/first-seen in SQL (portable — no array_agg, which is
            # Postgres-only and breaks on SQLite).
            stmt = (
                select(
                    Conversation.id.label("conversation_id"),
                    Conversation.title.label("conversation_title"),
                    func.min(UserInteraction.created_at).label("first_interaction_at"),
                    func.count(UserInteraction.id).label("interaction_count"),
                )
                .join(
                    UserInteraction,
                    UserInteraction.conversation_id == Conversation.id,
                )
                .where(UserInteraction.dataset_id == dataset_id)
                .where(UserInteraction.user_id == user_id)
                .group_by(Conversation.id, Conversation.title)
                .order_by(desc(func.min(UserInteraction.created_at)))
            )

            result = await self.session.execute(stmt)
            rows = result.all()

            # Distinct interaction types per conversation, gathered in Python (portable
            # across SQLite/Postgres). One extra query, not N+1.
            types_stmt = (
                select(
                    UserInteraction.conversation_id,
                    UserInteraction.interaction_type,
                )
                .where(UserInteraction.dataset_id == dataset_id)
                .where(UserInteraction.user_id == user_id)
                .distinct()
            )
            types_by_conv: dict[Any, list] = {}
            for conv_id, itype in (await self.session.execute(types_stmt)).all():
                if itype is not None:
                    types_by_conv.setdefault(conv_id, []).append(itype)

            conversations = []
            for row in rows:
                conversations.append({
                    "conversation_id": row.conversation_id,
                    "conversation_title": row.conversation_title,
                    "first_interaction_at": row.first_interaction_at,
                    "interaction_count": row.interaction_count,
                    "interaction_types": types_by_conv.get(row.conversation_id, []),
                })

            logger.info(
                f"Found {len(conversations)} conversations for dataset {dataset_id}"
            )
            return conversations

        except Exception as e:
            logger.error(
                f"Failed to get conversations for dataset {dataset_id}: {e}"
            )
            return []
