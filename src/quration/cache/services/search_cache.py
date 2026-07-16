"""Search results caching service.

This service provides caching for recent search results with 1-hour TTL.
It implements write-through cache pattern for mutations and cache-aside for reads.

Cache pattern:
- Key: search:{search_id}:results
- TTL: 1 hour (3600 seconds)
- Write-through: Updates go to both cache and database
- Cache-aside: Read from cache, fallback to database on miss
- Search ID: MD5 hash of search parameters for consistent caching
"""

import logging
from typing import Any, Optional

from quration.cache.redis_client import get_redis_client
from quration.cache.utils import CacheKeyGenerator, CacheSerializer, get_cache_stats
from quration.config import get_config

logger = logging.getLogger(__name__)


class SearchCache:
    """Cache service for search results.

    This service manages caching of search results with:
    - 1-hour TTL for frequently changing data
    - Write-through cache pattern
    - Automatic fallback to database
    - Parameter-based cache key generation

    Attributes:
        key_gen: Cache key generator
        ttl: Time to live in seconds (1 hour)
        stats: Cache statistics tracker
    """

    def __init__(self):
        """Initialize search cache service."""
        config = get_config()
        self.key_gen = CacheKeyGenerator(prefix=config.redis.key_prefix)
        self.ttl = config.redis.ttl_search
        self.stats = get_cache_stats()
        self.redis_client = get_redis_client()

    def generate_search_id(self, **search_params: Any) -> str:
        """Generate search ID from search parameters.

        Creates a stable hash from search parameters for cache key.

        Args:
            **search_params: Search parameters (query, filters, pagination, etc.)

        Returns:
            MD5 hash of sorted search parameters

        Example:
            >>> cache.generate_search_id(
            ...     query="gene expression",
            ...     organism="human",
            ...     limit=10
            ... )
            'a1b2c3d4e5f6...'
        """
        return CacheKeyGenerator.hash_params(**search_params)

    def get(self, search_id: str) -> Optional[dict[str, Any]]:
        """Get search results from cache.

        Implements cache-aside pattern:
        1. Check cache first
        2. Return cached data if found
        3. Return None on cache miss (caller should fetch from database)

        Args:
            search_id: Unique search identifier (hash of search params)

        Returns:
            Search results dictionary if cached, None otherwise
        """
        cache_key = self.key_gen.search_result(search_id)

        # Check if Redis is available
        if not self.redis_client.is_available():
            logger.debug(f"Redis unavailable, skipping cache for search {search_id}")
            self.stats.record_error()
            return None

        # Try to get from cache
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                self.stats.record_hit()
                logger.debug(f"Cache hit for search: {search_id}")
                return CacheSerializer.deserialize(cached_data)
            else:
                self.stats.record_miss()
                logger.debug(f"Cache miss for search: {search_id}")
                return None

        except Exception as e:
            logger.error(f"Error reading search cache: {e}", exc_info=True)
            self.stats.record_error()
            return None

    def get_by_params(self, **search_params: Any) -> Optional[dict[str, Any]]:
        """Get search results from cache using search parameters.

        Convenience method that generates search ID from parameters.

        Args:
            **search_params: Search parameters

        Returns:
            Search results dictionary if cached, None otherwise
        """
        search_id = self.generate_search_id(**search_params)
        return self.get(search_id)

    def set(
        self,
        search_id: str,
        results: dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Set search results in cache.

        Implements write-through cache pattern:
        - Cache the data with 1-hour TTL
        - Caller should also write to database if needed

        Args:
            search_id: Unique search identifier (hash of search params)
            results: Search results data to cache
            ttl: Optional custom TTL in seconds (defaults to 1 hour)

        Returns:
            True if cached successfully, False otherwise
        """
        cache_key = self.key_gen.search_result(search_id)
        cache_ttl = ttl or self.ttl

        # Check if Redis is available
        if not self.redis_client.is_available():
            logger.debug(f"Redis unavailable, skipping cache write for search {search_id}")
            return False

        # Cache the results
        try:
            serialized = CacheSerializer.serialize(results)
            success = self.redis_client.set(cache_key, serialized, ttl=cache_ttl)

            if success:
                logger.debug(
                    f"Cached search results {search_id} with TTL {cache_ttl}s"
                )
            else:
                logger.warning(f"Failed to cache search results {search_id}")

            return success

        except Exception as e:
            logger.error(f"Error writing search cache: {e}", exc_info=True)
            return False

    def set_by_params(
        self,
        results: dict[str, Any],
        ttl: Optional[int] = None,
        **search_params: Any
    ) -> bool:
        """Set search results in cache using search parameters.

        Convenience method that generates search ID from parameters.

        Args:
            results: Search results data to cache
            ttl: Optional custom TTL in seconds
            **search_params: Search parameters

        Returns:
            True if cached successfully, False otherwise
        """
        search_id = self.generate_search_id(**search_params)
        return self.set(search_id, results, ttl)

    def delete(self, search_id: str) -> bool:
        """Delete search results from cache.

        Args:
            search_id: Unique search identifier

        Returns:
            True if deleted, False otherwise
        """
        cache_key = self.key_gen.search_result(search_id)

        if not self.redis_client.is_available():
            return False

        try:
            deleted = self.redis_client.delete(cache_key)
            if deleted:
                logger.debug(f"Deleted search cache: {search_id}")
            return deleted

        except Exception as e:
            logger.error(f"Error deleting search cache: {e}", exc_info=True)
            return False

    def exists(self, search_id: str) -> bool:
        """Check if search results exist in cache.

        Args:
            search_id: Unique search identifier

        Returns:
            True if exists in cache, False otherwise
        """
        cache_key = self.key_gen.search_result(search_id)

        if not self.redis_client.is_available():
            return False

        return self.redis_client.exists(cache_key)

    def invalidate_all(self) -> int:
        """Invalidate all search result caches.

        Warning: This deletes ALL search result caches!

        Returns:
            Number of keys deleted
        """
        if not self.redis_client.is_available():
            return 0

        pattern = f"{self.key_gen.prefix}search:*:results"
        deleted = self.redis_client.delete_pattern(pattern)
        logger.warning(f"Invalidated all search caches ({deleted} keys)")
        return deleted

    def get_ttl(self, search_id: str) -> int:
        """Get remaining TTL for a search result cache.

        Args:
            search_id: Unique search identifier

        Returns:
            TTL in seconds, -1 if no TTL, -2 if key doesn't exist
        """
        cache_key = self.key_gen.search_result(search_id)

        if not self.redis_client.is_available():
            return -2

        return self.redis_client.ttl(cache_key)


# Singleton instance
_search_cache: Optional[SearchCache] = None


def get_search_cache() -> SearchCache:
    """Get or create singleton search cache instance.

    Returns:
        SearchCache instance
    """
    global _search_cache

    if _search_cache is None:
        _search_cache = SearchCache()

    return _search_cache
