"""User preferences caching service.

This service provides caching for user preferences with 7-day TTL.
It implements write-through cache pattern for mutations and cache-aside for reads.

Cache pattern:
- Key: user:{user_id}:prefs
- TTL: 7 days (604800 seconds)
- Write-through: Updates go to both cache and database
- Cache-aside: Read from cache, fallback to database on miss
"""

import logging
from typing import Any, Optional

from quration.cache.redis_client import get_redis_client
from quration.cache.utils import CacheKeyGenerator, CacheSerializer, get_cache_stats
from quration.config import get_config

logger = logging.getLogger(__name__)


class PreferenceCache:
    """Cache service for user preferences.

    This service manages caching of user preferences with:
    - 7-day TTL for infrequently changing data
    - Write-through cache pattern
    - Automatic fallback to database
    - Cache invalidation utilities

    Attributes:
        key_gen: Cache key generator
        ttl: Time to live in seconds (7 days)
        stats: Cache statistics tracker
    """

    def __init__(self):
        """Initialize preference cache service."""
        config = get_config()
        self.key_gen = CacheKeyGenerator(prefix=config.redis.key_prefix)
        self.ttl = config.redis.ttl_preference
        self.stats = get_cache_stats()
        self.redis_client = get_redis_client()

    def get(self, user_id: str) -> Optional[dict[str, Any]]:
        """Get user preferences from cache.

        Implements cache-aside pattern:
        1. Check cache first
        2. Return cached data if found
        3. Return None on cache miss (caller should fetch from database)

        Args:
            user_id: Unique user identifier

        Returns:
            User preferences dictionary if cached, None otherwise
        """
        cache_key = self.key_gen.user_preference(user_id)

        # Check if Redis is available
        if not self.redis_client.is_available():
            logger.debug(f"Redis unavailable, skipping cache for user {user_id}")
            self.stats.record_error()
            return None

        # Try to get from cache
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                self.stats.record_hit()
                logger.debug(f"Cache hit for user preferences: {user_id}")
                return CacheSerializer.deserialize(cached_data)
            else:
                self.stats.record_miss()
                logger.debug(f"Cache miss for user preferences: {user_id}")
                return None

        except Exception as e:
            logger.error(f"Error reading preference cache: {e}", exc_info=True)
            self.stats.record_error()
            return None

    def set(
        self,
        user_id: str,
        preferences: dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Set user preferences in cache.

        Implements write-through cache pattern:
        - Cache the data with 7-day TTL
        - Caller should also write to database

        Args:
            user_id: Unique user identifier
            preferences: User preferences data to cache
            ttl: Optional custom TTL in seconds (defaults to 7 days)

        Returns:
            True if cached successfully, False otherwise
        """
        cache_key = self.key_gen.user_preference(user_id)
        cache_ttl = ttl or self.ttl

        # Check if Redis is available
        if not self.redis_client.is_available():
            logger.debug(f"Redis unavailable, skipping cache write for user {user_id}")
            return False

        # Cache the preferences
        try:
            serialized = CacheSerializer.serialize(preferences)
            success = self.redis_client.set(cache_key, serialized, ttl=cache_ttl)

            if success:
                logger.debug(
                    f"Cached user preferences {user_id} with TTL {cache_ttl}s"
                )
            else:
                logger.warning(f"Failed to cache user preferences {user_id}")

            return success

        except Exception as e:
            logger.error(f"Error writing preference cache: {e}", exc_info=True)
            return False

    def delete(self, user_id: str) -> bool:
        """Delete user preferences from cache.

        Args:
            user_id: Unique user identifier

        Returns:
            True if deleted, False otherwise
        """
        cache_key = self.key_gen.user_preference(user_id)

        if not self.redis_client.is_available():
            return False

        try:
            deleted = self.redis_client.delete(cache_key)
            if deleted:
                logger.debug(f"Deleted preference cache: {user_id}")
            return deleted

        except Exception as e:
            logger.error(f"Error deleting preference cache: {e}", exc_info=True)
            return False

    def exists(self, user_id: str) -> bool:
        """Check if user preferences exist in cache.

        Args:
            user_id: Unique user identifier

        Returns:
            True if exists in cache, False otherwise
        """
        cache_key = self.key_gen.user_preference(user_id)

        if not self.redis_client.is_available():
            return False

        return self.redis_client.exists(cache_key)

    def invalidate_all(self) -> int:
        """Invalidate all user preference caches.

        Warning: This deletes ALL user preference caches!

        Returns:
            Number of keys deleted
        """
        if not self.redis_client.is_available():
            return 0

        pattern = f"{self.key_gen.prefix}user:*:prefs"
        deleted = self.redis_client.delete_pattern(pattern)
        logger.warning(f"Invalidated all preference caches ({deleted} keys)")
        return deleted

    def extend_ttl(self, user_id: str, ttl: Optional[int] = None) -> bool:
        """Extend TTL for a user preference cache.

        Args:
            user_id: Unique user identifier
            ttl: New TTL in seconds (defaults to 7 days)

        Returns:
            True if TTL was extended, False otherwise
        """
        cache_key = self.key_gen.user_preference(user_id)
        cache_ttl = ttl or self.ttl

        if not self.redis_client.is_available():
            return False

        try:
            success = self.redis_client.expire(cache_key, cache_ttl)
            if success:
                logger.debug(f"Extended TTL for user {user_id} preferences to {cache_ttl}s")
            return success

        except Exception as e:
            logger.error(f"Error extending preference cache TTL: {e}", exc_info=True)
            return False

    def get_ttl(self, user_id: str) -> int:
        """Get remaining TTL for a user preference cache.

        Args:
            user_id: Unique user identifier

        Returns:
            TTL in seconds, -1 if no TTL, -2 if key doesn't exist
        """
        cache_key = self.key_gen.user_preference(user_id)

        if not self.redis_client.is_available():
            return -2

        return self.redis_client.ttl(cache_key)


# Singleton instance
_preference_cache: Optional[PreferenceCache] = None


def get_preference_cache() -> PreferenceCache:
    """Get or create singleton preference cache instance.

    Returns:
        PreferenceCache instance
    """
    global _preference_cache

    if _preference_cache is None:
        _preference_cache = PreferenceCache()

    return _preference_cache
