"""Search repository for managing search queries and results.

This repository handles CRUD operations for searches and search results
with optimized bulk insert for large result sets.
"""

import logging
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from quration.cache.redis_client import RedisClient, build_search_results_key
from quration.database.models import Search, SearchResult
from quration.repositories.base import BaseRepository, RepositoryError

logger = logging.getLogger(__name__)


class SearchRepository(BaseRepository[Search]):
    """Repository for search operations."""

    def __init__(self, session: AsyncSession, cache: RedisClient | None = None):
        """Initialize search repository.

        Args:
            session: Async database session
            cache: Optional Redis cache instance
        """
        super().__init__(Search, session, cache)

    async def save_search(
        self,
        conversation_id: UUID,
        user_id: UUID,
        query_spec: dict[str, Any],
        result_count: int | None = None,
        execution_time_ms: int | None = None,
    ) -> Search:
        """Save a search query.

        Args:
            conversation_id: Conversation UUID
            user_id: User UUID
            query_spec: Complete query specification (JSONB)
            result_count: Number of results returned
            execution_time_ms: Execution time in milliseconds

        Returns:
            Created search

        Raises:
            RepositoryError: If creation fails
        """
        try:
            search = await self.create(
                conversation_id=conversation_id,
                user_id=user_id,
                query_spec=query_spec,
                result_count=result_count,
                execution_time_ms=execution_time_ms,
            )

            logger.info(
                f"Saved search {search.id} for conversation {conversation_id}"
            )
            return search
        except Exception as e:
            logger.error(f"Failed to save search: {e}")
            raise RepositoryError("Failed to save search") from e

    async def get_search(
        self, search_id: UUID, use_cache: bool = True
    ) -> Search | None:
        """Get a search by ID with results.

        Args:
            search_id: Search UUID
            use_cache: Whether to use cache (default: True)

        Returns:
            Search with results or None if not found
        """
        # Try cache first
        if use_cache and self.cache:
            cache_key = build_search_results_key(str(search_id))
            cached_data = self.cache.get(cache_key)

            if cached_data:
                logger.debug(f"Cache hit for search {search_id}")
                # For now, skip cache reconstruction and load from DB
                pass

        # Load from database
        try:
            result = await self.session.execute(
                select(Search)
                .where(Search.id == search_id)
                .options(selectinload(Search.results))
            )
            search = result.scalar_one_or_none()

            # Cache for future use
            if search and use_cache and self.cache:
                cache_key = build_search_results_key(str(search_id))
                cache_data = {
                    "id": str(search.id),
                    "conversation_id": str(search.conversation_id),
                    "user_id": str(search.user_id),
                    "query_spec": search.query_spec,
                    "result_count": search.result_count,
                    "execution_time_ms": search.execution_time_ms,
                    "created_at": search.created_at.isoformat(),
                    "results": [
                        {
                            "id": str(res.id),
                            "dataset_id": res.dataset_id,
                            "rank": res.rank,
                            "metadata": res.metadata,
                        }
                        for res in search.results
                    ],
                }
                self.cache.set(
                    cache_key, cache_data, ttl=self.cache.config.ttl_search
                )
                logger.debug(f"Cached search results {search_id}")

            return search
        except Exception as e:
            logger.error(f"Failed to get search {search_id}: {e}")
            return None

    async def get_user_searches(
        self,
        user_id: UUID,
        limit: int = 50,
        offset: int = 0,
        conversation_id: UUID | None = None,
    ) -> Sequence[Search]:
        """Get searches for a user.

        Args:
            user_id: User UUID
            limit: Maximum number of searches to return
            offset: Number of searches to skip
            conversation_id: Optional filter by conversation

        Returns:
            List of searches ordered by created_at desc
        """
        try:
            stmt = (
                select(Search)
                .where(Search.user_id == user_id)
                .order_by(desc(Search.created_at))
                .offset(offset)
                .limit(limit)
            )

            if conversation_id:
                stmt = stmt.where(Search.conversation_id == conversation_id)

            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get searches for user {user_id}: {e}")
            return []

    async def get_conversation_searches(
        self, conversation_id: UUID, limit: int | None = None, offset: int = 0
    ) -> Sequence[Search]:
        """Get all searches for a conversation.

        Args:
            conversation_id: Conversation UUID
            limit: Maximum number of searches to return
            offset: Number of searches to skip

        Returns:
            List of searches ordered by created_at
        """
        try:
            stmt = (
                select(Search)
                .where(Search.conversation_id == conversation_id)
                .order_by(desc(Search.created_at))  # most recent first
                .offset(offset)
            )

            if limit is not None:
                stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(
                f"Failed to get searches for conversation {conversation_id}: {e}"
            )
            return []

    async def save_search_results(
        self, search_id: UUID, results: list[dict[str, Any]]
    ) -> list[SearchResult]:
        """Save search results in bulk.

        This method optimizes bulk insert for potentially 100+ results.

        Args:
            search_id: Search UUID
            results: List of result dictionaries with dataset_id, rank, metadata

        Returns:
            List of created search results

        Raises:
            RepositoryError: If bulk insert fails
        """
        try:
            search_results = [
                SearchResult(
                    search_id=search_id,
                    dataset_id=result["dataset_id"],
                    # Default rank to list position when the caller doesn't supply one,
                    # so results keep their incoming order.
                    rank=result.get("rank", idx),
                    metadata=result.get("metadata", {}),
                )
                for idx, result in enumerate(results)
            ]

            self.session.add_all(search_results)
            await self.session.flush()

            # Invalidate search cache
            if self.cache:
                cache_key = build_search_results_key(str(search_id))
                self.cache.delete(cache_key)

            logger.info(
                f"Saved {len(search_results)} results for search {search_id}"
            )
            return search_results
        except Exception as e:
            logger.error(f"Failed to save search results: {e}")
            raise RepositoryError("Failed to save search results") from e

    async def get_search_results(
        self, search_id: UUID, limit: int | None = None, offset: int = 0
    ) -> Sequence[SearchResult]:
        """Get results for a search.

        Args:
            search_id: Search UUID
            limit: Maximum number of results to return
            offset: Number of results to skip

        Returns:
            List of search results ordered by rank
        """
        try:
            stmt = (
                select(SearchResult)
                .where(SearchResult.search_id == search_id)
                .order_by(SearchResult.rank)
                .offset(offset)
            )

            if limit is not None:
                stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get results for search {search_id}: {e}")
            return []

    async def find_similar_searches(
        self, user_id: UUID, query_spec: dict[str, Any], limit: int = 5
    ) -> Sequence[Search]:
        """Find similar searches for semantic search (future implementation).

        This is a placeholder for future semantic search functionality
        using vector embeddings of query_spec.

        Args:
            user_id: User UUID
            query_spec: Query specification to find similar searches for
            limit: Maximum number of similar searches to return

        Returns:
            List of similar searches (currently returns recent searches)
        """
        # TODO: Implement semantic similarity using embeddings
        # For now, just return recent searches with similar structure

        logger.warning("find_similar_searches not yet fully implemented")

        # Fallback: return recent searches
        return await self.get_user_searches(user_id, limit=limit)

    async def count_user_searches(
        self, user_id: UUID, conversation_id: UUID | None = None
    ) -> int:
        """Count searches for a user.

        Args:
            user_id: User UUID
            conversation_id: Optional filter by conversation

        Returns:
            Number of searches
        """
        filter_dict = {"user_id": user_id}
        if conversation_id:
            filter_dict["conversation_id"] = conversation_id

        return await self.count(filter_dict)

    async def get_dataset_searches(
        self, dataset_id: str, user_id: UUID | None = None, limit: int = 10
    ) -> Sequence[Search]:
        """Get searches that returned a specific dataset.

        Args:
            dataset_id: Dataset ID (e.g., GSE12345)
            user_id: Optional filter by user
            limit: Maximum number of searches to return

        Returns:
            List of searches that included this dataset
        """
        try:
            # Join with search_results to find searches containing this dataset
            stmt = (
                select(Search)
                .join(SearchResult, Search.id == SearchResult.search_id)
                .where(SearchResult.dataset_id == dataset_id)
                .order_by(desc(Search.created_at))
                .limit(limit)
            )

            if user_id:
                stmt = stmt.where(Search.user_id == user_id)

            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to get searches for dataset {dataset_id}: {e}")
            return []
