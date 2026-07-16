"""Cache utilities for key generation, serialization, and common operations.

This module provides helper functions for:
- Cache key generation with consistent naming
- JSON serialization/deserialization for complex objects
- Cache statistics and monitoring
- Common cache patterns
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Optional, TypeVar, Generic
from functools import wraps

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheKeyGenerator:
    """Generate cache keys with consistent naming conventions.

    Key patterns:
    - Conversation contexts: conv:{conversation_id}:context
    - User preferences: user:{user_id}:prefs
    - Search results: search:{search_id}:results
    - Session tokens: session:{token}
    """

    def __init__(self, prefix: str = "quration:"):
        """Initialize key generator.

        Args:
            prefix: Global prefix for all cache keys
        """
        self.prefix = prefix

    def _make_key(self, *parts: str) -> str:
        """Create cache key from parts.

        Args:
            *parts: Key components to join

        Returns:
            Formatted cache key
        """
        return self.prefix + ":".join(str(p) for p in parts)

    def conversation_context(self, conversation_id: str) -> str:
        """Generate key for conversation context.

        Args:
            conversation_id: Unique conversation identifier

        Returns:
            Cache key: quration:conv:{conversation_id}:context
        """
        return self._make_key("conv", conversation_id, "context")

    def user_preference(self, user_id: str) -> str:
        """Generate key for user preferences.

        Args:
            user_id: Unique user identifier

        Returns:
            Cache key: quration:user:{user_id}:prefs
        """
        return self._make_key("user", user_id, "prefs")

    def search_result(self, search_id: str) -> str:
        """Generate key for search results.

        Args:
            search_id: Unique search identifier (hash of search params)

        Returns:
            Cache key: quration:search:{search_id}:results
        """
        return self._make_key("search", search_id, "results")

    def session_token(self, token: str) -> str:
        """Generate key for session token.

        Args:
            token: Session token

        Returns:
            Cache key: quration:session:{token}
        """
        return self._make_key("session", token)

    @staticmethod
    def hash_params(**kwargs: Any) -> str:
        """Generate hash from parameters for cache key.

        Useful for creating stable cache keys from search parameters.

        Args:
            **kwargs: Parameters to hash

        Returns:
            MD5 hash of sorted parameters

        Example:
            >>> CacheKeyGenerator.hash_params(query="gene", limit=10)
            'a1b2c3d4e5f6...'
        """
        # Sort parameters for consistent hashing
        sorted_params = sorted(kwargs.items())
        param_str = json.dumps(sorted_params, sort_keys=True)
        return hashlib.md5(param_str.encode()).hexdigest()


class CacheSerializer:
    """Serialize/deserialize objects for Redis cache storage.

    Supports:
    - Pydantic models
    - Python dictionaries
    - Lists
    - Primitive types (str, int, float, bool)
    """

    @staticmethod
    def serialize(obj: Any) -> str:
        """Serialize object to JSON string for Redis storage.

        Args:
            obj: Object to serialize (supports Pydantic models, dicts, lists, primitives)

        Returns:
            JSON string representation

        Raises:
            TypeError: If object is not serializable
        """
        try:
            if isinstance(obj, BaseModel):
                # Pydantic model
                return obj.model_dump_json()
            elif isinstance(obj, (dict, list)):
                # Dict or list
                return json.dumps(obj)
            elif isinstance(obj, (str, int, float, bool, type(None))):
                # Primitive types
                return json.dumps(obj)
            elif hasattr(obj, "__dict__"):
                # Objects with __dict__
                return json.dumps(obj.__dict__)
            else:
                raise TypeError(f"Object of type {type(obj)} is not serializable")

        except Exception as e:
            logger.error(f"Failed to serialize object: {e}", exc_info=True)
            raise

    @staticmethod
    def deserialize(data: str, model_class: Optional[type[T]] = None) -> T:
        """Deserialize JSON string from Redis to Python object.

        Args:
            data: JSON string from Redis
            model_class: Optional Pydantic model class for validation

        Returns:
            Deserialized object

        Raises:
            ValueError: If deserialization fails
        """
        try:
            if model_class and issubclass(model_class, BaseModel):
                # Deserialize to Pydantic model
                return model_class.model_validate_json(data)
            else:
                # Deserialize to dict/list/primitive
                return json.loads(data)

        except Exception as e:
            logger.error(f"Failed to deserialize data: {e}", exc_info=True)
            raise ValueError(f"Deserialization failed: {e}")


class CacheStats:
    """Track cache hit/miss statistics for monitoring.

    Attributes:
        hits: Number of cache hits
        misses: Number of cache misses
        errors: Number of cache errors
        total_requests: Total cache requests
    """

    def __init__(self):
        """Initialize cache statistics."""
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.total_requests = 0
        self._start_time = datetime.utcnow()

    def record_hit(self) -> None:
        """Record a cache hit."""
        self.hits += 1
        self.total_requests += 1

    def record_miss(self) -> None:
        """Record a cache miss."""
        self.misses += 1
        self.total_requests += 1

    def record_error(self) -> None:
        """Record a cache error."""
        self.errors += 1
        self.total_requests += 1

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate.

        Returns:
            Hit rate as a percentage (0-100)
        """
        if self.total_requests == 0:
            return 0.0
        return (self.hits / self.total_requests) * 100

    @property
    def miss_rate(self) -> float:
        """Calculate cache miss rate.

        Returns:
            Miss rate as a percentage (0-100)
        """
        if self.total_requests == 0:
            return 0.0
        return (self.misses / self.total_requests) * 100

    @property
    def error_rate(self) -> float:
        """Calculate cache error rate.

        Returns:
            Error rate as a percentage (0-100)
        """
        if self.total_requests == 0:
            return 0.0
        return (self.errors / self.total_requests) * 100

    def uptime_seconds(self) -> float:
        """Get uptime in seconds since stats started.

        Returns:
            Uptime in seconds
        """
        return (datetime.utcnow() - self._start_time).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert statistics to dictionary.

        Returns:
            Dictionary with all statistics
        """
        return {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "total_requests": self.total_requests,
            "hit_rate": round(self.hit_rate, 2),
            "miss_rate": round(self.miss_rate, 2),
            "error_rate": round(self.error_rate, 2),
            "uptime_seconds": round(self.uptime_seconds(), 2),
        }

    def reset(self) -> None:
        """Reset all statistics."""
        self.hits = 0
        self.misses = 0
        self.errors = 0
        self.total_requests = 0
        self._start_time = datetime.utcnow()


# Global cache statistics
_cache_stats = CacheStats()


def get_cache_stats() -> CacheStats:
    """Get global cache statistics.

    Returns:
        CacheStats instance
    """
    return _cache_stats


def cache_aside(
    key_generator,
    ttl: int,
    stats: Optional[CacheStats] = None
):
    """Decorator for cache-aside pattern.

    This decorator implements the cache-aside (lazy loading) pattern:
    1. Check cache for data
    2. If cache hit, return cached data
    3. If cache miss, call function, cache result, return data

    Args:
        key_generator: Function that generates cache key from function args
        ttl: Time to live in seconds
        stats: Optional CacheStats instance for tracking hits/misses

    Example:
        @cache_aside(
            key_generator=lambda user_id: f"user:{user_id}:profile",
            ttl=3600
        )
        def get_user_profile(user_id: str) -> dict:
            # Expensive database query
            return db.query_user(user_id)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from quration.cache.redis_client import get_redis_client

            # Generate cache key
            cache_key = key_generator(*args, **kwargs)

            # Get Redis client
            redis_client = get_redis_client()

            # Try to get from cache
            if redis_client.is_available():
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    if stats:
                        stats.record_hit()
                    logger.debug(f"Cache hit for key: {cache_key}")
                    try:
                        return CacheSerializer.deserialize(cached_data)
                    except Exception as e:
                        logger.warning(f"Failed to deserialize cached data: {e}")
                        # Fall through to function call

            # Cache miss - call function
            if stats:
                stats.record_miss()
            logger.debug(f"Cache miss for key: {cache_key}")

            result = func(*args, **kwargs)

            # Cache the result
            if redis_client.is_available() and result is not None:
                try:
                    serialized = CacheSerializer.serialize(result)
                    redis_client.set(cache_key, serialized, ttl=ttl)
                except Exception as e:
                    logger.warning(f"Failed to cache result: {e}")

            return result

        return wrapper
    return decorator


def invalidate_cache_pattern(pattern: str) -> int:
    """Invalidate all cache keys matching a pattern.

    Args:
        pattern: Key pattern (e.g., "user:123:*")

    Returns:
        Number of keys deleted
    """
    from quration.cache.redis_client import get_redis_client

    redis_client = get_redis_client()
    if not redis_client.is_available():
        logger.warning(f"Cannot invalidate cache pattern '{pattern}': Redis unavailable")
        return 0

    deleted = redis_client.delete_pattern(pattern)
    logger.info(f"Invalidated {deleted} cache keys matching pattern: {pattern}")
    return deleted
