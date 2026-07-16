"""
Result cache manager for interpretation tool results.

This module provides a flexible caching system supporting:
- In-memory caching with LRU eviction
- Redis backend for distributed caching
- Cache statistics and monitoring
- Automatic serialization/deserialization
"""

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    errors: int = 0
    total_hit_latency_ms: float = 0.0
    total_miss_latency_ms: float = 0.0

    @property
    def total_requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    @property
    def avg_hit_latency_ms(self) -> float:
        if self.hits == 0:
            return 0.0
        return self.total_hit_latency_ms / self.hits

    @property
    def avg_miss_latency_ms(self) -> float:
        if self.misses == 0:
            return 0.0
        return self.total_miss_latency_ms / self.misses

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "evictions": self.evictions,
            "errors": self.errors,
            "total_requests": self.total_requests,
            "hit_rate": round(self.hit_rate, 4),
            "avg_hit_latency_ms": round(self.avg_hit_latency_ms, 3),
            "avg_miss_latency_ms": round(self.avg_miss_latency_ms, 3),
        }


class CacheEntry(BaseModel):
    """Cache entry with metadata."""

    data: dict[str, Any]
    tool_name: str
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: datetime | None = None

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def ttl_remaining(self) -> float:
        """Remaining TTL in seconds."""
        delta = self.expires_at - datetime.utcnow()
        return max(0.0, delta.total_seconds())


class CacheBackend(ABC):
    """Abstract base class for cache backends."""

    @abstractmethod
    async def get(self, key: str) -> CacheEntry | None:
        """Get an entry from the cache."""
        pass

    @abstractmethod
    async def set(
        self, key: str, entry: CacheEntry, ttl_seconds: int | None = None
    ) -> bool:
        """Set an entry in the cache."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete an entry from the cache."""
        pass

    @abstractmethod
    async def clear(self) -> int:
        """Clear all entries. Returns count of cleared entries."""
        pass

    @abstractmethod
    async def keys(self, pattern: str | None = None) -> list[str]:
        """Get all keys matching a pattern."""
        pass

    @abstractmethod
    async def size(self) -> int:
        """Get the number of entries in the cache."""
        pass


class InMemoryBackend(CacheBackend):
    """In-memory cache backend with LRU eviction.

    Thread-safe implementation using asyncio locks.
    """

    def __init__(self, max_size: int = 1000):
        """Initialize the backend.

        Args:
            max_size: Maximum number of entries before eviction
        """
        self._max_size = max_size
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._eviction_count = 0

    async def get(self, key: str) -> CacheEntry | None:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None

            # Check expiration
            if entry.is_expired:
                del self._cache[key]
                return None

            # Update access metadata and move to end (most recently used)
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()
            self._cache.move_to_end(key)

            return entry

    async def set(
        self, key: str, entry: CacheEntry, ttl_seconds: int | None = None
    ) -> bool:
        async with self._lock:
            # Update expiration if TTL provided
            if ttl_seconds is not None:
                entry.expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

            # Remove existing entry if present
            if key in self._cache:
                del self._cache[key]

            # Evict oldest entries if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
                self._eviction_count += 1

            self._cache[key] = entry
            return True

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> int:
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count

    async def keys(self, pattern: str | None = None) -> list[str]:
        async with self._lock:
            if pattern is None:
                return list(self._cache.keys())

            # Simple pattern matching (prefix only)
            return [k for k in self._cache.keys() if k.startswith(pattern)]

    async def size(self) -> int:
        async with self._lock:
            return len(self._cache)

    @property
    def eviction_count(self) -> int:
        return self._eviction_count


class RedisBackend(CacheBackend):
    """Redis cache backend for distributed caching.

    Requires redis-py[async] package.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        prefix: str = "quration:cache:",
    ):
        """Initialize Redis backend.

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password
            prefix: Key prefix for namespacing
        """
        self._host = host
        self._port = port
        self._db = db
        self._password = password
        self._prefix = prefix
        self._client: Any = None

    async def _get_client(self) -> Any:
        """Get or create Redis client."""
        if self._client is None:
            try:
                import redis.asyncio as redis

                self._client = redis.Redis(
                    host=self._host,
                    port=self._port,
                    db=self._db,
                    password=self._password,
                    decode_responses=True,
                )
            except ImportError:
                raise ImportError(
                    "redis package required for Redis backend. "
                    "Install with: pip install redis[async]"
                )
        return self._client

    def _make_key(self, key: str) -> str:
        """Add prefix to key."""
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> CacheEntry | None:
        try:
            client = await self._get_client()
            data = await client.get(self._make_key(key))
            if data is None:
                return None

            entry_dict = json.loads(data)
            entry = CacheEntry(**entry_dict)

            # Update access metadata
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()

            # Update in Redis
            ttl = await client.ttl(self._make_key(key))
            if ttl > 0:
                await client.setex(
                    self._make_key(key), ttl, entry.model_dump_json()
                )

            return entry

        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def set(
        self, key: str, entry: CacheEntry, ttl_seconds: int | None = None
    ) -> bool:
        try:
            client = await self._get_client()

            # Calculate TTL
            if ttl_seconds is None:
                ttl_seconds = int(entry.ttl_remaining)

            if ttl_seconds <= 0:
                return False

            await client.setex(
                self._make_key(key), ttl_seconds, entry.model_dump_json()
            )
            return True

        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        try:
            client = await self._get_client()
            result = await client.delete(self._make_key(key))
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    async def clear(self) -> int:
        try:
            client = await self._get_client()
            keys = await client.keys(f"{self._prefix}*")
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return 0

    async def keys(self, pattern: str | None = None) -> list[str]:
        try:
            client = await self._get_client()
            if pattern:
                redis_pattern = f"{self._prefix}{pattern}*"
            else:
                redis_pattern = f"{self._prefix}*"

            keys = await client.keys(redis_pattern)
            # Remove prefix from returned keys
            prefix_len = len(self._prefix)
            return [k[prefix_len:] for k in keys]
        except Exception as e:
            logger.error(f"Redis keys error: {e}")
            return []

    async def size(self) -> int:
        keys = await self.keys()
        return len(keys)

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.close()
            self._client = None


class ResultCacheManager:
    """Manager for caching tool execution results.

    Provides a high-level interface for caching with:
    - Automatic key generation
    - Statistics tracking
    - Cache warming and invalidation
    - Multiple backend support

    Example:
        ```python
        cache = ResultCacheManager()

        # Cache a result
        await cache.cache_result(
            tool_name="search_pubmed",
            inputs={"query": "TP53"},
            result={"articles": [...]},
            ttl_seconds=3600
        )

        # Get from cache
        result = await cache.get_cached_result(
            tool_name="search_pubmed",
            inputs={"query": "TP53"}
        )
        ```
    """

    def __init__(
        self,
        backend: CacheBackend | None = None,
        default_ttl_seconds: int = 3600,
        enable_stats: bool = True,
    ):
        """Initialize the cache manager.

        Args:
            backend: Cache backend (defaults to InMemoryBackend)
            default_ttl_seconds: Default TTL for cached entries
            enable_stats: Enable statistics tracking
        """
        self._backend = backend or InMemoryBackend()
        self._default_ttl = default_ttl_seconds
        self._enable_stats = enable_stats
        self._stats = CacheStats()

    def _generate_key(self, tool_name: str, inputs: dict[str, Any]) -> str:
        """Generate a cache key for a tool call.

        Args:
            tool_name: Name of the tool
            inputs: Input parameters

        Returns:
            Cache key string
        """
        # Normalize inputs for consistent hashing
        sorted_inputs = json.dumps(inputs, sort_keys=True, default=str)
        key_data = f"{tool_name}:{sorted_inputs}"
        hash_value = hashlib.sha256(key_data.encode()).hexdigest()[:16]
        return f"{tool_name}:{hash_value}"

    async def get_cached_result(
        self, tool_name: str, inputs: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Get a cached result if available.

        Args:
            tool_name: Name of the tool
            inputs: Input parameters

        Returns:
            Cached result data or None
        """
        start_time = time.time()
        key = self._generate_key(tool_name, inputs)

        try:
            entry = await self._backend.get(key)
            latency_ms = (time.time() - start_time) * 1000

            if entry is not None:
                if self._enable_stats:
                    self._stats.hits += 1
                    self._stats.total_hit_latency_ms += latency_ms
                return entry.data
            else:
                if self._enable_stats:
                    self._stats.misses += 1
                    self._stats.total_miss_latency_ms += latency_ms
                return None

        except Exception as e:
            logger.error(f"Cache get error: {e}")
            if self._enable_stats:
                self._stats.errors += 1
            return None

    async def cache_result(
        self,
        tool_name: str,
        inputs: dict[str, Any],
        result: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> bool:
        """Cache a tool result.

        Args:
            tool_name: Name of the tool
            inputs: Input parameters
            result: Result to cache
            ttl_seconds: TTL override

        Returns:
            True if cached successfully
        """
        key = self._generate_key(tool_name, inputs)
        ttl = ttl_seconds or self._default_ttl

        entry = CacheEntry(
            data=result,
            tool_name=tool_name,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(seconds=ttl),
        )

        try:
            success = await self._backend.set(key, entry, ttl)
            if success and self._enable_stats:
                self._stats.sets += 1
            return success

        except Exception as e:
            logger.error(f"Cache set error: {e}")
            if self._enable_stats:
                self._stats.errors += 1
            return False

    async def invalidate(
        self, tool_name: str, inputs: dict[str, Any] | None = None
    ) -> int:
        """Invalidate cached results.

        Args:
            tool_name: Name of the tool
            inputs: Specific inputs to invalidate (or None for all tool results)

        Returns:
            Number of entries invalidated
        """
        try:
            if inputs is not None:
                # Invalidate specific entry
                key = self._generate_key(tool_name, inputs)
                success = await self._backend.delete(key)
                count = 1 if success else 0
            else:
                # Invalidate all entries for tool
                keys = await self._backend.keys(f"{tool_name}:")
                count = 0
                for key in keys:
                    if await self._backend.delete(key):
                        count += 1

            if self._enable_stats:
                self._stats.deletes += count

            return count

        except Exception as e:
            logger.error(f"Cache invalidate error: {e}")
            if self._enable_stats:
                self._stats.errors += 1
            return 0

    async def clear(self) -> int:
        """Clear all cached results.

        Returns:
            Number of entries cleared
        """
        try:
            count = await self._backend.clear()
            if self._enable_stats:
                self._stats.deletes += count
            return count
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            if self._enable_stats:
                self._stats.errors += 1
            return 0

    async def warm_cache(
        self,
        entries: list[tuple[str, dict[str, Any], dict[str, Any], int]],
    ) -> int:
        """Warm the cache with pre-computed results.

        Args:
            entries: List of (tool_name, inputs, result, ttl_seconds) tuples

        Returns:
            Number of entries successfully cached
        """
        count = 0
        for tool_name, inputs, result, ttl in entries:
            if await self.cache_result(tool_name, inputs, result, ttl):
                count += 1
        return count

    async def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Statistics dictionary
        """
        stats = self._stats.to_dict()
        stats["size"] = await self._backend.size()

        # Add backend-specific stats
        if isinstance(self._backend, InMemoryBackend):
            stats["evictions"] = self._backend.eviction_count

        return stats

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._stats = CacheStats()

    async def get_cache_info(
        self, tool_name: str | None = None
    ) -> dict[str, Any]:
        """Get information about cached entries.

        Args:
            tool_name: Filter by tool name

        Returns:
            Cache information
        """
        pattern = f"{tool_name}:" if tool_name else None
        keys = await self._backend.keys(pattern)

        entries_info = []
        for key in keys[:100]:  # Limit to first 100
            entry = await self._backend.get(key)
            if entry:
                entries_info.append(
                    {
                        "key": key,
                        "tool_name": entry.tool_name,
                        "created_at": entry.created_at.isoformat(),
                        "ttl_remaining": entry.ttl_remaining,
                        "access_count": entry.access_count,
                    }
                )

        return {
            "total_keys": len(keys),
            "entries": entries_info,
        }


# Singleton instance
_cache_manager: ResultCacheManager | None = None


def get_cache_manager() -> ResultCacheManager:
    """Get or create the global cache manager.

    Returns:
        ResultCacheManager instance
    """
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = ResultCacheManager()
    return _cache_manager


def configure_cache(
    backend: str = "memory",
    redis_url: str | None = None,
    max_size: int = 1000,
    default_ttl: int = 3600,
) -> ResultCacheManager:
    """Configure and return the global cache manager.

    Args:
        backend: 'memory' or 'redis'
        redis_url: Redis connection URL (if backend='redis')
        max_size: Maximum cache size (for memory backend)
        default_ttl: Default TTL in seconds

    Returns:
        Configured ResultCacheManager
    """
    global _cache_manager

    if backend == "redis" and redis_url:
        # Parse Redis URL
        from urllib.parse import urlparse

        parsed = urlparse(redis_url)
        cache_backend = RedisBackend(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            password=parsed.password,
            db=int(parsed.path.lstrip("/") or 0),
        )
    else:
        cache_backend = InMemoryBackend(max_size=max_size)

    _cache_manager = ResultCacheManager(
        backend=cache_backend,
        default_ttl_seconds=default_ttl,
    )

    return _cache_manager
