"""User repository for managing users and preferences.

This repository handles CRUD operations for users and their preferences
with integrated caching for fast retrieval.
"""

import logging
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from quration.cache.redis_client import RedisClient, build_user_preferences_key
from quration.database.models import User, UserPreference
from quration.repositories.base import BaseRepository, RepositoryError

logger = logging.getLogger(__name__)


class UserRepository(BaseRepository[User]):
    """Repository for user operations."""

    def __init__(self, session: AsyncSession, cache: RedisClient | None = None):
        """Initialize user repository.

        Args:
            session: Async database session
            cache: Optional Redis cache instance
        """
        super().__init__(User, session, cache)

    async def create_user(self, external_id: str) -> User:
        """Create a new user.

        Args:
            external_id: External user identifier (e.g., from auth provider)

        Returns:
            Created user

        Raises:
            RepositoryError: If creation fails
        """
        try:
            user = await self.create(external_id=external_id)
            logger.info(f"Created user {user.id} with external ID {external_id}")
            return user
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            raise RepositoryError("Failed to create user") from e

    async def get_user(self, user_id: UUID) -> User | None:
        """Get a user by ID.

        Args:
            user_id: User UUID

        Returns:
            User or None if not found
        """
        return await self.get_by_id(user_id)

    async def get_user_by_external_id(self, external_id: str) -> User | None:
        """Get a user by external ID.

        Args:
            external_id: External user identifier

        Returns:
            User or None if not found
        """
        return await self.find_one({"external_id": external_id})

    async def get_or_create_user(self, external_id: str) -> User:
        """Get existing user or create if not exists.

        Args:
            external_id: External user identifier

        Returns:
            Existing or newly created user

        Raises:
            RepositoryError: If creation fails
        """
        user = await self.get_user_by_external_id(external_id)

        if user is None:
            user = await self.create_user(external_id)

        return user

    async def update_user(self, user_id: UUID, **kwargs: Any) -> User | None:
        """Update a user.

        Args:
            user_id: User UUID
            **kwargs: Fields to update

        Returns:
            Updated user or None if not found
        """
        return await self.update(user_id, **kwargs)

    # Preference operations

    async def get_user_preferences(
        self, user_id: UUID, use_cache: bool = True
    ) -> Sequence[UserPreference]:
        """Get all preferences for a user.

        Args:
            user_id: User UUID
            use_cache: Whether to use cache (default: True)

        Returns:
            List of user preferences
        """
        # Try cache first
        if use_cache and self.cache:
            cache_key = build_user_preferences_key(str(user_id))
            cached_data = self.cache.get(cache_key)

            if cached_data:
                logger.debug(f"Cache hit for user {user_id} preferences")
                # For now, skip cache reconstruction and load from DB
                pass

        # Load from database
        try:
            stmt = (
                select(UserPreference)
                .where(UserPreference.user_id == user_id)
                .order_by(desc(UserPreference.updated_at))
            )

            result = await self.session.execute(stmt)
            preferences = result.scalars().all()

            # Cache for future use
            if use_cache and self.cache:
                cache_key = build_user_preferences_key(str(user_id))
                cache_data = [
                    {
                        "id": str(pref.id),
                        "preference_type": pref.preference_type,
                        "preference_value": pref.preference_value,
                        "confidence_score": pref.confidence_score,
                        "created_at": pref.created_at.isoformat(),
                        "updated_at": pref.updated_at.isoformat(),
                    }
                    for pref in preferences
                ]
                self.cache.set(
                    cache_key, cache_data, ttl=self.cache.config.ttl_preferences
                )
                logger.debug(f"Cached preferences for user {user_id}")

            return preferences
        except Exception as e:
            logger.error(f"Failed to get preferences for user {user_id}: {e}")
            return []

    async def save_preference(
        self,
        user_id: UUID,
        preference_type: str,
        preference_value: Any,
        confidence_score: float | None = None,
        evidence: dict[str, Any] | None = None,
        is_accepted: bool = True,
    ) -> UserPreference:
        """Save a user preference.

        Args:
            user_id: User UUID
            preference_type: Type of preference (e.g., "organism", "platform")
            preference_value: Preference value as JSON
            confidence_score: Optional confidence score (0.0 to 1.0)
            evidence: Optional evidence dictionary
            is_accepted: Whether the preference is accepted (default: True)

        Returns:
            Created preference

        Raises:
            RepositoryError: If creation fails
        """
        try:
            preference = UserPreference(
                user_id=user_id,
                preference_type=preference_type,
                preference_value=preference_value,
                confidence_score=confidence_score,
                evidence=evidence,
                is_accepted=is_accepted,
            )
            self.session.add(preference)
            await self.session.flush()
            await self.session.refresh(preference)

            # Invalidate cache
            if self.cache:
                cache_key = build_user_preferences_key(str(user_id))
                self.cache.delete(cache_key)

            logger.info(
                f"Saved preference {preference.id} for user {user_id}"
            )
            return preference
        except Exception as e:
            logger.error(f"Failed to save preference: {e}")
            raise RepositoryError("Failed to save preference") from e

    async def get_preference_by_type(
        self, user_id: UUID, preference_type: str
    ) -> UserPreference | None:
        """Get a user preference by type.

        Args:
            user_id: User UUID
            preference_type: Type of preference

        Returns:
            User preference or None if not found
        """
        try:
            stmt = (
                select(UserPreference)
                .where(UserPreference.user_id == user_id)
                .where(UserPreference.preference_type == preference_type)
                .order_by(desc(UserPreference.updated_at))
                .limit(1)
            )

            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(
                f"Failed to get preference {preference_type} for user {user_id}: {e}"
            )
            return None

    async def get_preference(self, preference_id: UUID) -> UserPreference | None:
        """Fetch a single preference by its id (or None if it doesn't exist)."""
        try:
            stmt = select(UserPreference).where(UserPreference.id == preference_id)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get preference {preference_id}: {e}")
            return None

    async def get_preferences_by_type(
        self, user_id: UUID, preference_type: str
    ) -> Sequence[UserPreference]:
        """All of a user's preferences of a given type (newest first)."""
        try:
            stmt = (
                select(UserPreference)
                .where(UserPreference.user_id == user_id)
                .where(UserPreference.preference_type == preference_type)
                .order_by(desc(UserPreference.updated_at))
            )
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(
                f"Failed to get preferences of type {preference_type} for user {user_id}: {e}"
            )
            return []

    async def update_preference(
        self,
        preference_id: UUID,
        preference_value: Any = None,
        confidence_score: float | None = None,
        evidence: dict[str, Any] | None = None,
        is_accepted: bool | None = None,
    ) -> UserPreference | None:
        """Update a user preference.

        Args:
            preference_id: Preference UUID
            preference_value: New preference value (if provided)
            confidence_score: New confidence score (if provided)
            evidence: New evidence dictionary to merge/set (if provided)
            is_accepted: New is_accepted value (if provided)

        Returns:
            Updated preference or None if not found
        """
        try:
            stmt = select(UserPreference).where(UserPreference.id == preference_id)
            result = await self.session.execute(stmt)
            preference = result.scalar_one_or_none()

            if not preference:
                return None

            if preference_value is not None:
                preference.preference_value = preference_value
            if confidence_score is not None:
                preference.confidence_score = confidence_score
            if evidence is not None:
                if isinstance(preference.evidence, dict) and isinstance(evidence, dict):
                    merged = dict(preference.evidence)
                    merged.update(evidence)
                    preference.evidence = merged
                else:
                    preference.evidence = evidence
            if is_accepted is not None:
                preference.is_accepted = is_accepted

            await self.session.flush()
            await self.session.refresh(preference)

            # Invalidate cache
            if self.cache:
                cache_key = build_user_preferences_key(str(preference.user_id))
                self.cache.delete(cache_key)

            logger.debug(f"Updated preference {preference_id}")
            return preference
        except Exception as e:
            logger.error(f"Failed to update preference {preference_id}: {e}")
            return None

    async def accept_preference(self, preference_id: UUID) -> UserPreference | None:
        """Accept a suggested preference, boosting its confidence score."""
        try:
            stmt = select(UserPreference).where(UserPreference.id == preference_id)
            result = await self.session.execute(stmt)
            preference = result.scalar_one_or_none()

            if not preference:
                return None

            preference.is_accepted = True
            # Boost confidence score when accepted
            if preference.confidence_score is not None:
                preference.confidence_score = min(1.0, max(0.8, preference.confidence_score + 0.1))
            else:
                preference.confidence_score = 0.8

            await self.session.flush()
            await self.session.refresh(preference)

            # Invalidate cache
            if self.cache:
                cache_key = build_user_preferences_key(str(preference.user_id))
                self.cache.delete(cache_key)

            return preference
        except Exception as e:
            logger.error(f"Failed to accept preference {preference_id}: {e}")
            return None

    async def delete_preference(self, preference_id: UUID) -> bool:
        """Delete a user preference.

        Args:
            preference_id: Preference UUID

        Returns:
            True if deleted successfully
        """
        try:
            # Get preference first to find user_id for cache invalidation
            stmt = select(UserPreference).where(UserPreference.id == preference_id)
            result = await self.session.execute(stmt)
            preference = result.scalar_one_or_none()

            if not preference:
                return False

            user_id = preference.user_id

            # Delete preference
            await self.session.delete(preference)
            await self.session.flush()

            # Invalidate cache
            if self.cache:
                cache_key = build_user_preferences_key(str(user_id))
                self.cache.delete(cache_key)

            logger.debug(f"Deleted preference {preference_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete preference {preference_id}: {e}")
            return False

    async def get_high_confidence_preferences(
        self, user_id: UUID, min_confidence: float = 0.7
    ) -> Sequence[UserPreference]:
        """Get high-confidence preferences for a user.

        Args:
            user_id: User UUID
            min_confidence: Minimum confidence score threshold

        Returns:
            List of high-confidence preferences
        """
        try:
            stmt = (
                select(UserPreference)
                .where(UserPreference.user_id == user_id)
                .where(UserPreference.confidence_score >= min_confidence)
                .order_by(desc(UserPreference.confidence_score))
            )

            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            logger.error(
                f"Failed to get high-confidence preferences for user {user_id}: {e}"
            )
            return []

    async def count_user_preferences(self, user_id: UUID) -> int:
        """Count preferences for a user.

        Args:
            user_id: User UUID

        Returns:
            Number of preferences
        """
        try:
            stmt = (
                select(UserPreference)
                .where(UserPreference.user_id == user_id)
            )
            result = await self.session.execute(stmt)
            return len(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to count preferences for user {user_id}: {e}")
            return 0

    async def analyze_search_patterns(
        self, user_id: UUID, limit: int = 50
    ) -> dict[str, dict[str, Any]]:
        """Analyze user's search patterns to identify potential preferences.

        Args:
            user_id: User UUID
            limit: Number of recent searches to analyze

        Returns:
            Dictionary of pattern analysis by category
        """
        from collections import Counter
        from quration.database.models import Search

        try:
            # Get recent searches
            stmt = (
                select(Search)
                .where(Search.user_id == user_id)
                .order_by(desc(Search.created_at))
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            searches = result.scalars().all()

            if not searches:
                return {}

            # Analyze patterns
            organism_counts = Counter()
            platform_counts = Counter()
            disease_counts = Counter()

            for search in searches:
                query_spec = search.query_spec or {}

                # Extract organisms
                if "organism" in query_spec:
                    organisms = query_spec["organism"]
                    if isinstance(organisms, list):
                        organism_counts.update(organisms)
                    elif isinstance(organisms, str):
                        organism_counts[organisms] += 1

                # Extract platforms
                if "platform" in query_spec:
                    platforms = query_spec["platform"]
                    if isinstance(platforms, list):
                        platform_counts.update(platforms)
                    elif isinstance(platforms, str):
                        platform_counts[platforms] += 1

                # Extract disease areas
                if "disease_area" in query_spec:
                    diseases = query_spec["disease_area"]
                    if isinstance(diseases, list):
                        disease_counts.update(diseases)
                    elif isinstance(diseases, str):
                        disease_counts[diseases] += 1

            total_searches = len(searches)
            patterns = {}

            # Build organism pattern. `value`/`confidence` summarize the dominant item
            # (top value + its share of searches); `values`/`counts`/`frequency` retain
            # the fuller breakdown.
            if organism_counts:
                top_organisms = organism_counts.most_common(5)
                patterns["organism"] = {
                    "value": top_organisms[0][0],
                    "confidence": top_organisms[0][1] / total_searches,
                    "values": [org for org, _ in top_organisms],
                    "counts": dict(top_organisms),
                    "frequency": sum(organism_counts.values()) / total_searches,
                    "total_searches": total_searches,
                }

            # Build platform pattern
            if platform_counts:
                top_platforms = platform_counts.most_common(5)
                patterns["platform"] = {
                    "value": top_platforms[0][0],
                    "confidence": top_platforms[0][1] / total_searches,
                    "values": [plat for plat, _ in top_platforms],
                    "counts": dict(top_platforms),
                    "frequency": sum(platform_counts.values()) / total_searches,
                    "total_searches": total_searches,
                }

            # Build disease area pattern
            if disease_counts:
                top_diseases = disease_counts.most_common(5)
                patterns["disease_area"] = {
                    "value": top_diseases[0][0],
                    "confidence": top_diseases[0][1] / total_searches,
                    "values": [dis for dis, _ in top_diseases],
                    "counts": dict(top_diseases),
                    "frequency": sum(disease_counts.values()) / total_searches,
                    "total_searches": total_searches,
                }

            return patterns

        except Exception as e:
            logger.error(f"Failed to analyze search patterns for user {user_id}: {e}")
            return {}
