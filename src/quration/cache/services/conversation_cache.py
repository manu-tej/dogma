"""Conversation context caching service.

This service provides caching for hot conversation contexts with 24-hour TTL.
It implements write-through cache pattern for mutations and cache-aside for reads.

Cache pattern:
- Key: conv:{conversation_id}:context
- TTL: 24 hours (86400 seconds)
- Write-through: Updates go to both cache and database
- Cache-aside: Read from cache, fallback to database on miss
"""

import logging
from typing import Any, Optional

from quration.cache.redis_client import get_redis_client
from quration.cache.utils import CacheKeyGenerator, CacheSerializer, get_cache_stats
from quration.config import get_config

logger = logging.getLogger(__name__)


class ConversationCache:
    """Cache service for conversation contexts.

    This service manages caching of conversation contexts with:
    - 24-hour TTL for hot data
    - Write-through cache pattern
    - Automatic fallback to database
    - Cache invalidation utilities

    Attributes:
        key_gen: Cache key generator
        ttl: Time to live in seconds (24 hours)
        stats: Cache statistics tracker
    """

    def __init__(self):
        """Initialize conversation cache service."""
        config = get_config()
        self.key_gen = CacheKeyGenerator(prefix=config.redis.key_prefix)
        self.ttl = config.redis.ttl_conversation
        self.stats = get_cache_stats()
        self.redis_client = get_redis_client()

    def get(self, conversation_id: str) -> Optional[dict[str, Any]]:
        """Get conversation context from cache.

        Implements cache-aside pattern:
        1. Check cache first
        2. Return cached data if found
        3. Return None on cache miss (caller should fetch from database)

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            Conversation context dictionary if cached, None otherwise
        """
        cache_key = self.key_gen.conversation_context(conversation_id)

        # Check if Redis is available
        if not self.redis_client.is_available():
            logger.debug(f"Redis unavailable, skipping cache for conversation {conversation_id}")
            self.stats.record_error()
            return None

        # Try to get from cache
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                self.stats.record_hit()
                logger.debug(f"Cache hit for conversation: {conversation_id}")
                return CacheSerializer.deserialize(cached_data)
            else:
                self.stats.record_miss()
                logger.debug(f"Cache miss for conversation: {conversation_id}")
                return None

        except Exception as e:
            logger.error(f"Error reading conversation cache: {e}", exc_info=True)
            self.stats.record_error()
            return None

    def set(
        self,
        conversation_id: str,
        context: dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Set conversation context in cache.

        Implements write-through cache pattern:
        - Cache the data with 24-hour TTL
        - Caller should also write to database

        Args:
            conversation_id: Unique conversation identifier
            context: Conversation context data to cache
            ttl: Optional custom TTL in seconds (defaults to 24 hours)

        Returns:
            True if cached successfully, False otherwise
        """
        cache_key = self.key_gen.conversation_context(conversation_id)
        cache_ttl = ttl or self.ttl

        # Check if Redis is available
        if not self.redis_client.is_available():
            logger.debug(f"Redis unavailable, skipping cache write for conversation {conversation_id}")
            return False

        # Cache the context
        try:
            serialized = CacheSerializer.serialize(context)
            success = self.redis_client.set(cache_key, serialized, ttl=cache_ttl)

            if success:
                logger.debug(
                    f"Cached conversation {conversation_id} with TTL {cache_ttl}s"
                )
            else:
                logger.warning(f"Failed to cache conversation {conversation_id}")

            return success

        except Exception as e:
            logger.error(f"Error writing conversation cache: {e}", exc_info=True)
            return False

    def delete(self, conversation_id: str) -> bool:
        """Delete conversation context from cache.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            True if deleted, False otherwise
        """
        cache_key = self.key_gen.conversation_context(conversation_id)

        if not self.redis_client.is_available():
            return False

        try:
            deleted = self.redis_client.delete(cache_key)
            if deleted:
                logger.debug(f"Deleted conversation cache: {conversation_id}")
            return deleted

        except Exception as e:
            logger.error(f"Error deleting conversation cache: {e}", exc_info=True)
            return False

    def exists(self, conversation_id: str) -> bool:
        """Check if conversation context exists in cache.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            True if exists in cache, False otherwise
        """
        cache_key = self.key_gen.conversation_context(conversation_id)

        if not self.redis_client.is_available():
            return False

        return self.redis_client.exists(cache_key)

    def invalidate_all(self) -> int:
        """Invalidate all conversation caches.

        Warning: This deletes ALL conversation caches!

        Returns:
            Number of keys deleted
        """
        if not self.redis_client.is_available():
            return 0

        pattern = f"{self.key_gen.prefix}conv:*:context"
        deleted = self.redis_client.delete_pattern(pattern)
        logger.warning(f"Invalidated all conversation caches ({deleted} keys)")
        return deleted

    def extend_ttl(self, conversation_id: str, ttl: Optional[int] = None) -> bool:
        """Extend TTL for a conversation cache.

        Useful for keeping active conversations hot.

        Args:
            conversation_id: Unique conversation identifier
            ttl: New TTL in seconds (defaults to 24 hours)

        Returns:
            True if TTL was extended, False otherwise
        """
        cache_key = self.key_gen.conversation_context(conversation_id)
        cache_ttl = ttl or self.ttl

        if not self.redis_client.is_available():
            return False

        try:
            success = self.redis_client.expire(cache_key, cache_ttl)
            if success:
                logger.debug(f"Extended TTL for conversation {conversation_id} to {cache_ttl}s")
            return success

        except Exception as e:
            logger.error(f"Error extending conversation cache TTL: {e}", exc_info=True)
            return False

    def get_ttl(self, conversation_id: str) -> int:
        """Get remaining TTL for a conversation cache.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            TTL in seconds, -1 if no TTL, -2 if key doesn't exist
        """
        cache_key = self.key_gen.conversation_context(conversation_id)

        if not self.redis_client.is_available():
            return -2

        return self.redis_client.ttl(cache_key)


# Singleton instance
_conversation_cache: Optional[ConversationCache] = None


def get_conversation_cache() -> ConversationCache:
    """Get or create singleton conversation cache instance.

    Returns:
        ConversationCache instance
    """
    global _conversation_cache

    if _conversation_cache is None:
        _conversation_cache = ConversationCache()

    return _conversation_cache
